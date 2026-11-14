"""🎀 Verify a SQL Server load. Needs DM_DB_URL.  python scripts/verify_sql_load.py --results-csv out/results.csv --expect-couples 24628 ✨"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from decodematrimony import logger as log  # noqa: E402
from decodematrimony.db import make_engine  # noqa: E402
from decodematrimony.verify import run_checks  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--results-csv", type=Path, default=None)
ap.add_argument("--expect-couples", type=int, default=None)
a = ap.parse_args()
url = os.getenv("DM_DB_URL")
if not url:
    log.failure("DM_DB_URL is not set")
    sys.exit(2)
good = run_checks(make_engine(url), a.results_csv, a.expect_couples)
(log.success if good else log.failure)("ALL CHECKS PASSED" if good else "SOME CHECKS FAILED")
sys.exit(0 if good else 1)
