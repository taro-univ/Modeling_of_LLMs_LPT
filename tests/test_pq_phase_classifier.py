import numpy as np

from analysis.isotropy import IsotropyFitter
from analysis.pq_metrics import compute_pq_moments, pairwise_overlaps, trial_mean_vectors
from analysis.pq_phase_classifier import Thresholds, classify_from_moments


def test_pairwise_overlaps_excludes_self_overlap():
    vectors = np.array(
        [
            [1.0, 0.0],
            [0.0, 1.0],
            [1.0, 1.0],
        ]
    )

    q_vals = pairwise_overlaps(vectors)

    assert q_vals.shape == (3,)
    assert not np.any(np.isclose(q_vals, 1.0))


def test_trial_mean_vectors_censors_short_trials():
    hidden = [
        np.array([[1.0, 0.0], [3.0, 0.0]]),
        np.array([[0.0, 1.0]]),
    ]

    means = trial_mean_vectors(hidden, min_steps=2)

    assert means.n_censored == 1
    assert means.vectors.shape == (1, 2)
    np.testing.assert_allclose(means.vectors[0], [2.0, 0.0])


def test_remove_topk_removes_dominant_common_direction():
    X = np.array(
        [
            [10.0, 1.0],
            [11.0, 1.0],
            [12.0, 1.0],
            [13.0, 1.0],
        ]
    )
    transformer = IsotropyFitter(method="remove_topk", topk=1).fit(X)
    transformed = transformer.transform(X)

    assert np.linalg.matrix_rank(transformed, tol=1e-8) <= 1
    np.testing.assert_allclose(transformed.mean(axis=0), [0.0, 0.0], atol=1e-8)


def test_moments_are_finite_for_valid_q_values():
    q_vals = np.array([-0.2, 0.1, 0.4, 0.8, 0.9])
    moments = compute_pq_moments(q_vals, tail_threshold=0.5, n_bootstrap=20, random_seed=1)

    assert moments.q_count == 5
    assert moments.q_tail_mass == 0.4
    assert np.isfinite(moments.q_mean)
    assert np.isfinite(moments.q_var)
    assert len(moments.q_mean_ci_95) == 2


def test_unset_thresholds_make_phase_undetermined():
    moments = {"q_var": 0.01, "q_tail_mass": 1.0, "q_bimodality_bc": 0.8, "q_mean": 0.7}

    phase = classify_from_moments(accuracy=1.0, moments=moments, n_effective=25, thresholds=Thresholds())

    assert phase == "undetermined"


def test_classify_ordered_when_accuracy_tail_and_low_variance_match():
    moments = {"q_var": 0.01, "q_tail_mass": 0.9, "q_bimodality_bc": 0.2, "q_mean": 0.8}
    thresholds = Thresholds(
        acc_ordered_min=0.5,
        ordered_var_max=0.05,
        ordered_tail_min=0.7,
        min_trials=5,
    )

    phase = classify_from_moments(accuracy=0.8, moments=moments, n_effective=25, thresholds=thresholds)

    assert phase == "ordered"


def test_classify_paramagnetic_uses_pq_not_pm_rate():
    moments = {"q_var": 0.01, "q_tail_mass": 0.0, "q_bimodality_bc": 0.2, "q_mean": 0.02}
    thresholds = Thresholds(
        acc_ordered_min=0.5,
        pm_mean_max=0.05,
        pm_var_max=0.02,
        pm_rate_min=0.9,
        min_trials=5,
    )

    phase = classify_from_moments(accuracy=0.0, moments=moments, n_effective=25, thresholds=thresholds)

    assert phase == "paramagnetic"
