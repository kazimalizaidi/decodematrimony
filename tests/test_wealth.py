"""🧸 SYNTHETIC unit test for the wealth index."""
import numpy as np
import pandas as pd
import pytest
from decodematrimony.wealth import build_wealth_index


def _hh(n=4000, seed=2):
    rng = np.random.default_rng(seed)
    latent = rng.normal(size=n)
    d = pd.DataFrame({"pw": rng.uniform(1, 5, n)})
    for i, c in enumerate(["a1", "a2", "a3", "a4"]):
        d[c] = np.where(latent + rng.normal(scale=0.6, size=n) > i * 0.4 - 0.4, 1, 2)
    d["roof"] = np.where(latent > 0, 1, 2) + (rng.random(n) < 0.1)
    d["rooms"] = np.clip(np.round(3 + latent + rng.normal(scale=0.5, size=n)), 1, 12)
    d["area"] = 100 + 30 * latent + rng.normal(scale=15, size=n)   # continuous, so few score ties
    d["latent"] = latent
    return d


def test_index_orients_and_balances():
    d = _hh()
    out = build_wealth_index(d, "pw", ["a1", "a2", "a3", "a4"], ["roof"], ["rooms", "area"])
    assert np.corrcoef(out["wealth_score"], d["latent"])[0, 1] > 0.8      # sign oriented to assets
    share = d["pw"].groupby(out["wealth_quintile"]).sum() / d["pw"].sum()
    assert sorted(out["wealth_quintile"].unique()) == [1, 2, 3, 4, 5]
    assert (share.sub(0.2).abs() < 0.02).all()


def test_rejects_bad_weights():
    d = _hh(100)
    d.loc[0, "pw"] = 0
    with pytest.raises(ValueError):
        build_wealth_index(d, "pw", ["a1", "a2"], ["roof"], ["rooms"])
