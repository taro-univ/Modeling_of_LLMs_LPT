"""P(q) overlap moments for phase classification."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Iterable

import numpy as np
from scipy import stats

from analysis.io_utils import _cosine

LOGGER = logging.getLogger(__name__)

try:
    from diptest import diptest as _diptest  # type: ignore
except Exception:
    _diptest = None
    LOGGER.warning(
        "diptest not installed; q_bimodality_dip and q_bimodality_dip_pval will be NaN. "
        "Install with: pip install diptest"
    )


@dataclass(frozen=True)
class TrialMeans:
    vectors: np.ndarray
    n_censored: int
    norms: np.ndarray


@dataclass(frozen=True)
class PQMoments:
    q_mean: float
    q_mean_ci_95: tuple[float, float]
    q_var: float
    q_var_ci_95: tuple[float, float]
    q_abs_mean_exploratory: float
    q_tail_mass: float
    q_bimodality_bc: float
    q_bimodality_dip: float
    q_bimodality_dip_pval: float
    q_count: int
    hbar_norm_mean: float
    hbar_norm_std: float

    def to_dict(self) -> dict:
        d = asdict(self)
        d["q_mean_ci_95"] = list(self.q_mean_ci_95)
        d["q_var_ci_95"] = list(self.q_var_ci_95)
        return d


def trial_mean_vectors(hidden_trials: Iterable[np.ndarray], min_steps: int = 1) -> TrialMeans:
    """Time-average each replica hidden trajectory after censoring short trials."""
    vectors: list[np.ndarray] = []
    n_censored = 0
    for H in hidden_trials:
        H_arr = np.asarray(H, dtype=np.float64)
        if H_arr.ndim != 2 or H_arr.shape[0] < min_steps:
            n_censored += 1
            continue
        vectors.append(H_arr.mean(axis=0))

    if not vectors:
        return TrialMeans(
            vectors=np.empty((0, 0), dtype=np.float64),
            n_censored=n_censored,
            norms=np.empty((0,), dtype=np.float64),
        )

    mat = np.vstack(vectors)
    return TrialMeans(vectors=mat, n_censored=n_censored, norms=np.linalg.norm(mat, axis=1))


def pairwise_overlaps(vectors: np.ndarray) -> np.ndarray:
    """Compute off-diagonal replica overlaps q^{alpha beta}; self-overlaps are excluded."""
    X = np.asarray(vectors, dtype=np.float64)
    if X.ndim != 2 or X.shape[0] < 2:
        return np.empty((0,), dtype=np.float64)
    q_vals = [_cosine(X[i], X[j]) for i, j in combinations(range(X.shape[0]), 2)]
    return np.asarray(q_vals, dtype=np.float64)


def _bootstrap_ci(vals: np.ndarray, fn, n_bootstrap: int, rng: np.random.Generator) -> tuple[float, float]:
    clean = vals[np.isfinite(vals)]
    if clean.size == 0:
        return (float("nan"), float("nan"))
    if clean.size == 1 or n_bootstrap <= 0:
        v = float(fn(clean))
        return (v, v)
    boots = np.empty(n_bootstrap, dtype=np.float64)
    for i in range(n_bootstrap):
        sample = rng.choice(clean, size=clean.size, replace=True)
        boots[i] = fn(sample)
    return (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)))


def sarle_bimodality_coefficient(vals: np.ndarray) -> float:
    clean = vals[np.isfinite(vals)]
    if clean.size < 3:
        return float("nan")
    skew = stats.skew(clean, bias=False)
    kurt = stats.kurtosis(clean, fisher=False, bias=False)
    if not np.isfinite(kurt) or abs(kurt) < 1e-12:
        return float("nan")
    return float((skew * skew + 1.0) / kurt)


def hartigan_dip_statistic(vals: np.ndarray) -> float:
    """Return Hartigan's dip statistic, or NaN when diptest is unavailable."""
    clean = np.sort(vals[np.isfinite(vals)])
    if clean.size < 3 or _diptest is None:
        return float("nan")
    dip, _ = _diptest(clean)
    return float(dip)


def dip_pvalue(vals: np.ndarray, observed: float, n_bootstrap: int, rng: np.random.Generator) -> float:
    clean = vals[np.isfinite(vals)]
    if clean.size < 3 or not np.isfinite(observed) or _diptest is None:
        return float("nan")
    _, pval = _diptest(clean, boot_pval=True, n_boot=n_bootstrap)
    return float(pval)


def compute_pq_moments(
    q_vals: np.ndarray,
    hbar_norms: np.ndarray | None = None,
    tail_threshold: float = 0.5,
    n_bootstrap: int = 500,
    random_seed: int = 0,
) -> PQMoments:
    clean = np.asarray(q_vals, dtype=np.float64)
    clean = clean[np.isfinite(clean)]
    rng = np.random.default_rng(random_seed)
    if clean.size == 0:
        nan_ci = (float("nan"), float("nan"))
        return PQMoments(
            q_mean=float("nan"),
            q_mean_ci_95=nan_ci,
            q_var=float("nan"),
            q_var_ci_95=nan_ci,
            q_abs_mean_exploratory=float("nan"),
            q_tail_mass=float("nan"),
            q_bimodality_bc=float("nan"),
            q_bimodality_dip=float("nan"),
            q_bimodality_dip_pval=float("nan"),
            q_count=0,
            hbar_norm_mean=float("nan"),
            hbar_norm_std=float("nan"),
        )

    norms = np.asarray(hbar_norms if hbar_norms is not None else [], dtype=np.float64)
    dip = hartigan_dip_statistic(clean)
    return PQMoments(
        q_mean=float(np.mean(clean)),
        q_mean_ci_95=_bootstrap_ci(clean, np.mean, n_bootstrap, rng),
        q_var=float(np.var(clean)),
        q_var_ci_95=_bootstrap_ci(clean, np.var, n_bootstrap, rng),
        q_abs_mean_exploratory=float(np.mean(np.abs(clean))),
        q_tail_mass=float(np.mean(clean >= tail_threshold)),
        q_bimodality_bc=sarle_bimodality_coefficient(clean),
        q_bimodality_dip=dip,
        q_bimodality_dip_pval=dip_pvalue(clean, dip, n_bootstrap, rng),
        q_count=int(clean.size),
        hbar_norm_mean=float(np.mean(norms)) if norms.size else float("nan"),
        hbar_norm_std=float(np.std(norms)) if norms.size else float("nan"),
    )
