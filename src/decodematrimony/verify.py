"""✨ Post-load verification for SQL Server: counts, constraints, and SQL-vs-Python estimate cross-checks. 🎀"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from . import logger as log

EDU = {0: "no_education", 1: "primary", 2: "secondary", 3: "higher"}


def compare_estimates(sql_df: pd.DataFrame, results: pd.DataFrame, metric: str, tol: float = 1e-6) -> list[tuple[str, float, float, bool]]:
    """Compare a SQL-computed estimate (columns grp, value) with the Python pipeline's estimate for `metric`."""
    py = results[results["metric"] == metric].set_index("group_label")["estimate"]
    out: list[tuple[str, float, float, bool]] = []
    for _, r in sql_df.iterrows():
        g = str(r["grp"])
        if g in py.index:
            a, b = float(r["value"]), float(py[g])
            out.append((g, a, b, abs(a - b) <= tol))
    return out


def table_counts(engine: Engine) -> dict[str, int]:
    qs = {
        "core.couples": "SELECT COUNT(*) FROM core.couples",
        "ana.results (all runs)": "SELECT COUNT(*) FROM ana.results",
        "ana.vw_latest_results": "SELECT COUNT(*) FROM ana.vw_latest_results",
        "ana.mahr_benchmark": "SELECT COUNT(*) FROM ana.mahr_benchmark",
        "ops.run_log SUCCESS": "SELECT COUNT(*) FROM ops.run_log WHERE status='SUCCESS'",
        "ops.run_log FAILED": "SELECT COUNT(*) FROM ops.run_log WHERE status='FAILED'",
        "ops.data_lineage": "SELECT COUNT(*) FROM ops.data_lineage",
    }
    with engine.connect() as conn:
        return {k: int(conn.execute(text(q)).scalar_one()) for k, q in qs.items()}


def run_checks(engine: Engine, results_csv: Optional[Path] = None, expect_couples: Optional[int] = None) -> bool:
    ok = True
    log.milestone("table counts")
    counts = table_counts(engine)
    for k, v in counts.items():
        log.success(f"{k}: {v:,}")
    if expect_couples is not None:
        good = counts["core.couples"] == expect_couples
        ok &= good
        (log.success if good else log.failure)(f"core.couples == {expect_couples:,}: {good}")

    log.milestone("integrity checks")
    with engine.connect() as conn:
        bad_w = int(conn.execute(text("SELECT COUNT(*) FROM core.couples WHERE weight <= 0")).scalar_one())
        orphan = int(conn.execute(text(
            "SELECT COUNT(*) FROM ana.results r LEFT JOIN ops.run_log l ON l.run_id = r.run_id WHERE l.run_id IS NULL")).scalar_one())
        latest = int(conn.execute(text(
            "SELECT COUNT(*) FROM ana.results WHERE run_id = (SELECT TOP 1 run_id FROM ops.run_log WHERE status='SUCCESS' ORDER BY finished_at DESC)")).scalar_one())
    for name, good in (("no non-positive weights", bad_w == 0), ("no orphan results", orphan == 0),
                       ("view matches latest successful run", latest == counts["ana.vw_latest_results"])):
        ok &= good
        (log.success if good else log.failure)(f"{name}: {good}")

    log.milestone("constraint test (a bad row must be rejected and rolled back)")
    rejected = False
    with engine.connect() as conn:
        try:
            conn.execute(text("INSERT INTO core.couples (couple_id, survey_year, weight, psu, strata, wife_age) "
                              "VALUES ('__constraint_test__', 2024, 1.0, 1, 1, 5)"))
        except DBAPIError:
            rejected = True
        finally:
            conn.rollback()
    ok &= rejected
    (log.success if rejected else log.failure)(f"CHECK constraint rejected wife_age=5: {rejected}")

    if results_csv is not None and results_csv.exists():
        log.milestone("SQL vs Python cross-check (weighted estimates must agree)")
        res = pd.read_csv(results_csv)
        with engine.connect() as conn:
            hyper = pd.read_sql(text(
                "SELECT region AS grp, SUM(CASE WHEN edu_pairing='hypergamous' THEN weight ELSE 0 END) / "
                "SUM(CASE WHEN edu_pairing IS NOT NULL THEN weight ELSE 0 END) AS value "
                "FROM core.couples WHERE region IS NOT NULL GROUP BY region"), conn)
            gap = pd.read_sql(text(
                "SELECT wife_edu AS grp, SUM(weight * age_gap) / SUM(weight) AS value FROM core.couples "
                "WHERE age_gap IS NOT NULL AND wife_edu IS NOT NULL GROUP BY wife_edu"), conn)
        gap["grp"] = gap["grp"].map(lambda g: EDU[int(g)])
        for metric, frame in (("share_hypergamous", hyper), ("age_gap_mean_years", gap)):
            cmp = compare_estimates(frame, res, metric)
            if not cmp:
                log.missing(f"{metric}: nothing to compare")
                continue
            for g, a, b, good in cmp:
                ok &= good
                (log.success if good else log.failure)(f"{metric}[{g}] SQL={a:.6f} Python={b:.6f} match={good}")
    return ok
