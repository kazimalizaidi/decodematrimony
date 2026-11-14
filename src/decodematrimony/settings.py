"""🎀 Typed settings + the DHS variable map (verify codes against YOUR recode manual!). 🧸"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class DhsVariableMap:
    """🧸 Column names in the DHS Couples' Recode (CR) file.

    These are the standard DHS recode names, but Pakistan files can differ.
    Verify each against the official recode manual and override with a JSON
    file (config/dhs_variable_map.json). The loader fails loudly on missing
    required columns instead of guessing. 💗
    """

    case_id: str = "caseid"
    weight: str = "v005"
    psu: str = "v021"
    strata: str = "v022"
    wife_age: str = "v012"
    husband_age: str = "mv012"
    wife_edu: str = "v106"
    husband_edu: str = "mv106"
    wealth: str = "v190"
    region: str = "v024"
    wife_age_first_union: str = "v511"
    wife_working: str = "v714"
    wife_ethnicity: Optional[str] = None  # optional: structural missingness is OK
    husband_ethnicity: Optional[str] = None

    @classmethod
    def from_json(cls, path: Path) -> "DhsVariableMap":
        raw = json.loads(path.read_text(encoding="utf-8"))
        allowed = {f.name for f in fields(cls)}
        unknown = set(raw) - allowed
        if unknown:
            raise ValueError(f"Unknown variable-map keys: {sorted(unknown)}")
        return cls(**raw)

    def required(self) -> list[str]:
        return [
            v for k, v in asdict(self).items()
            if v is not None and k not in ("wife_ethnicity", "husband_ethnicity")
        ]


@dataclass(frozen=True)
class Settings:
    """✨ Everything configurable, read from env vars (see .env.example)."""

    db_url: Optional[str]
    n_boot: int
    seed: int
    min_cell: int
    out_dir: Path

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            db_url=os.getenv("DM_DB_URL"),
            n_boot=int(os.getenv("DM_N_BOOT", "1000")),
            seed=int(os.getenv("DM_SEED", "20260101")),
            min_cell=int(os.getenv("DM_MIN_CELL", "30")),
            out_dir=Path(os.getenv("DM_OUT_DIR", "out")),
        )
