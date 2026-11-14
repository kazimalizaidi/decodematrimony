"""🎀 End-to-end orchestrator: ingest -> clean -> (SQL Server) -> analyse -> report. ✨

  python -m decodematrimony.pipeline --dhs data/raw/PKCR*.DTA --year 2017 [--no-db]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

import pandas as pd

from . import logger as log
from .analysis.lenses import ResultRow, run_all, to_frame
from .clean import clean_couples
from .ingest.dhs import RawDhs, read_dhs_couples
from .ingest.roster import RosterMap, couples_from_roster, read_roster_file
from .macro import build_mahr_benchmark, load_series
from .settings import DhsVariableMap, Settings


def main(argv: Optional[Sequence[str]] = None) -> int:
    log.install_excepthook()
    ap = argparse.ArgumentParser(description="🎀 DecodeMatrimony pipeline")
    ap.add_argument("--dhs", type=Path, default=None, help="DHS Couples' Recode (.dta or .csv)")
    ap.add_argument("--roster", type=Path, default=None, help="household roster file (.dta/.csv), e.g. merged HIES sections")
    ap.add_argument("--roster-map", type=Path, default=None, help="JSON RosterMap with your verified column names/codes")
    ap.add_argument("--year", type=int, required=True, help="survey year, e.g. 2017")
    ap.add_argument("--varmap", type=Path, default=None, help="JSON override for DHS variable names")
    ap.add_argument("--gold-csv", type=Path, default=None)
    ap.add_argument("--gold-cols", nargs=2, default=["date", "pkr_per_tola"])
    ap.add_argument("--cpi-csv", type=Path, default=None)
    ap.add_argument("--cpi-cols", nargs=2, default=["date", "cpi"])
    ap.add_argument("--base-month", default=None, help="YYYY-MM month indexed to 100 for the Mahr benchmark")
    ap.add_argument("--no-db", action="store_true", help="skip SQL Server (results still written to out/)")
    a = ap.parse_args(argv)

    cfg = Settings.from_env()
    vmap = DhsVariableMap.from_json(a.varmap) if a.varmap else DhsVariableMap()
    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    log.milestone("DecodeMatrimony pipeline starting 🎀")

    src_path = a.dhs if a.dhs is not None else a.roster
    if src_path is not None and (
        {"tests", "fixtures"} & {part.lower() for part in src_path.parts}
        or any(w in src_path.name.lower() for w in ("synthetic", "simulated", "fake", "dummy"))
    ):
        log.failure(f"refusing {src_path}: this pipeline only runs on real survey files, never synthetic data")
        return 2
    if (a.dhs is None) == (a.roster is None):
        log.failure("provide exactly one of --dhs or --roster")
        return 2
    raw: RawDhs
    if a.roster is not None:
        if a.roster_map is None:
            log.failure("--roster needs --roster-map")
            return 2
        df, digest = read_roster_file(a.roster)
        raw = couples_from_roster(df, RosterMap.from_json(a.roster_map), a.roster.name, digest)
    else:
        assert a.dhs is not None
        raw = read_dhs_couples(a.dhs, vmap)
    cleaned = clean_couples(raw, vmap, a.year)
    cleaned.missingness.to_csv(cfg.out_dir / "missingness_report.csv", index=False)

    bench: Optional[pd.DataFrame] = None
    if a.gold_csv and a.cpi_csv and a.base_month:
        bench = build_mahr_benchmark(load_series(a.gold_csv, *a.gold_cols), load_series(a.cpi_csv, *a.cpi_cols), a.base_month)
        bench.to_csv(cfg.out_dir / "mahr_benchmark.csv", index=False)
        log.success(f"built DERIVED Mahr benchmark: {len(bench)} months (written to out/mahr_benchmark.csv)")
    else:
        log.missing("Mahr benchmark skipped (needs --gold-csv, --cpi-csv, --base-month)")

    engine = None
    run_id = None
    if not a.no_db:
        from . import db
        if not cfg.db_url:
            log.failure("DM_DB_URL not set (use --no-db to run without SQL Server)")
            return 2
        engine = db.make_engine(cfg.db_url)
        db.apply_migrations(engine, Path(__file__).resolve().parents[2] / "sql")
        run_id = db.start_run(engine, cfg.n_boot, cfg.seed)
    try:
        if engine is not None:
            from . import db
            db.merge_dataframe(engine, cleaned.couples, "core", "couples", ["couple_id"])
            db.record_lineage(engine, raw.source_name, raw.sha256, len(raw.frame))
            if bench is not None:
                db.merge_dataframe(engine, bench, "ana", "mahr_benchmark", ["obs_date"])
        rows: list[ResultRow] = run_all(cleaned.couples, cfg.n_boot, cfg.seed, cfg.min_cell)
        res = to_frame(rows)
        res.to_csv(cfg.out_dir / "results.csv", index=False)
        (cfg.out_dir / "run_summary.json").write_text(json.dumps({
            "n_couples": int(len(cleaned.couples)), "n_boot": cfg.n_boot, "seed": cfg.seed, "source_name": raw.source_name,
            "source_sha256": raw.sha256, "n_results": len(rows), "n_significant": int(res["significant"].sum())}, indent=1), encoding="utf-8")
        if engine is not None and run_id is not None:
            from . import db
            db.merge_dataframe(engine, res.assign(run_id=str(run_id)), "ana", "results", ["run_id", "metric", "group_label"])
            db.finish_run(engine, run_id, True, f"{len(rows)} results")
        log.success(f"pipeline complete: {len(rows)} results, {int(res['significant'].sum())} significant")
        return 0
    except Exception as exc:
        log.failure(f"pipeline failed: {exc}")
        if engine is not None and run_id is not None:
            from . import db
            db.finish_run(engine, run_id, False, str(exc))
        raise


if __name__ == "__main__":
    sys.exit(main())
