import numpy as np
import pandas as pd
from decodematrimony.analysis.lenses import run_all
from decodematrimony.clean import clean_couples
from decodematrimony.ingest.dhs import RawDhs
from decodematrimony.settings import DhsVariableMap


def _raw(df: pd.DataFrame) -> RawDhs:
    return RawDhs(df, {"v024": {1: "Punjab", 2: "Sindh", 3: "KPK", 4: "Balochistan"}}, "x", "fixture")


def test_clean_handles_missing_codes_and_gap(raw_frame):
    df = raw_frame.copy()
    df.loc[0, "v106"] = 9           # DHS missing code
    df.loc[1, "mv012"] = 150        # out of range
    df.loc[2, "v021"] = np.nan      # no PSU -> dropped
    res = clean_couples(_raw(df), DhsVariableMap(), 2017)
    c = res.couples
    assert res.dropped_rows == 1 and len(c) == len(df) - 1
    assert pd.isna(c.loc[0, "wife_edu"]) and pd.isna(c.loc[1, "age_gap"])
    ok = c["age_gap"].notna()
    assert ((c["husband_age"] - c["wife_age"])[ok] == c["age_gap"][ok]).all()
    assert c["weight"].between(0.3, 2.5).all()
    assert c["region"].dropna().isin({"punjab", "sindh", "khyber pakhtunkhwa", "balochistan"}).all()
    assert c["wife_ethnicity"].isna().all()  # structural missingness preserved


def test_pairing_logic(raw_frame):
    df = raw_frame.head(3).copy()
    df["v106"], df["mv106"] = [1, 2, 3], [2, 2, 1]
    c = clean_couples(_raw(df), DhsVariableMap(), 2017).couples
    assert list(c["edu_pairing"]) == ["hypergamous", "homogamous", "hypogamous"]


def test_lenses_recover_planted_structure(raw_frame):
    c = clean_couples(_raw(raw_frame), DhsVariableMap(), 2017).couples
    rows = run_all(c, n_boot=60, seed=11, min_cell=30)
    gradient = [r for r in rows if r.metric == "age_gap_superiority_vs_no_education" and r.group_label == "higher"][0]
    assert gradient.estimate is not None and gradient.estimate < 0.2 and gradient.significant
    timing = [r for r in rows if r.metric == "spearman_wife_age_vs_age_at_first_union"][0]
    assert timing.estimate is not None and timing.estimate < -0.3
    assert not any(r.metric == "share_ethnic_endogamy" for r in rows)


def test_truncation_artifact_is_removed_by_age_restriction():
    """🧸 SYNTHETIC: age at first union independent of cohort, but capped by current age."""
    from decodematrimony.analysis.lenses import LENS4_MIN_AGE, _spearman_row
    rng = np.random.default_rng(9)
    n = 4000
    age = rng.integers(18, 50, n)
    afm = np.minimum(rng.integers(14, 28, n), age)
    df = pd.DataFrame({"weight": rng.uniform(0.5, 2, n), "psu": rng.integers(1, 40, n),
                       "strata": rng.integers(1, 4, n), "wife_age": age, "wife_age_first_union": afm})
    naive = _spearman_row(df, "wife_age", "wife_age_first_union", "m", 30, 1, "")
    fixed = _spearman_row(df[df["wife_age"] >= LENS4_MIN_AGE], "wife_age", "wife_age_first_union", "m", 30, 1, "")
    assert naive is not None and fixed is not None
    assert naive.estimate is not None and fixed.estimate is not None
    assert naive.estimate > 0.10 and abs(fixed.estimate) < 0.05


def test_adjustment_removes_age_confounding():
    """🧸 SYNTHETIC unit test: gap depends only on wife age; education depends on age. Unadjusted looks like an
    education effect, adjusted must not."""
    from decodematrimony.analysis.lenses import age_gap_adjusted_by_education, age_gap_by_education
    rng = np.random.default_rng(5)
    n = 6000
    age = rng.integers(18, 60, n)
    edu = np.where(rng.random(n) < np.clip((60 - age) / 60, 0.05, 0.95), rng.integers(1, 4, n), 0)
    gap = (age // 10) * 2 + rng.integers(-2, 3, n)
    df = pd.DataFrame({"weight": rng.uniform(0.5, 2, n), "psu": rng.integers(1, 60, n), "strata": rng.integers(1, 4, n),
                       "wife_age": age, "wife_edu": edu, "age_gap": gap, "region": rng.choice(["a", "b"], n)})
    raw = [r for r in age_gap_by_education(df, 30, 40, 1) if r.metric == "age_gap_superiority_vs_no_education" and r.group_label == "higher"][0]
    adj = [r for r in age_gap_adjusted_by_education(df, 30, 40, 1) if r.group_label == "higher"][0]
    assert raw.estimate is not None and adj.estimate is not None
    assert raw.estimate < 0.45 and 0.47 < adj.estimate < 0.53
