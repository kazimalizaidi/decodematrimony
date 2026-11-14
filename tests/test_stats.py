import numpy as np
from decodematrimony.survey_stats import (SurveyDesign, bootstrap, holm, weighted_auc,
                                          weighted_quantile, weighted_rank, weighted_spearman)


def test_weighted_quantile_median():
    assert weighted_quantile(np.array([1.0, 2, 3, 4]), np.ones(4), 0.5) == 2.5


def test_weighted_quantile_respects_weights():
    assert weighted_quantile(np.array([1.0, 10.0]), np.array([99.0, 1.0]), 0.5) < 2


def test_rank_ties_midpoint():
    r = weighted_rank(np.array([1.0, 1.0, 2.0]), np.ones(3))
    assert r[0] == r[1] == 1.0 and r[2] == 2.5


def test_spearman_perfect_and_inverse():
    x = np.arange(1.0, 11)
    w = np.ones(10)
    assert abs(weighted_spearman(x, x, w) - 1) < 1e-12
    assert abs(weighted_spearman(x, -x, w) + 1) < 1e-12


def test_auc_known_values():
    x, y = np.array([3.0, 4.0]), np.array([1.0, 2.0])
    assert weighted_auc(x, np.ones(2), y, np.ones(2)) == 1.0
    assert weighted_auc(x, np.ones(2), x, np.ones(2)) == 0.5


def test_holm_matches_hand_calc():
    assert holm([0.01, 0.04, 0.03]) == [0.03, 0.06, 0.06]


def test_rao_wu_preserves_expected_total_weight():
    rng = np.random.default_rng(1)
    n = 400
    strata = rng.integers(1, 4, n)
    psu = strata * 10 + rng.integers(0, 8, n)
    d = SurveyDesign(rng.uniform(0.5, 2, n), psu.astype(np.int64), strata.astype(np.int64))
    totals = [w.sum() for w in d.replicate_weights(300, 3)]
    assert abs(np.mean(totals) / d.weight.sum() - 1) < 0.03


def test_bootstrap_detects_known_effect():
    rng = np.random.default_rng(2)
    n = 600
    strata = rng.integers(1, 4, n).astype(np.int64)
    psu = (strata * 10 + rng.integers(0, 8, n)).astype(np.int64)
    x = rng.normal(size=n)
    y = x + rng.normal(scale=0.5, size=n)
    d = SurveyDesign(np.ones(n), psu, strata)
    res = bootstrap(d, lambda w: weighted_spearman(x, y, w), 200, 5)
    assert res.estimate > 0.7 and res.p_value < 0.05 and res.ci_low > 0.5
