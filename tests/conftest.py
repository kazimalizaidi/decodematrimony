"""🧸 SYNTHETIC TEST FIXTURES ONLY. They exist to unit-test code paths and are never read by the pipeline. 🎀"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def make_fixture(n: int = 1500, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    strata = rng.integers(1, 5, n)
    psu = strata * 100 + rng.integers(1, 12, n)
    wedu = rng.integers(0, 4, n)
    wealth = rng.integers(1, 6, n)
    wage = rng.integers(18, 50, n)
    gap = (8 - 2 * wedu + rng.normal(0, 3, n)).round().astype(int)   # planted: more education -> smaller gap
    afu = np.clip(15 + 0.15 * (50 - wage) + rng.normal(0, 2, n), 10, 40).round().astype(int)  # planted gradient
    return pd.DataFrame({
        "caseid": [f"  {i:06d} " for i in range(n)],
        "v005": rng.integers(300_000, 2_500_000, n), "v021": psu, "v022": strata,
        "v012": wage, "mv012": wage + gap, "v106": wedu,
        "mv106": np.clip(wedu + rng.integers(-1, 2, n), 0, 3), "v190": wealth,
        "v024": rng.choice([1, 2, 3, 4], n), "v511": afu, "v714": rng.integers(0, 2, n),
    })


@pytest.fixture(scope="session")
def raw_frame() -> pd.DataFrame:
    return make_fixture()
