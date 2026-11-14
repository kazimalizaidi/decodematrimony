"""🧸 SYNTHETIC roster fixture, unit tests only."""
import numpy as np
import pandas as pd
import pytest
from decodematrimony.analysis.lenses import run_all
from decodematrimony.clean import clean_couples
from decodematrimony.ingest.roster import RosterMap, couples_from_roster
from decodematrimony.settings import DhsVariableMap

M = RosterMap("hh", "line", "rel", "sex", "age", "edu", "wt", "psu", "strata", "prov",
              head_code=1, spouse_code=2, male_code=1, female_code=2,
              edu_recode={0: 0, 1: 1, 2: 2, 3: 3, 4: 3}, working="work")


def _roster(n=900, seed=3):
    rng = np.random.default_rng(seed)
    rows = []
    for h in range(n):
        strata = int(rng.integers(1, 5)); psu = strata * 100 + int(rng.integers(1, 10))
        male_head = rng.random() < 0.9
        wedu = int(rng.integers(0, 4)); gap = int(round(8 - 2 * wedu + rng.normal(0, 3)))
        wage = int(rng.integers(20, 55))
        common = dict(hh=h, wt=float(rng.uniform(100, 900)), psu=psu, strata=strata, prov=int(rng.integers(1, 5)))
        hs = (1, 1 if male_head else 2); ss = (2, 2 if male_head else 1)
        w_age, h_age = wage, wage + gap
        rows.append({**common, "line": 1, "rel": 1, "sex": hs[1], "age": h_age if male_head else w_age, "edu": min(wedu + 1, 4) if male_head else wedu, "work": 0})
        rows.append({**common, "line": 2, "rel": 2, "sex": ss[1], "age": w_age if male_head else h_age, "edu": wedu if male_head else min(wedu + 1, 4), "work": int(rng.integers(0, 2)) if male_head else 0})
        if h % 50 == 0:
            rows.append({**common, "line": 3, "rel": 2, "sex": 2, "age": 30, "edu": 1, "work": 0})  # polygyny -> dropped
    return pd.DataFrame(rows)


def test_roster_to_couples_and_lenses():
    raw = couples_from_roster(_roster(), M, "fixture")
    assert raw.frame["v511"].isna().all()
    c = clean_couples(raw, DhsVariableMap(), 2024).couples
    assert len(c) > 700 and c["wife_edu"].isin([0, 1, 2, 3]).all()
    rows = run_all(c, n_boot=40, seed=5, min_cell=30)
    assert not any(r.metric.startswith("spearman_wife_age_vs_age_at_first_union") for r in rows)  # skipped
    g = [r for r in rows if r.metric == "age_gap_superiority_vs_no_education" and r.group_label == "higher"][0]
    assert g.estimate is not None and g.estimate < 0.25


def test_missing_column_raises():
    with pytest.raises(KeyError):
        couples_from_roster(_roster().drop(columns=["age"]), M, "x")


def test_pipeline_roster_end_to_end(tmp_path, monkeypatch):
    import json
    from decodematrimony.pipeline import main
    _roster().to_csv(tmp_path / "r.csv", index=False)
    mp = {k: v for k, v in M.__dict__.items()}
    mp["edu_recode"] = {str(k): v for k, v in M.edu_recode.items()}
    (tmp_path / "map.json").write_text(json.dumps(mp))
    monkeypatch.setenv("DM_N_BOOT", "40")
    monkeypatch.setenv("DM_OUT_DIR", str(tmp_path / "out"))
    assert main(["--roster", str(tmp_path / "r.csv"), "--roster-map", str(tmp_path / "map.json"), "--year", "2024", "--no-db"]) == 0
    assert (tmp_path / "out" / "results.csv").exists()


def test_split_hies_code():
    import pandas as pd
    from decodematrimony.ingest.roster import split_hies_code
    d = split_hies_code(pd.Series([2112101701, 3011204305, 12345]))
    assert (d.loc[0, "province"], d.loc[0, "stratum"], d.loc[0, "psu"], d.loc[0, "urban"]) == (2, 2112, 21121017, 1)
    assert d.loc[1, "province"] == 3 and d.loc[1, "urban"] == 0 and d.loc[1, "household"] == 3011204305
    assert pd.isna(d.loc[2, "psu"])


def test_marital_filter_and_labels():
    r = _roster()
    r["ms"] = 2
    r.loc[(r["hh"] < 100) & (r["rel"] == 2), "ms"] = 6   # nikkah without rukhsati -> dropped
    m = RosterMap(**{**M.__dict__, "marital_status": "ms", "region_labels": {1: "punjab", 2: "sindh", 3: "kpk", 4: "balochistan"}})
    raw = couples_from_roster(r, m, "x")
    assert (raw.frame["caseid"].astype(int) >= 100).all()
    c = clean_couples(raw, DhsVariableMap(), 2024).couples
    assert c["region"].dropna().isin({"punjab", "sindh", "khyber pakhtunkhwa", "balochistan"}).all()


def test_age_at_first_union_flows_through():
    import numpy as np
    r = _roster()
    r["afm"] = np.clip(15 + 0.15 * (50 - r["age"]), 10, 40).round()
    m = RosterMap(**{**M.__dict__, "wife_age_first_union": "afm"})
    raw = couples_from_roster(r, m, "x")
    assert raw.frame["v511"].notna().all()
    c = clean_couples(raw, DhsVariableMap(), 2024).couples
    rows = run_all(c, n_boot=40, seed=5, min_cell=30)
    assert any(x.metric == "spearman_wife_age_vs_age_at_first_union" for x in rows)
