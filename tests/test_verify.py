"""🧸 SYNTHETIC unit test for the SQL-vs-Python comparison helper (no database needed)."""
import pandas as pd
from decodematrimony.db import stage_dtypes
from decodematrimony.verify import compare_estimates


def test_compare_estimates_flags_mismatch():
    res = pd.DataFrame({"metric": ["share_hypergamous"] * 2, "group_label": ["punjab", "sindh"], "estimate": [0.40, 0.50]})
    sql = pd.DataFrame({"grp": ["punjab", "sindh", "other"], "value": [0.40, 0.51, 0.1]})
    out = compare_estimates(sql, res, "share_hypergamous")
    assert [(g, ok) for g, _, _, ok in out] == [("punjab", True), ("sindh", False)]


def test_stage_dtypes_only_text_columns():
    df = pd.DataFrame({"a": ["x", None], "b": [1, None], "c": [None, None]}).astype(object)
    assert list(stage_dtypes(df)) == ["a"]
