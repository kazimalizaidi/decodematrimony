"""🎀 Household-roster adapter (PBS HIES / PSLM / LFS style files) -> couple-level frame. ✨

HIES has no 'couples file'. We build couples from the roster: in each household, the
head and their spouse (opposite sex), requiring exactly one head and one spouse.
You supply the column names and code values (verify them in the coding scheme!).
Output uses the canonical column names the cleaner expects, so every lens just works. 🧸

Known biases (also in README): only head+spouse pairs are observed, so couples living
inside a parent's household are missed (skews older); age at first marriage exists only in HIES Section 4 (ever-married women) and must be merged in.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .. import logger as log
from .dhs import RawDhs, sha256_file


@dataclass(frozen=True)
class RosterMap:
    """💗 All names/codes come from YOU, read off the official coding scheme."""

    household_id: str
    person_line: str
    relationship: str
    sex: str
    age: str
    education: str
    weight: str
    psu: str
    strata: str
    region: str
    head_code: int
    spouse_code: int
    male_code: int
    female_code: int
    edu_recode: dict[int, int]            # raw education code -> 0 none,1 primary,2 secondary,3 higher
    wealth_quintile: Optional[str] = None  # optional: e.g. a consumption-quintile column you merged in
    working: Optional[str] = None          # optional: wife employed (1/0) merged in from the labour section
    working_yes_code: int = 1
    marital_status: Optional[str] = None   # optional: keep only pairs where BOTH are in married_codes
    married_codes: tuple[int, ...] = (2,)  # HIES manual: 2 = currently married (6 = nikkah, no rukhsati)
    region_labels: dict[int, str] = field(default_factory=dict)
    wife_age_first_union: Optional[str] = None  # optional: HIES Section 4 "age at first marriage" merged onto the roster

    @classmethod
    def from_json(cls, path: Path) -> "RosterMap":
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw = {k: v for k, v in raw.items() if not k.startswith("_")}
        raw["edu_recode"] = {int(k): int(v) for k, v in raw["edu_recode"].items()}
        raw["region_labels"] = {int(k): str(v) for k, v in raw.get("region_labels", {}).items()}
        raw["married_codes"] = tuple(int(c) for c in raw.get("married_codes", [2]))
        return cls(**raw)


def couples_from_roster(roster: pd.DataFrame, m: RosterMap, source_name: str, sha256: str = "") -> RawDhs:
    """✨ Pair head and spouse per household. Households that don't have exactly one head and
    one opposite-sex spouse are dropped and counted (cream log), never guessed."""
    need = [m.household_id, m.person_line, m.relationship, m.sex, m.age, m.education, m.weight, m.psu, m.strata, m.region]
    need += [c for c in (m.wealth_quintile, m.working, m.marital_status, m.wife_age_first_union) if c]
    absent = [c for c in need if c not in roster.columns]
    if absent:
        log.failure(f"roster columns missing: {absent}")
        raise KeyError(f"roster columns missing: {absent}")
    r = roster[need].copy()
    heads = r[r[m.relationship] == m.head_code]
    spouses = r[r[m.relationship] == m.spouse_code]
    h_ok = heads.groupby(m.household_id).size().eq(1)
    s_ok = spouses.groupby(m.household_id).size().eq(1)
    good = h_ok[h_ok].index.intersection(s_ok[s_ok].index)
    n_hh = r[m.household_id].nunique()
    log.milestone(f"{len(good):,} of {n_hh:,} households have exactly one head and one spouse")
    heads = heads[heads[m.household_id].isin(good)].set_index(m.household_id)
    spouses = spouses[spouses[m.household_id].isin(good)].set_index(m.household_id)
    pair = heads.join(spouses, lsuffix="_h", rsuffix="_s", how="inner")
    opposite = ((pair[f"{m.sex}_h"] == m.male_code) & (pair[f"{m.sex}_s"] == m.female_code)) | \
               ((pair[f"{m.sex}_h"] == m.female_code) & (pair[f"{m.sex}_s"] == m.male_code))
    if (~opposite).any():
        log.missing(f"dropped {int((~opposite).sum()):,} same-sex or unknown-sex head/spouse pairs")
    pair = pair[opposite]
    if m.marital_status:
        ok_m = pair[f"{m.marital_status}_h"].isin(m.married_codes) & pair[f"{m.marital_status}_s"].isin(m.married_codes)
        if (~ok_m).any():
            log.missing(f"dropped {int((~ok_m).sum()):,} pairs where head/spouse not both currently married")
        pair = pair[ok_m]
    head_is_male = pair[f"{m.sex}_h"] == m.male_code

    def pick(col: str, want_male: bool) -> pd.Series:
        male = pair[f"{col}_h"].where(head_is_male, pair[f"{col}_s"])
        female = pair[f"{col}_s"].where(head_is_male, pair[f"{col}_h"])
        return male if want_male else female

    def edu(col: pd.Series) -> pd.Series:
        return pd.to_numeric(col, errors="coerce").map(lambda c: m.edu_recode.get(int(c), np.nan) if pd.notna(c) else np.nan)

    frame = pd.DataFrame({
        "caseid": pair.index.astype(str),
        "v005": pd.to_numeric(pair[f"{m.weight}_h"], errors="coerce") * 1_000_000.0,
        "v021": pd.to_numeric(pair[f"{m.psu}_h"], errors="coerce"),
        "v022": pd.to_numeric(pair[f"{m.strata}_h"], errors="coerce"),
        "v012": pd.to_numeric(pick(m.age, False), errors="coerce"),
        "mv012": pd.to_numeric(pick(m.age, True), errors="coerce"),
        "v106": edu(pick(m.education, False)),
        "mv106": edu(pick(m.education, True)),
        "v190": pd.to_numeric(pair[f"{m.wealth_quintile}_h"], errors="coerce") if m.wealth_quintile else np.nan,
        "v024": pd.to_numeric(pair[f"{m.region}_h"], errors="coerce"),
        "v511": pd.to_numeric(pick(m.wife_age_first_union, False), errors="coerce") if m.wife_age_first_union else np.nan,
        "v714": (pd.to_numeric(pick(m.working, False), errors="coerce") == m.working_yes_code).astype(float)
                if m.working else np.nan,
    }).reset_index(drop=True)
    if m.working:
        raw_w = pd.to_numeric(pick(m.working, False), errors="coerce").reset_index(drop=True)
        frame.loc[raw_w.isna(), "v714"] = np.nan
    log.success(f"built {len(frame):,} head-spouse couples from roster")
    return RawDhs(frame=frame, value_labels={"v024": dict(m.region_labels)} if m.region_labels else {},
                  sha256=sha256, source_name=source_name)


def read_roster_file(path: Path) -> tuple[pd.DataFrame, str]:
    if not path.exists():
        raise FileNotFoundError(path)
    suf = path.suffix.lower()
    df = pd.read_stata(path, convert_categoricals=False) if suf == ".dta" else pd.read_csv(path)
    return df, sha256_file(path)


def split_hies_code(code: pd.Series) -> pd.DataFrame:
    """🌸 Decode a 10-digit HIES processing code (PBS coding scheme). NOTE: in the real section files `hhcode`
    is stored as an approximate float and looks 11 digits long, so scripts/build_hies_roster.py builds the
    household id from prcode and hhno instead and does not use this helper.

    digit 1 = province (1 KP, 2 Punjab, 3 Sindh, 4 Balochistan), digits 2-3 = stratum,
    digit 4 = sub-universe (1 rural, 2 urban), digit 5 = quarter, digits 6-8 = PSU within
    stratum, digits 9-10 = household. Returns province, stratum (digits 1-4), psu (digits 1-8),
    household (all 10). Use these as the region/strata/psu/household columns in your RosterMap. ✨
    """
    txt = pd.to_numeric(code, errors="coerce").astype("Int64").astype("string")
    bad = txt.isna() | (txt.str.len() != 10)
    if bad.any():
        log.missing(f"{int(bad.sum()):,} codes are not 10 digits; their rows get NA design columns")
    ok = txt.where(~bad)
    return pd.DataFrame({
        "province": pd.to_numeric(ok.str[0], errors="coerce"),
        "stratum": pd.to_numeric(ok.str[:4], errors="coerce"),
        "psu": pd.to_numeric(ok.str[:8], errors="coerce"),
        "household": pd.to_numeric(ok, errors="coerce"),
        "urban": pd.to_numeric(ok.str[3], errors="coerce").map({1: 0, 2: 1}),
    })
