import pandas as pd
import pytest
from decodematrimony.db import _ident, build_merge_sql
from decodematrimony.macro import build_mahr_benchmark
from decodematrimony.textnorm import normalise_label


def test_merge_sql_shape():
    sql = build_merge_sql("core", "couples", "couples_stage", ["couple_id"], ["couple_id", "weight"])
    assert "MERGE core.couples" in sql and "WHEN MATCHED" in sql and "INSERT (couple_id, weight)" in sql


def test_identifier_guard():
    with pytest.raises(ValueError):
        _ident("x; DROP TABLE y")


def test_mahr_benchmark_indexing():
    m = pd.to_datetime(["2020-01-01", "2021-01-01"])
    gold = pd.DataFrame({"obs_date": m, "value": [100.0, 150.0]})
    cpi = pd.DataFrame({"obs_date": m, "value": [200.0, 220.0]})
    b = build_mahr_benchmark(gold, cpi, "2020-01")
    assert b.loc[0, "gold_index"] == 100 and b.loc[1, "gold_index"] == 150
    assert abs(b.loc[1, "gold_to_cpi_ratio"] - 150 / 110 * 100) < 1e-9
    assert abs(b.loc[1, "real_value_fixed_pkr"] - 10000 / 110) < 1e-9


def test_mahr_missing_base_raises():
    m = pd.to_datetime(["2020-01-01"])
    d = pd.DataFrame({"obs_date": m, "value": [1.0]})
    with pytest.raises(ValueError):
        build_mahr_benchmark(d, d, "2019-01")


def test_label_normalisation():
    assert normalise_label("KPK/NWFP ") == "khyber pakhtunkhwa"
    assert normalise_label("  Punjab ") == "punjab"


def test_inspect_flags_missing_columns(tmp_path, raw_frame):
    from decodematrimony.inspect_dhs import inspect
    from decodematrimony.settings import DhsVariableMap
    f = tmp_path / "x.dta"
    raw_frame.drop(columns=["v714"]).to_stata(f, write_index=False)
    assert inspect(f, DhsVariableMap()) == ["v714"]
