"""Shared utilities for analysis modules."""

from __future__ import annotations

import numpy as np

TS_FULL = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0]
TS_COLLAPSE = [1.1, 1.3, 1.7, 2.5, 3.0]
TS_ALL = sorted(set(TS_FULL + TS_COLLAPSE))
TS_PQ = [0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 1.2, 1.5, 2.0, 3.0]


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Safe cosine similarity; zero vectors return 0.0."""
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def load_condition(dirs, N: int, T: float, layer: str):
    """Compatibility loader backed by BaseAnalyzer._load_condition.

    Returns a flat dict compatible with the functional API in pq_metrics /
    pq_phase_classifier / stagnation_diagnostic.  Does NOT import spin_glass
    to avoid a layer-inversion dependency.
    """
    from pathlib import Path

    from analysis.base_analyzer import BaseAnalyzer

    class _Loader(BaseAnalyzer):
        def run_analysis(self):  # pragma: no cover
            raise NotImplementedError

    for base_dir in [Path(d) for d in dirs]:
        loader = _Loader(base_dir, out_dir=".", ns=[N], ts=[T], layer=layer)
        cond = loader._load_condition(N, T, load_hidden=True)
        if cond is None:
            continue
        hidden = cond.hidden.get(layer, [])
        d = {
            "hidden": hidden,
            "is_fallback": cond.is_fallback[: len(hidden)],
            "accuracy": [r["accuracy"] for r in cond.trials],
            "early_stop": cond.early_stop,
            "pm_rate": cond.pm_rate,
            "sg_rate": cond.sg_rate,
            "ordered_rate": cond.ordered_rate,
            "n_trials": len(hidden),
            "N": cond.N,
            "T": cond.T,
        }
        if d["hidden"]:
            return d
    return None
