"""📉 Survey-weighted, non-parametric statistics with a Rao-Wu rescaled bootstrap. 🎀

Everything here respects the DHS design: weights, PSUs (clusters) and strata.
Naive i.i.d. tests would understate uncertainty, so we resample PSUs within
strata instead. ✨
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterator, Sequence

import numpy as np
from numpy.typing import NDArray

F64 = NDArray[np.float64]
I64 = NDArray[np.int64]


def weighted_quantile(values: F64, weights: F64, q: float) -> float:
    """✨ Weighted quantile via interpolated cumulative weights."""
    m = np.isfinite(values) & (weights > 0)
    v, w = values[m], weights[m]
    if v.size == 0:
        return float("nan")
    order = np.argsort(v, kind="stable")
    v, w = v[order], w[order]
    cw = (np.cumsum(w) - 0.5 * w) / w.sum()
    return float(np.interp(q, cw, v))


def weighted_mean(values: F64, weights: F64) -> float:
    m = np.isfinite(values) & (weights > 0)
    return float(np.average(values[m], weights=weights[m])) if m.any() else float("nan")


def weighted_rank(x: F64, w: F64) -> F64:
    """🌸 Weighted mid-ranks (ties share the midpoint of their cumulative weight)."""
    uniq, inv = np.unique(x, return_inverse=True)
    gw = np.bincount(inv, weights=w, minlength=uniq.size)
    mid = np.cumsum(gw) - gw / 2.0
    return mid[inv].astype(np.float64)


def weighted_spearman(x: F64, y: F64, w: F64) -> float:
    """✨ Weighted Spearman = weighted Pearson on weighted mid-ranks."""
    m = np.isfinite(x) & np.isfinite(y) & (w > 0)
    if m.sum() < 3:
        return float("nan")
    xr, yr, ww = weighted_rank(x[m], w[m]), weighted_rank(y[m], w[m]), w[m]
    mx, my = np.average(xr, weights=ww), np.average(yr, weights=ww)
    cov = np.sum(ww * (xr - mx) * (yr - my))
    vx, vy = np.sum(ww * (xr - mx) ** 2), np.sum(ww * (yr - my) ** 2)
    return float(cov / np.sqrt(vx * vy)) if vx > 0 and vy > 0 else float("nan")


def weighted_auc(x: F64, wx: F64, y: F64, wy: F64) -> float:
    """🎀 Weighted probability of superiority P(X>Y)+0.5P(X=Y) (Mann-Whitney effect size)."""
    mx, my = np.isfinite(x) & (wx > 0), np.isfinite(y) & (wy > 0)
    x, wx, y, wy = x[mx], wx[mx], y[my], wy[my]
    if x.size == 0 or y.size == 0:
        return float("nan")
    order = np.argsort(y, kind="stable")
    ys, cw = y[order], np.concatenate([[0.0], np.cumsum(wy[order])])
    lo = np.searchsorted(ys, x, side="left")
    hi = np.searchsorted(ys, x, side="right")
    less, eq = cw[lo], cw[hi] - cw[lo]
    return float(np.sum(wx * (less + 0.5 * eq)) / (wx.sum() * wy.sum()))


def holm(pvals: Sequence[float]) -> list[float]:
    """🧸 Holm-Bonferroni step-down adjusted p-values (order preserved)."""
    n = len(pvals)
    order = np.argsort(pvals)
    adj = np.empty(n)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (n - rank) * pvals[idx]))
        adj[idx] = running
    return [float(a) for a in adj]


@dataclass(frozen=True)
class SurveyDesign:
    """✨ Weights + PSU + strata, with a Rao-Wu rescaled bootstrap generator."""

    weight: F64
    psu: I64
    strata: I64

    def __post_init__(self) -> None:
        if not (len(self.weight) == len(self.psu) == len(self.strata)):
            raise ValueError("design arrays must be the same length")

    def subset(self, mask: NDArray[np.bool_]) -> "SurveyDesign":
        return SurveyDesign(self.weight[mask], self.psu[mask], self.strata[mask])

    def replicate_weights(self, n_boot: int, seed: int) -> Iterator[F64]:
        """Rao-Wu: in stratum h with n_h PSUs draw n_h-1 PSUs with replacement and
        rescale by n_h/(n_h-1). Single-PSU strata contribute no variance (kept as is)."""
        rng = np.random.default_rng(seed)
        keys = np.stack([self.strata, self.psu], axis=1)
        uniq, inv = np.unique(keys, axis=0, return_inverse=True)
        inv = inv.reshape(-1)
        strata_of_psu = uniq[:, 0]
        groups = [np.flatnonzero(strata_of_psu == s) for s in np.unique(strata_of_psu)]
        for _ in range(n_boot):
            mult = np.ones(uniq.shape[0])
            for g in groups:
                n_h = g.size
                if n_h < 2:
                    continue
                counts = rng.multinomial(n_h - 1, np.full(n_h, 1.0 / n_h))
                mult[g] = counts * (n_h / (n_h - 1))
            yield self.weight * mult[inv]


@dataclass(frozen=True)
class BootResult:
    estimate: float
    ci_low: float
    ci_high: float
    p_value: float
    n_valid: int


def bootstrap(
    design: SurveyDesign,
    stat: Callable[[F64], float],
    n_boot: int,
    seed: int,
    null: float = 0.0,
) -> BootResult:
    """✨ Point estimate + percentile 95% CI + bootstrap two-sided p vs `null`."""
    est = stat(design.weight)
    reps = np.array([stat(w) for w in design.replicate_weights(n_boot, seed)])
    reps = reps[np.isfinite(reps)]
    if reps.size < max(20, n_boot // 2) or not np.isfinite(est):
        return BootResult(est, float("nan"), float("nan"), float("nan"), int(reps.size))
    lo, hi = np.percentile(reps, [2.5, 97.5])
    tail = min(np.sum(reps <= null), np.sum(reps >= null))
    p = min(1.0, (2.0 * tail + 1.0) / (reps.size + 1.0))
    return BootResult(float(est), float(lo), float(hi), float(p), int(reps.size))
