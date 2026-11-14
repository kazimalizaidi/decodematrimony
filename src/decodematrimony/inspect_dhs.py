"""🧸 Column checker: run this FIRST on your real PKCR71 file, before the pipeline. ✨

  python -m decodematrimony.inspect_dhs data/raw/PKCR71FL.DTA [config/dhs_variable_map.json]

Prints each variable we need with its official label from the file, so YOU can verify
every code by eye (no guessing). 🎀
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from . import logger as log
from .settings import DhsVariableMap


def inspect(path: Path, vmap: DhsVariableMap) -> list[str]:
    reader: Any
    with pd.read_stata(path, iterator=True, convert_categoricals=False) as reader:
        labels: dict[str, str] = reader.variable_labels()
    missing_cols: list[str] = []
    log.milestone(f"{path.name}: {len(labels)} variables found")
    for role, col in vmap.__dict__.items():
        if col is None:
            log.missing(f"{role:22s} (not configured, lens will be skipped)")
        elif col in labels:
            log.success(f"{role:22s} {col:8s} -> {labels[col]}")
        else:
            log.failure(f"{role:22s} {col:8s} NOT IN FILE")
            missing_cols.append(col)
    return missing_cols


def main(argv: Optional[list[str]] = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        log.failure("usage: python -m decodematrimony.inspect_dhs <file.dta> [varmap.json]")
        return 2
    vmap = DhsVariableMap.from_json(Path(args[1])) if len(args) > 1 else DhsVariableMap()
    return 1 if inspect(Path(args[0]), vmap) else 0


if __name__ == "__main__":
    sys.exit(main())
