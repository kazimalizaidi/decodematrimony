"""📉 The analytical lenses: hypergamy, age gaps, marriage timing, workforce trade-offs. 🎀

All inference is survey-weighted with a PSU/strata Rao-Wu bootstrap. Cells smaller
than `min_cell` are skipped and logged (cream), never reported. 🧸
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from .. import logger as log
from ..survey_stats import (F64, SurveyDesign, bootstrap, holm, weighted_auc,
                            weighted_quantile, weighted_spearman)

ALPHA = 0.05
AGE_BANDS = [15, 25, 30, 35, 40, 45, 50, 60, 100]   # wife age bands used for adjustment
LENS4_MIN_AGE = 30   # younger wives are right-truncated: they cannot have married later than their current age
EDU_LABELS = {0: "no_education", 1: "primary", 2: "secondary", 3: "higher"}


@dataclass
class ResultRow:
    metric: str
    group_label: str
    estimate: Optional[float]
    ci_low: Optional[float]
    ci_high: Optional[float]
    p_value: Optional[float]
    n_unweighted: int
    method: str
    notes: str = ""
    p_adjusted: Optional[float] = None

    @property
    def significant(self) -> bool:
        p = self.p_adjusted if self.p_adjusted is not None else self.p_value
        return p is not None and np.isfinite(p) and p < ALPHA


def _nan_none(x: float) -> Optional[float]:
    return None if not np.isfinite(x) else float(x)


def _design(df: pd.DataFrame) -> SurveyDesign:
    return SurveyDesign(df["weight"].to_numpy(np.float64), df["psu"].to_numpy(np.int64), df["strata"].to_numpy(np.int64))


def _col(df: pd.DataFrame, name: str) -> F64:
    return np.asarray(df[name].astype("Float64").to_numpy(dtype=np.float64, na_value=np.nan), dtype=np.float64)


def _share_stat(fl: F64) -> Callable[[F64], float]:
    return lambda w: float(np.sum(w * fl) / np.sum(w))


def _spearman_stat(x: F64, y: F64) -> Callable[[F64], float]:
    return lambda w: weighted_spearman(x, y, w)


def _median_stat(v: F64, m: NDArray[np.bool_]) -> Callable[[F64], float]:
    return lambda w: weighted_quantile(v[m], w[m], 0.5)


def _auc_stat(v: F64, a: NDArray[np.bool_], b: NDArray[np.bool_]) -> Callable[[F64], float]:
    """Centered at 0 (AUC-0.5) so the bootstrap p-value tests 'no stochastic dominance'."""
    return lambda w: weighted_auc(v[a], w[a], v[b], w[b]) - 0.5


def _report(rows: list[ResultRow]) -> None:
    for r in rows:
        log.stat_result(f"{r.metric}[{r.group_label}]", r.estimate if r.estimate is not None else float("nan"),
                        r.p_adjusted if r.p_adjusted is not None else r.p_value, r.significant)


def _spearman_row(df: pd.DataFrame, a: str, b: str, metric: str, n_boot: int, seed: int, note: str, group: str = "all") -> Optional[ResultRow]:
    d = df.dropna(subset=[a, b])
    if len(d) < 50:
        log.missing(f"{metric}: only {len(d)} complete cases, skipped")
        return None
    x, y = _col(d, a), _col(d, b)
    r = bootstrap(_design(d), _spearman_stat(x, y), n_boot, seed)
    return ResultRow(metric, group, _nan_none(r.estimate), _nan_none(r.ci_low), _nan_none(r.ci_high),
                     _nan_none(r.p_value), len(d), "weighted Spearman, Rao-Wu PSU/strata bootstrap", note)


def share_rows(df: pd.DataFrame, flag: pd.Series, by: str, metric: str, min_cell: int, n_boot: int, seed: int) -> list[ResultRow]:
    """✨ Weighted share (flag==1) per group with bootstrap CI."""
    rows: list[ResultRow] = []
    d = df.assign(_flag=flag).dropna(subset=["_flag", by])
    for g, sub in d.groupby(by, observed=True):
        if len(sub) < min_cell:
            log.missing(f"{metric}[{g}]: n={len(sub)} < {min_cell}, suppressed")
            continue
        fl = _col(sub, "_flag")
        r = bootstrap(_design(sub), _share_stat(fl), n_boot, seed, null=0.5)
        rows.append(ResultRow(metric, str(g), _nan_none(r.estimate), _nan_none(r.ci_low), _nan_none(r.ci_high),
                              None, len(sub), "weighted share, Rao-Wu bootstrap CI (descriptive)"))
    return rows


def age_gap_by_education(df: pd.DataFrame, min_cell: int, n_boot: int, seed: int) -> list[ResultRow]:
    """🎀 Weighted median husband-minus-wife age gap per wife-education level, plus
    weighted probability-of-superiority vs 'no_education' (Holm-adjusted)."""
    d = df.dropna(subset=["age_gap", "wife_edu"])
    gap = _col(d, "age_gap")
    edu = _col(d, "wife_edu")
    design = _design(d)
    rows: list[ResultRow] = []
    for lvl, name in EDU_LABELS.items():
        m = edu == lvl
        if m.sum() < min_cell:
            log.missing(f"age_gap_median[{name}]: n={int(m.sum())} < {min_cell}, suppressed")
            continue
        r = bootstrap(design, _median_stat(gap, m), n_boot, seed, null=float("nan"))
        rows.append(ResultRow("age_gap_median_years", name, _nan_none(r.estimate), _nan_none(r.ci_low),
                              _nan_none(r.ci_high), None, int(m.sum()), "weighted median, Rao-Wu bootstrap CI (descriptive)"))
    ref = edu == 0
    contrasts: list[ResultRow] = []
    if ref.sum() >= min_cell:
        for lvl, name in EDU_LABELS.items():
            m = edu == lvl
            if lvl == 0 or m.sum() < min_cell:
                continue
            r = bootstrap(design, _auc_stat(gap, m, ref), n_boot, seed)
            contrasts.append(ResultRow("age_gap_superiority_vs_no_education", name, _nan_none(r.estimate + 0.5),
                                       _nan_none(r.ci_low + 0.5), _nan_none(r.ci_high + 0.5), _nan_none(r.p_value),
                                       int(m.sum()), "weighted Mann-Whitney effect P(X>Y), bootstrap p vs 0.5, Holm",
                                       "estimate<0.5 means smaller gaps than uneducated wives"))
    valid = [c for c in contrasts if c.p_value is not None]
    for c, a in zip(valid, holm([c.p_value for c in valid if c.p_value is not None])):
        c.p_adjusted = a
    return rows + contrasts


def _stratified_auc_stat(
    gap: F64, edu: F64, cells: list[NDArray[np.int64]], level: int, min_side: int = 5
) -> Callable[[F64], float]:
    """Stratified weighted Mann-Whitney effect (minus 0.5): within each age-band x region cell compare
    `level` wives with uneducated wives, then pool cells with weight W_x * W_y (van Elteren-style)."""
    def stat(w: F64) -> float:
        num = den = 0.0
        for idx in cells:
            x, y = idx[edu[idx] == level], idx[edu[idx] == 0]
            if x.size < min_side or y.size < min_side:
                continue
            wx, wy = float(w[x].sum()), float(w[y].sum())
            if wx <= 0 or wy <= 0:
                continue
            num += wx * wy * weighted_auc(gap[x], w[x], gap[y], w[y])
            den += wx * wy
        return num / den - 0.5 if den > 0 else float("nan")
    return stat


def age_gap_adjusted_by_education(df: pd.DataFrame, min_cell: int, n_boot: int, seed: int) -> list[ResultRow]:
    """🎀 Age-gap contrast vs uneducated wives, ADJUSTED for wife age band x region (stratified)."""
    d = df.dropna(subset=["age_gap", "wife_edu", "wife_age", "region"]).reset_index(drop=True)
    band = pd.cut(d["wife_age"].astype("float64"), AGE_BANDS, right=False, labels=False).astype("float64")
    d = d[band.notna()].reset_index(drop=True)
    band = band[band.notna()].reset_index(drop=True)
    code = (band.astype("int64") * 100 + pd.factorize(d["region"])[0]).to_numpy(np.int64)
    cells = [np.flatnonzero(code == c) for c in np.unique(code)]
    gap, edu, design = _col(d, "age_gap"), _col(d, "wife_edu"), _design(d)
    rows: list[ResultRow] = []
    for lvl, name in EDU_LABELS.items():
        n = int((edu == lvl).sum())
        if lvl == 0 or n < min_cell:
            continue
        r = bootstrap(design, _stratified_auc_stat(gap, edu, cells, lvl), n_boot, seed)
        rows.append(ResultRow("age_gap_superiority_vs_no_education_adjusted", name, _nan_none(r.estimate + 0.5),
                              _nan_none(r.ci_low + 0.5), _nan_none(r.ci_high + 0.5), _nan_none(r.p_value), n,
                              "stratified weighted Mann-Whitney effect (wife age band x region), bootstrap p vs 0.5, Holm",
                              "adjusted for wife age band and region; estimate<0.5 = smaller gaps than uneducated wives"))
    valid = [c for c in rows if c.p_value is not None]
    for c, a in zip(valid, holm([c.p_value for c in valid if c.p_value is not None])):
        c.p_adjusted = a
    return rows


def gap_summaries_by_education(df: pd.DataFrame, min_cell: int, n_boot: int, seed: int) -> list[ResultRow]:
    """✨ Weighted mean age gap and share of couples with a gap of 10+ years, by wife education."""
    d = df.dropna(subset=["age_gap", "wife_edu"]).copy()
    d["wife_edu_label"] = d["wife_edu"].astype("Int64").map(EDU_LABELS)
    big = (d["age_gap"].astype("Float64") >= 10).astype("Float64")
    rows = share_rows(d, big, "wife_edu_label", "share_age_gap_10plus", min_cell, n_boot, seed)
    gap, edu, design = _col(d, "age_gap"), _col(d, "wife_edu"), _design(d)
    from ..survey_stats import weighted_mean
    for lvl, name in EDU_LABELS.items():
        m = edu == lvl
        if m.sum() < min_cell:
            continue
        r = bootstrap(design, lambda w, m=m: weighted_mean(gap[m], w[m]), n_boot, seed, null=float("nan"))  # type: ignore[misc]
        rows.append(ResultRow("age_gap_mean_years", name, _nan_none(r.estimate), _nan_none(r.ci_low), _nan_none(r.ci_high),
                              None, int(m.sum()), "weighted mean, Rao-Wu bootstrap CI (descriptive)"))
    return rows


def run_all(couples: pd.DataFrame, n_boot: int, seed: int, min_cell: int) -> list[ResultRow]:
    """💗 Execute every lens. Optional lenses are skipped with a cream log when data are structurally missing."""
    df = couples.copy()
    rows: list[ResultRow] = []
    log.milestone("lens 1/6: age gap by wife education (weighted medians + Holm-adjusted contrasts)")
    rows += age_gap_by_education(df, min_cell, n_boot, seed)
    log.milestone("lens 1b/6: same contrast adjusted for wife age band x region (stratified)")
    rows += age_gap_adjusted_by_education(df, min_cell, n_boot, seed)
    log.milestone("lens 1c/6: weighted mean age gap and share of gaps of 10+ years by wife education")
    rows += gap_summaries_by_education(df, min_cell, n_boot, seed)

    log.milestone("lens 2/6: wealth gradient of the age gap (weighted Spearman)")
    r = _spearman_row(df, "wealth_quintile", "age_gap", "spearman_wealth_vs_age_gap", n_boot, seed,
                      "household wealth quintile vs husband-minus-wife age gap")
    if r:
        rows.append(r)
        hyp = (df["edu_pairing"].astype("string") == "hypergamous").astype("Float64").where(df["edu_pairing"].notna())
        rows += share_rows(df, hyp, "wealth_quintile", "share_hypergamous_by_wealth_quintile", min_cell, n_boot, seed)
        hom = (df["edu_pairing"].astype("string") == "homogamous").astype("Float64").where(df["edu_pairing"].notna())
        rows += share_rows(df, hom, "wealth_quintile", "share_homogamous_by_wealth_quintile", min_cell, n_boot, seed)
        big = (df["age_gap"].astype("Float64") >= 10).astype("Float64")
        rows += share_rows(df, big, "wealth_quintile", "share_age_gap_10plus_by_wealth_quintile", min_cell, n_boot, seed)

    log.milestone("lens 3/6: educational hypergamy / homogamy / hypogamy by region")
    for lab in ("hypergamous", "homogamous", "hypogamous"):
        flag = (df["edu_pairing"].astype("string") == lab).astype("Float64").where(df["edu_pairing"].notna())
        rows += share_rows(df, flag, "region", f"share_{lab}", min_cell, n_boot, seed)

    log.milestone(f"lens 4/6: marriage-timing cohort gradient (wives aged {LENS4_MIN_AGE}+ to avoid truncation)")
    r = _spearman_row(df[df["wife_age"] >= LENS4_MIN_AGE], "wife_age", "wife_age_first_union",
                      "spearman_wife_age_vs_age_at_first_union", n_boot, seed,
                      f"cross-sectional cohort gradient among wives aged {LENS4_MIN_AGE}+ (younger wives are right-truncated); "
                      "NOT a longitudinal attrition curve", group=f"wife_age_{LENS4_MIN_AGE}plus")
    if r:
        rows.append(r)

    log.milestone("lens 5/6: female workforce participation vs age gap")
    d = df.dropna(subset=["wife_working", "age_gap"])
    if len(d) >= 2 * min_cell and d["wife_working"].nunique() == 2:
        g, wk = _col(d, "age_gap"), _col(d, "wife_working") == 1
        res = bootstrap(_design(d), _auc_stat(g, wk, ~wk), n_boot, seed)
        rows.append(ResultRow("age_gap_superiority_working_vs_not", "wife_working", _nan_none(res.estimate + 0.5),
                              _nan_none(res.ci_low + 0.5), _nan_none(res.ci_high + 0.5), _nan_none(res.p_value),
                              len(d), "weighted Mann-Whitney effect P(X>Y), bootstrap p vs 0.5"))
        flag = df["wife_working"].astype("Float64")
        rows += share_rows(df, flag, "edu_pairing", "share_wife_working", min_cell, n_boot, seed)
    else:
        log.missing("workforce lens skipped: wife_working too sparse or single-valued")

    log.milestone("lens 6/6: ethnic endogamy (inelasticity proxy; DHS has no sect/caste)")
    e = df.dropna(subset=["wife_ethnicity", "husband_ethnicity"])
    if len(e) >= min_cell:
        flag = (e["wife_ethnicity"] == e["husband_ethnicity"]).astype("Float64")
        rows += share_rows(e.assign(all_couples="all"), flag, "all_couples", "share_ethnic_endogamy", min_cell, n_boot, seed)
    else:
        log.missing("ethnicity lens skipped: ethnicity columns absent (structural missingness)")
    _report(rows)
    return rows


def to_frame(rows: list[ResultRow]) -> pd.DataFrame:
    return pd.DataFrame([{**{k: getattr(r, k) for k in ("metric", "group_label", "estimate", "ci_low", "ci_high",
                                                       "p_value", "p_adjusted", "n_unweighted", "method", "notes")},
                          "significant": int(r.significant)} for r in rows])
