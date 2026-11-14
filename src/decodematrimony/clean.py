"""✨ Raw DHS -> validated couple-level table, with an explicit missingness report. 🧸

Rules (all documented, none silent):
  * weights = v005 / 1e6 (DHS convention); rows without weight/PSU/strata are dropped
  * DHS "don't know/missing" codes are converted to <NA>; out-of-range values -> <NA> + logged
  * edu pairing compares husband vs wife education level (0 none .. 3 higher)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from . import logger as log
from .ingest.dhs import RawDhs
from .settings import DhsVariableMap
from .textnorm import normalise_label

AGE_RANGE = (15, 99)
EDU_VALID = {0, 1, 2, 3}
WEALTH_VALID = {1, 2, 3, 4, 5}


@dataclass(frozen=True)
class CleanResult:
    couples: pd.DataFrame
    missingness: pd.DataFrame
    dropped_rows: int


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype("Float64")


def _restrict(s: pd.Series, valid: set[int], name: str) -> pd.Series:
    out = _num(s)
    bad = out.notna() & ~out.isin(list(valid))
    if bad.any():
        log.missing(f"{name}: {int(bad.sum()):,} out-of-domain codes -> NA")
    return out.mask(bad)


def _range(s: pd.Series, lo: int, hi: int, name: str) -> pd.Series:
    out = _num(s)
    bad = out.notna() & ((out < lo) | (out > hi))
    if bad.any():
        log.missing(f"{name}: {int(bad.sum()):,} out-of-range values -> NA")
    return out.mask(bad)


def _label(raw: RawDhs, col: Optional[str], series: pd.Series) -> pd.Series:
    if col is None:
        return pd.Series(pd.NA, index=series.index, dtype="string")
    lab = raw.value_labels.get(col, {})
    codes = pd.to_numeric(series, errors="coerce")
    mapped = codes.map(lambda c: pd.NA if pd.isna(c) else normalise_label(lab.get(int(c), str(int(c)))))
    return mapped.astype("string")


def clean_couples(raw: RawDhs, vmap: DhsVariableMap, survey_year: int) -> CleanResult:
    """💗 Build core.couples-shaped frame. Raises if nothing survives validation."""
    f = raw.frame
    w = _num(f[vmap.weight]) / 1_000_000.0
    psu, strata = _num(f[vmap.psu]), _num(f[vmap.strata])
    ok = w.notna() & (w > 0) & psu.notna() & strata.notna()
    dropped = int((~ok).sum())
    if dropped:
        log.missing(f"dropped {dropped:,} rows lacking weight/PSU/strata")
    f, w, psu, strata = f[ok], w[ok], psu[ok], strata[ok]

    wage = _range(f[vmap.wife_age], *AGE_RANGE, "wife_age")
    hage = _range(f[vmap.husband_age], *AGE_RANGE, "husband_age")
    wedu = _restrict(f[vmap.wife_edu], EDU_VALID, "wife_edu")
    hedu = _restrict(f[vmap.husband_edu], EDU_VALID, "husband_edu")
    gap = (hage - wage).astype("Float64")
    gap = gap.mask((gap < -40) | (gap > 60))
    pairing = pd.Series(pd.NA, index=f.index, dtype="string")
    both = wedu.notna() & hedu.notna()
    pairing = pairing.mask(both & (hedu > wedu), "hypergamous").mask(both & (hedu == wedu), "homogamous").mask(
        both & (hedu < wedu), "hypogamous")
    work = _num(f[vmap.wife_working])
    work = work.where(work.isin([0, 1]), pd.NA) if work.notna().any() else work
    afu = _range(f[vmap.wife_age_first_union], 8, 60, "wife_age_first_union")

    out = pd.DataFrame({
        "couple_id": f[vmap.case_id].astype("string").str.strip() + "|" + str(survey_year),
        "survey_year": np.int16(survey_year),
        "weight": w.astype("float64"),
        "psu": psu.astype("Int64"),
        "strata": strata.astype("Int64"),
        "wife_age": wage.astype("Int64"),
        "husband_age": hage.astype("Int64"),
        "age_gap": gap.astype("Int64"),
        "wife_edu": wedu.astype("Int64"),
        "husband_edu": hedu.astype("Int64"),
        "edu_pairing": pairing,
        "wealth_quintile": _restrict(f[vmap.wealth], WEALTH_VALID, "wealth").astype("Int64"),
        "region": _label(raw, vmap.region, f[vmap.region]),
        "wife_age_first_union": afu.astype("Int64"),
        "wife_working": work.astype("Int64"),
        "wife_ethnicity": _label(raw, vmap.wife_ethnicity, f[vmap.wife_ethnicity]) if vmap.wife_ethnicity and vmap.wife_ethnicity in f else _label(raw, None, f[vmap.case_id]),
        "husband_ethnicity": _label(raw, vmap.husband_ethnicity, f[vmap.husband_ethnicity]) if vmap.husband_ethnicity and vmap.husband_ethnicity in f else _label(raw, None, f[vmap.case_id]),
    }).reset_index(drop=True)

    if out["couple_id"].duplicated().any():
        log.failure("duplicate couple_id values detected")
        raise ValueError("duplicate couple_id after cleaning")
    if out.empty:
        raise ValueError("no couples survived validation")

    miss = out.isna().mean().rename("share_missing").reset_index().rename(columns={"index": "column"})
    for _, r in miss[miss["share_missing"] > 0].iterrows():
        log.missing(f"missingness {r['column']}: {r['share_missing']:.1%}")
    log.success(f"cleaned {len(out):,} couples")
    return CleanResult(couples=out, missingness=miss, dropped_rows=dropped)
