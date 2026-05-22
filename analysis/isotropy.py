"""Hidden-state isotropization for replica-overlap analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


ArrayLike2D = np.ndarray


def stack_hidden_samples(hidden_trials: Iterable[np.ndarray]) -> np.ndarray:
    """Stack all move-step hidden states from all trials into one 2D matrix."""
    # float32 のまま保持してメモリ効率を確保（float64 への昇格は不要）
    arrays = [np.asarray(H, dtype=np.float32) for H in hidden_trials if np.asarray(H).ndim == 2 and H.shape[0] > 0]
    if not arrays:
        return np.empty((0, 0), dtype=np.float32)
    return np.vstack(arrays)


@dataclass(frozen=True)
class IsotropyTransformer:
    """Apply a fitted centering/top-k removal/ZCA transform."""

    method: str
    mean_: np.ndarray
    components_: np.ndarray | None = None
    zca_matrix_: np.ndarray | None = None

    def transform(self, X: ArrayLike2D) -> np.ndarray:
        X_arr = np.asarray(X, dtype=np.float32)
        if X_arr.ndim == 1:
            X_arr = X_arr.reshape(1, -1)
        centered = X_arr - self.mean_
        if self.method == "center":
            return centered
        if self.method == "remove_topk":
            if self.components_ is None or self.components_.size == 0:
                return centered
            projection = centered @ self.components_.T @ self.components_
            return centered - projection
        if self.method == "zca":
            if self.zca_matrix_ is None:
                return centered
            return centered @ self.zca_matrix_
        raise ValueError(f"Unknown isotropy method: {self.method}")

    def transform_trials(self, hidden_trials: Iterable[np.ndarray]) -> list[np.ndarray]:
        return [self.transform(H) for H in hidden_trials]


class IsotropyFitter:
    """Fit isotropization parameters on the model/layer-wide hidden-state union."""

    def __init__(self, method: str = "remove_topk", topk: int = 3, zca_reg: float = 1e-5):
        if method not in {"center", "remove_topk", "zca"}:
            raise ValueError("method must be one of: center, remove_topk, zca")
        if topk < 0:
            raise ValueError("topk must be non-negative")
        if zca_reg <= 0:
            raise ValueError("zca_reg must be positive")
        self.method = method
        self.topk = topk
        self.zca_reg = zca_reg

    def fit(self, X: ArrayLike2D) -> IsotropyTransformer:
        # float32 のまま処理。hidden state の精度には十分で、SVD も float32 で動作する
        X_arr = np.asarray(X, dtype=np.float32)
        if X_arr.ndim != 2 or X_arr.shape[0] == 0:
            raise ValueError("X must be a non-empty 2D array")
        mean = X_arr.mean(axis=0)
        centered = X_arr - mean

        if self.method == "center":
            return IsotropyTransformer(method=self.method, mean_=mean)

        if self.method == "remove_topk":
            k = min(self.topk, centered.shape[0], centered.shape[1])
            if k == 0:
                components = np.empty((0, centered.shape[1]), dtype=np.float32)
            else:
                # X^T X (d×d) の固有値分解で top-k 右特異ベクトルを取得。
                # full SVD (LAPACK SGESDD) はワーク領域が O(m×n²) になり大規模データで OOM になる。
                # eigh は対称行列専用 (SSYEVD) でワーク領域が O(d²) に留まる（今回は d=3584）。
                cov = centered.T @ centered          # shape (d, d), float32
                eigvals, eigvecs = np.linalg.eigh(cov)  # ascending order
                # eigh は昇順なので末尾 k 列が top-k 固有ベクトル（= 主成分方向）
                components = eigvecs[:, -k:].T.astype(np.float32)  # shape (k, d)
            return IsotropyTransformer(method=self.method, mean_=mean, components_=components)

        cov = np.cov(centered, rowvar=False)
        eigvals, eigvecs = np.linalg.eigh(cov)
        eigvals = np.maximum(eigvals, 0.0)
        inv_sqrt = np.diag(1.0 / np.sqrt(eigvals + self.zca_reg))
        zca = eigvecs @ inv_sqrt @ eigvecs.T
        return IsotropyTransformer(method=self.method, mean_=mean, zca_matrix_=zca)


def fit_isotropy(
    hidden_trials: Iterable[np.ndarray],
    method: str = "remove_topk",
    topk: int = 3,
    zca_reg: float = 1e-5,
) -> IsotropyTransformer:
    """Fit isotropy on all hidden-state steps in the supplied model/layer union."""
    samples = stack_hidden_samples(hidden_trials)
    return IsotropyFitter(method=method, topk=topk, zca_reg=zca_reg).fit(samples)
