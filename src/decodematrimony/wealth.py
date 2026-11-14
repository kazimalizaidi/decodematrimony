"""🎀 DHS-style household wealth index (weighted PCA on housing + asset indicators) -> quintiles. ✨

Why not consumption? The consumption file (sec_6a) is item-level with group-total codes mixed in, so summing
it risks double counting unless the coding scheme is applied exactly. A housing/asset PCA index is the standard
DHS method and needs no code semantics beyond 'yes=1, no=2' (printed in the HIES variable labels). 🧸
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from . import logger as log
from .survey_stats import F64, weighted_quantile


def _wmean_sd(x: F64, w: F64) -> tuple[float, float]:
    m = float(np.average(x, weights=w))
    return m, float(np.sqrt(np.average((x - m) ** 2, weights=w)))


def build_wealth_index(
    hh: pd.DataFrame,
    weight: str,
    yes_no: Sequence[str],
    categorical: Sequence[str],
    numeric: Sequence[str],
    min_share: float = 0.01,
) -> pd.DataFrame:
    """Return a frame (same index as `hh`) with `wealth_score` and `wealth_quintile` (1 poorest .. 5 richest).

    * yes_no columns: 1 = has asset, anything else = no (missing counted as no, logged)
    * categorical columns: one dummy per category with weighted share between min_share and 1-min_share
    * numeric columns: clipped at the weighted 99th percentile, missing filled with the weighted mean
    The first principal component of the weighted correlation matrix is the score; its sign is oriented so it
    correlates positively with the number of assets owned.
    """
    w = hh[weight].to_numpy(np.float64)
    if (w <= 0).any() or not np.isfinite(w).all():
        raise ValueError("weights must be positive and finite")
    cols: dict[str, F64] = {}
    asset_count = np.zeros(len(hh))
    for c in yes_no:
        has: F64 = np.asarray((pd.to_numeric(hh[c], errors="coerce") == 1).to_numpy(), dtype=np.float64)
        miss = int(pd.to_numeric(hh[c], errors="coerce").isna().sum())
        if miss:
            log.missing(f"wealth: {c} has {miss:,} missing values (treated as 'no')")
        cols[c] = has
        asset_count += has
    for c in categorical:
        codes = pd.to_numeric(hh[c], errors="coerce")
        for k in sorted(codes.dropna().unique()):
            ind: F64 = np.asarray((codes == k).to_numpy(), dtype=np.float64)
            share = float(np.average(ind, weights=w))
            if min_share <= share <= 1 - min_share:
                cols[f"{c}={k:g}"] = ind
    for c in numeric:
        v = pd.to_numeric(hh[c], errors="coerce").to_numpy(np.float64)
        ok = np.isfinite(v)
        cap = weighted_quantile(v[ok], w[ok], 0.99)
        fill = float(np.average(np.minimum(v[ok], cap), weights=w[ok]))
        cols[c] = np.where(ok, np.minimum(v, cap), fill)
    z: list[F64] = []
    names: list[str] = []
    for name, x in cols.items():
        m, sd = _wmean_sd(x, w)
        if sd > 1e-9:
            z.append((x - m) / sd)
            names.append(name)
    if len(z) < 3:
        raise ValueError("too few non-constant wealth indicators")
    Z = np.column_stack(z)
    cov = (Z * w[:, None]).T @ Z / w.sum()
    vals, vecs = np.linalg.eigh(cov)
    v1 = vecs[:, -1]
    score = Z @ v1
    ac = asset_count - np.average(asset_count, weights=w)
    sc = score - np.average(score, weights=w)
    if float(np.sum(w * ac * sc)) < 0:
        score, v1 = -score, -v1
    log.milestone(f"wealth PCA: {len(names)} indicators, PC1 explains {vals[-1] / vals.sum():.1%} of variance")
    cuts = [weighted_quantile(score, w, q) for q in (0.2, 0.4, 0.6, 0.8)]
    quint = np.searchsorted(np.array(cuts), score, side="right") + 1
    return pd.DataFrame({"wealth_score": score, "wealth_quintile": quint.astype(np.int64)}, index=hh.index)
