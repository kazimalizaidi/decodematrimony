"""💗 SQL Server access: idempotent MERGE loads, GO-batch migrations, rollback on failure. ✨"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import pandas as pd
from sqlalchemy import NVARCHAR, Engine, create_engine, text

from . import logger as log

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _ident(name: str) -> str:
    """🧸 Only our own constant identifiers ever reach SQL text."""
    if not _IDENT.match(name):
        raise ValueError(f"unsafe SQL identifier: {name!r}")
    return name


def make_engine(url: str) -> Engine:
    return create_engine(url, fast_executemany=True, future=True)


def apply_migrations(engine: Engine, sql_dir: Path) -> None:
    """🎀 Run every sql/*.sql in order, splitting on GO lines, inside one transaction."""
    try:
        with engine.begin() as conn:
            for f in sorted(sql_dir.glob("*.sql")):
                for batch in re.split(r"^\s*GO\s*$", f.read_text(encoding="utf-8"), flags=re.M | re.I):
                    if batch.strip():
                        conn.exec_driver_sql(batch)
                log.milestone(f"applied migration {f.name}")
        log.success("migrations committed")
    except Exception as exc:
        log.failure(f"migration rolled back: {exc}")
        raise


def build_merge_sql(schema: str, table: str, stage: str, keys: Sequence[str], cols: Sequence[str]) -> str:
    """✨ Generate an idempotent MERGE (upsert) from staging into a target table."""
    s, t, st = _ident(schema), _ident(table), _ident(stage)
    on = " AND ".join(f"t.{_ident(k)} = s.{_ident(k)}" for k in keys)
    non_keys = [c for c in cols if c not in keys]
    upd = ", ".join(f"t.{_ident(c)} = s.{_ident(c)}" for c in non_keys)
    ins_cols = ", ".join(_ident(c) for c in cols)
    ins_vals = ", ".join(f"s.{_ident(c)}" for c in cols)
    when_matched = f"WHEN MATCHED THEN UPDATE SET {upd} " if non_keys else ""
    return (
        f"MERGE {s}.{t} AS t USING stg.{st} AS s ON {on} {when_matched}"
        f"WHEN NOT MATCHED BY TARGET THEN INSERT ({ins_cols}) VALUES ({ins_vals});"
    )


def stage_dtypes(clean: pd.DataFrame) -> dict[str, NVARCHAR]:
    """🧸 Bounded NVARCHAR(500) for text columns in staging tables: NVARCHAR(MAX) makes pyodbc's
    fast_executemany slow and fragile on SQL Server."""
    return {c: NVARCHAR(500) for c in clean.columns if clean[c].map(lambda v: isinstance(v, str)).any()}


def merge_dataframe(engine: Engine, df: pd.DataFrame, schema: str, table: str, keys: Sequence[str]) -> None:
    """🌸 Land df in stg.<table>_stage then MERGE; commit on success, rollback on any error."""
    stage = f"{_ident(table)}_stage"
    clean = df.astype(object).where(df.notna(), None)
    try:
        with engine.begin() as conn:
            clean.to_sql(stage, conn, schema="stg", if_exists="replace", index=False, chunksize=5000,
                         dtype=stage_dtypes(clean))
            conn.execute(text(build_merge_sql(schema, table, stage, keys, list(df.columns))))
        log.success(f"merged {len(df):,} rows into {schema}.{table}")
    except Exception as exc:
        log.failure(f"rollback on {schema}.{table}: {exc}")
        raise


def start_run(engine: Engine, n_boot: int, seed: int) -> uuid.UUID:
    rid = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO ops.run_log(run_id,started_at,status,n_boot,seed) VALUES (:r,:t,'RUNNING',:b,:s)"),
            {"r": str(rid), "t": datetime.now(timezone.utc).replace(tzinfo=None), "b": n_boot, "s": seed},
        )
    return rid


def finish_run(engine: Engine, rid: uuid.UUID, ok: bool, message: str = "") -> None:
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE ops.run_log SET finished_at=:t,status=:s,message=:m WHERE run_id=:r"),
            {"t": datetime.now(timezone.utc).replace(tzinfo=None), "s": "SUCCESS" if ok else "FAILED",
             "m": message[:1000], "r": str(rid)},
        )


def record_lineage(engine: Engine, source: str, sha256: str, n_rows: int) -> None:
    """🧸 Same file hash twice = no duplicate lineage row (idempotent)."""
    with engine.begin() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM ops.data_lineage WHERE source_name=:s AND file_sha256=:h"),
            {"s": source, "h": sha256},
        ).first()
        if exists is None:
            conn.execute(
                text("INSERT INTO ops.data_lineage VALUES (:s,:h,:n,:t)"),
                {"s": source, "h": sha256, "n": n_rows, "t": datetime.now(timezone.utc).replace(tzinfo=None)},
            )
