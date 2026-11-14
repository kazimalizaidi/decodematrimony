"""🎀 DHS Couples' Recode reader: Stata/CSV in, typed raw frame + value labels + lineage hash out. ✨

You must obtain the real file yourself from the DHS Program (registration + approval).
We never fabricate or simulate data here. 🧸
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from .. import logger as log
from ..settings import DhsVariableMap


@dataclass(frozen=True)
class RawDhs:
    frame: pd.DataFrame
    value_labels: dict[str, dict[int, str]]
    sha256: str
    source_name: str


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_dhs_couples(path: Path, vmap: DhsVariableMap) -> RawDhs:
    """💗 Read only the columns we need; fail loudly (listing them) if any required one is absent."""
    if not path.exists():
        log.failure(f"file not found: {path}")
        raise FileNotFoundError(path)
    wanted = list(dict.fromkeys(vmap.required() + [c for c in (vmap.wife_ethnicity, vmap.husband_ethnicity) if c]))
    labels: dict[str, dict[int, str]] = {}
    suffix = path.suffix.lower()
    if suffix == ".dta":
        reader: Any
        with pd.read_stata(path, iterator=True, convert_categoricals=False) as reader:
            available = list(reader.variable_labels().keys())
            labels = {k: {int(c): str(v) for c, v in d.items()} for k, d in reader.value_labels().items()}
            missing_req = [c for c in vmap.required() if c not in available]
            if missing_req:
                raise KeyError(f"required DHS columns missing from file: {missing_req}")
            keep = [c for c in wanted if c in available]
            for opt in (vmap.wife_ethnicity, vmap.husband_ethnicity):
                if opt and opt not in available:
                    log.missing(f"optional column {opt} not in file; ethnicity lens will be skipped")
            frame = reader.read(columns=keep)
    elif suffix == ".csv":
        head = pd.read_csv(path, nrows=0)
        missing_req = [c for c in vmap.required() if c not in head.columns]
        if missing_req:
            raise KeyError(f"required DHS columns missing from file: {missing_req}")
        frame = pd.read_csv(path, usecols=[c for c in wanted if c in head.columns], dtype_backend="numpy_nullable")
    else:
        raise ValueError(f"unsupported file type: {suffix}")
    log.success(f"read {len(frame):,} couples x {frame.shape[1]} columns from {path.name}")
    return RawDhs(frame=frame, value_labels=labels, sha256=sha256_file(path), source_name=path.name)
