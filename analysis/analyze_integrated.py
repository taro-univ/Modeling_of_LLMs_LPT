"""
analyze_integrated.py — full_sweep + collapse_phase 統合相図・P(q) 解析

full_sweep (T=0.1~1.0) と collapse_phase (T=1.1~3.0) を統合し、
広域 N-T 相図と P(q) 分布を描画する。

使用例:
  python3 analysis/analyze_integrated.py
  python3 analysis/analyze_integrated.py --model deepseek-r1-distill-qwen-7b --layer layer_mid
"""

from __future__ import annotations

import argparse
import json
import random
from itertools import combinations
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
import numpy as np

# ===========================================================================
# 定数
# ===========================================================================

MODEL_DEFAULT = "deepseek-r1-distill-qwen-7b"
LAYER_DEFAULT = "layer_mid"

NS_DEFAULT = [2, 3, 4, 5, 6]

# full_sweep: T=0.1~1.0 (0.1刻み)
TS_FULL = [round(t * 0.1, 1) for t in range(1, 11)]
# collapse_phase: T=1.1~3.0 (不等間隔)
TS_COLLAPSE = [1.1, 1.2, 1.3, 1.4, 1.5, 1.8, 2.0, 2.5, 3.0]
TS_ALL = TS_FULL + TS_COLLAPSE

# P(q) dist グリッド用代表温度（広域をカバーする10点）
TS_PQ = [0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 1.2, 1.5, 2.0, 3.0]

Q_BINS    = np.linspace(-0.1, 1.05, 47)
Q_CENTERS = (Q_BINS[:-1] + Q_BINS[1:]) / 2

PHASE_COLORS = {
    "ordered":      "#1f77b4",
    "spin_glass":   "#ff7f0e",
    "mixed":        "#9467bd",
    "paramagnetic": "#d62728",
}
PHASE_TO_INT = {"ordered": 3, "spin_glass": 2, "mixed": 1, "paramagnetic": 0}
INT_TO_LABEL = {3: "ordered", 2: "spin glass", 1: "mixed", 0: "paramagnetic"}
CMAP_PHASES  = ListedColormap([
    PHASE_COLORS["paramagnetic"], PHASE_COLORS["mixed"],
    PHASE_COLORS["spin_glass"],   PHASE_COLORS["ordered"],
])


# ===========================================================================
# データロード
# ===========================================================================

def _early_stop_rate(early_stop: list, keys: set) -> float:
    """early_stop リスト中で keys に属する要素の割合を返す。空なら nan。"""
    if not early_stop:
        return float("nan")
    return sum(1 for es in early_stop if es in keys) / len(early_stop)


def _load_hidden_from_dir(cdir: Path, layer: str):
    """cdir 内の npz ファイルから隠れ状態と fallback フラグを収集する。"""
    hidden_list: list[np.ndarray] = []
    is_fallback_list: list[bool]  = []
    for npz_path in sorted(cdir.glob("trial_*_hidden.npz")):
        d = np.load(npz_path, allow_pickle=True)
        if layer not in d:
            continue
        H = d[layer].astype(np.float32)
        texts = list(d["move_texts"])
        is_fb = (len(texts) > 0 and texts[0] == "__fallback__")
        hidden_list.append(H)
        is_fallback_list.append(is_fb)
    return hidden_list, is_fallback_list


def load_condition(
    dirs: list[Path],
    N: int,
    T: float,
    layer: str,
) -> Optional[dict]:
    """複数ディレクトリから (N, T) 条件のデータを検索してロードする。"""
    tag = f"{T:.1f}".replace(".", "_")
    for base_dir in dirs:
        cdir = base_dir / f"N{N}_T{tag}"
        if not cdir.exists():
            continue

        summary = []
        sp = cdir / "summary.json"
        if sp.exists():
            with open(sp) as f:
                summary = json.load(f)

        hidden_list, is_fallback_list = _load_hidden_from_dir(cdir, layer)
        if not hidden_list:
            continue

        accuracy   = [r["accuracy"]       for r in summary] if summary else []
        early_stop = [r.get("early_stop") for r in summary] if summary else []

        return {
            "hidden":       hidden_list,
            "is_fallback":  is_fallback_list,
            "accuracy":     accuracy,
            "early_stop":   early_stop,
            "pm_rate":      _early_stop_rate(early_stop, {"no_move_catchall", "move_ceiling"}),
            "sg_rate":      _early_stop_rate(early_stop, {"move_loop_repeat", "move_loop_reverse"}),
            "ordered_rate": _early_stop_rate(early_stop, {"goal_reached"}),
            "n_trials":     len(hidden_list),
            "N": N, "T": T,
        }
    return None


# ===========================================================================
# 物理量計算
# ===========================================================================

def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def compute_pq(cond: dict) -> np.ndarray:
    means = [H.mean(axis=0) for H in cond["hidden"]]
    q_vals = [_cosine(means[i], means[j]) for i, j in combinations(range(len(means)), 2)]
    return np.array(q_vals, dtype=np.float32)


def compute_qea(cond: dict, max_pairs_per_trial: int = 300) -> float:
    """試行内ステップ間コサイン類似度の平均 (Edwards-Anderson order parameter)。"""
    vals = []
    for H, is_fb in zip(cond["hidden"], cond["is_fallback"]):
        if is_fb or H.shape[0] < 2:
            continue
        pairs = list(combinations(range(H.shape[0]), 2))
        if len(pairs) > max_pairs_per_trial:
            pairs = random.sample(pairs, max_pairs_per_trial)
        for i, j in pairs:
            vals.append(_cosine(H[i], H[j]))
    return float(np.mean(vals)) if vals else float("nan")


def compute_autocorr(cond: dict, max_lag: int = 8) -> np.ndarray:
    result = []
    for lag in range(1, max_lag + 1):
        vals = []
        for H, is_fb in zip(cond["hidden"], cond["is_fallback"]):
            if is_fb or H.shape[0] <= lag:
                continue
            for t in range(H.shape[0] - lag):
                vals.append(_cosine(H[t], H[t + lag]))
        result.append(float(np.mean(vals)) if vals else float("nan"))
    return np.array(result)


def _is_paramagnetic(pm_rate: float) -> bool:
    """PM 相の判定: pm_rate が有限かつ 0.5 超。"""
    return not np.isnan(pm_rate) and pm_rate > 0.5


def _is_spin_glass(sg_rate: float, q_ea: Optional[float]) -> bool:
    """SG 相の判定: sg_rate > 0.3 または q_EA > 0.70 のいずれかが成立。"""
    by_rate = not np.isnan(sg_rate) and sg_rate > 0.3
    by_qea  = q_ea is not None and not np.isnan(q_ea) and q_ea > 0.70
    return by_rate or by_qea


def classify_phase(cond: dict, q_ea: Optional[float] = None) -> str:
    """早期終了ラベル率と q_EA から相を分類して文字列ラベルを返す。"""
    acc = float(np.mean(cond["accuracy"])) if cond["accuracy"] else 0.0
    if acc > 0.4:
        return "ordered"
    if _is_paramagnetic(cond["pm_rate"]):
        return "paramagnetic"
    if _is_spin_glass(cond["sg_rate"], q_ea):
        return "spin_glass"
    return "mixed"


# ===========================================================================
# ヘルパー：heatmap の軸ラベル設定（非均等 T グリッド対応）
# ===========================================================================

def _set_T_ticks(ax, ts: list[float], step: int = 2, rotation: int = 45) -> None:
    positions = list(range(0, len(ts), step))
    ax.set_xticks(positions)
    ax.set_xticklabels([f"{ts[i]:.1f}" for i in positions], rotation=rotation, fontsize=7)


def _build_phase_mat(all_conds, ns, ts, qea_cache=None) -> np.ndarray:
    mat = np.full((len(ns), len(ts)), np.nan)
    for i, N in enumerate(ns):
        for j, T in enumerate(ts):
            cond = all_conds.get((N, T))
            if cond is None:
                continue
            q_ea = (qea_cache or {}).get((N, T))
            mat[i, j] = PHASE_TO_INT[classify_phase(cond, q_ea)]
    return mat


# ===========================================================================
# Figure 1: 統合相図（4パネル）— private helpers
# ===========================================================================

def _plot_accuracy_heatmap(
    ax,
    all_conds: dict,
    ns: list[int],
    ts: list[float],
) -> None:
    """パネル1: accuracy heatmap を描画する。"""
    acc_mat = np.full((len(ns), len(ts)), np.nan)
    for i, N in enumerate(ns):
        for j, T in enumerate(ts):
            cond = all_conds.get((N, T))
            if cond and cond["accuracy"]:
                acc_mat[i, j] = float(np.mean(cond["accuracy"]))

    im = ax.imshow(acc_mat, aspect="auto", origin="lower",
                   vmin=0, vmax=1, cmap="RdYlBu")
    plt.colorbar(im, ax=ax, label="accuracy $m$")
    ax.set_title("Accuracy heatmap")
    ax.set_ylabel("Disk count  N")
    ax.set_yticks(range(len(ns)))
    ax.set_yticklabels(ns)
    _set_T_ticks(ax, ts)
    sep = TS_FULL.index(TS_FULL[-1])  # = 9 (T=1.0 の列インデックス)
    ax.axvline(sep + 0.5, color="k", ls=":", lw=1.5, alpha=0.7, label="sweep boundary (T=1.0)")
    ax.legend(fontsize=8, loc="upper right")


def _plot_accuracy_vs_T(
    ax,
    all_conds: dict,
    ns: list[int],
    ts: list[float],
    colors_n,
) -> None:
    """パネル2: Accuracy vs Temperature 折れ線を描画する。"""
    ax.set_title("Accuracy vs Temperature  (per N)")
    for idx, N in enumerate(ns):
        ts_v, acc_v, err_v = [], [], []
        for T in ts:
            cond = all_conds.get((N, T))
            if cond and cond["accuracy"]:
                a = cond["accuracy"]
                ts_v.append(T)
                acc_v.append(float(np.mean(a)))
                err_v.append(float(np.std(a) / np.sqrt(len(a))))
        ax.errorbar(ts_v, acc_v, yerr=err_v, fmt="o-",
                    color=colors_n[idx], lw=1.5, ms=4, label=f"N={N}")
    ax.axhline(0.5, color="gray", ls="--", alpha=0.6, label="threshold=0.5")
    ax.axvline(1.0, color="k", ls=":", lw=1, alpha=0.5)
    ax.set_xlabel("Temperature  T")
    ax.set_ylabel("Accuracy")
    ax.set_ylim(-0.05, 1.05)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)


def _plot_phase_heatmap(
    ax,
    all_conds: dict,
    ns: list[int],
    ts: list[float],
    qea_cache: dict,
) -> None:
    """パネル3: Phase classification heatmap を描画する。"""
    phase_mat = _build_phase_mat(all_conds, ns, ts, qea_cache)
    im2 = ax.imshow(phase_mat, aspect="auto", origin="lower",
                    vmin=-0.5, vmax=3.5, cmap=CMAP_PHASES)
    cbar2 = plt.colorbar(im2, ax=ax, ticks=[0, 1, 2, 3])
    cbar2.ax.set_yticklabels([INT_TO_LABEL[i] for i in [0, 1, 2, 3]], fontsize=8)
    ax.set_title("Phase classification  (early_stop + q_EA)")
    ax.set_xlabel("Temperature  T")
    ax.set_ylabel("Disk count  N")
    ax.set_yticks(range(len(ns)))
    ax.set_yticklabels(ns)
    _set_T_ticks(ax, ts)
    sep = TS_FULL.index(TS_FULL[-1])
    ax.axvline(sep + 0.5, color="k", ls=":", lw=1.5, alpha=0.7)


def _find_tc(ts_v: list[float], acc_v: list[float], threshold: float = 0.15) -> Optional[float]:
    """高温側から走査して Tc を線形補間で求める。見つからなければ None。"""
    for j in range(len(ts_v) - 1, 0, -1):
        if acc_v[j - 1] >= threshold > acc_v[j]:
            slope = (acc_v[j] - acc_v[j - 1]) / (ts_v[j] - ts_v[j - 1])
            return ts_v[j - 1] + (threshold - acc_v[j - 1]) / slope
    return None


def _fit_power_law(ax, bc_ns: list[int], bc_Tc: list[float]) -> None:
    """冪乗則フィットを試みて ax に描画する。失敗は無視。"""
    try:
        ns_arr = np.array(bc_ns, dtype=float)
        Tc_arr = np.array(bc_Tc, dtype=float)
        coeffs = np.polyfit(np.log(ns_arr), np.log(Tc_arr), 1)
        alpha  = -coeffs[0]
        A      = np.exp(coeffs[1])
        ns_fit = np.linspace(min(bc_ns) * 0.8, max(bc_ns) * 1.2, 50)
        ax.plot(ns_fit, A * ns_fit**(-alpha), "r--",
                label=fr"$T_c \propto N^{{-{alpha:.2f}}}$")
    except Exception:
        pass


def _compute_boundary(all_conds: dict, ns: list[int], ts: list[float]) -> dict[int, Optional[float]]:
    """各 N について Tc を求め {N: Tc or None} を返す。"""
    boundary: dict[int, Optional[float]] = {}
    for N in ns:
        ts_v, acc_v = [], []
        for T in ts:
            cond = all_conds.get((N, T))
            if cond and cond["accuracy"]:
                ts_v.append(T)
                acc_v.append(float(np.mean(cond["accuracy"])))
        boundary[N] = _find_tc(ts_v, acc_v)
    return boundary


def _annotate_missing_tc(ax, all_conds: dict, ns: list[int], ts: list[float],
                          boundary: dict) -> None:
    """Tc が見つからない N について、最大 accuracy が低い場合に注釈を付ける。"""
    for N in ns:
        if boundary.get(N) is not None:
            continue
        max_acc = max(
            (float(np.mean(all_conds[(N, T)]["accuracy"]))
             for T in ts if (N, T) in all_conds and all_conds[(N, T)]["accuracy"]),
            default=None,
        )
        if max_acc is not None and max_acc < 0.5:
            ax.annotate(f"N={N}\n(acc<0.5)", xy=(N, 0.05), fontsize=7,
                        ha="center", color="gray")


def _plot_Tc_boundary(
    ax,
    all_conds: dict,
    ns: list[int],
    ts: list[float],
) -> None:
    """パネル4: Tc(N) 境界と冪乗フィットを描画する。"""
    ax.set_title(r"Phase Boundary  $T_c(N)$")
    boundary = _compute_boundary(all_conds, ns, ts)

    bc_ns = [N for N in ns if boundary.get(N) is not None]
    bc_Tc = [boundary[N] for N in bc_ns]
    if bc_ns:
        ax.plot(bc_ns, bc_Tc, "ko-", linewidth=2, markersize=9, label=r"$T_c(N)$")
        if len(bc_ns) >= 2:
            _fit_power_law(ax, bc_ns, bc_Tc)

    _annotate_missing_tc(ax, all_conds, ns, ts, boundary)
    ax.set_xlabel("Disk count  N")
    ax.set_ylabel(r"$T_c(N)$")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)


def plot_phase_diagram(
    all_conds: dict,
    ns: list[int],
    ts: list[float],
    out_path: Path,
    qea_cache: dict,
) -> None:
    fig = plt.figure(figsize=(20, 10))
    gs  = gridspec.GridSpec(2, 3, figure=fig, hspace=0.45, wspace=0.35)
    ax_hm  = fig.add_subplot(gs[0, :2])
    ax_acc = fig.add_subplot(gs[0, 2])
    ax_ph  = fig.add_subplot(gs[1, :2])
    ax_tc  = fig.add_subplot(gs[1, 2])
    fig.suptitle("Integrated Phase Diagram  (full_sweep + collapse_phase,  DeepSeek-R1-Distill-Qwen-7B)", fontsize=13)

    colors_n = plt.cm.tab10(np.linspace(0, 0.6, len(ns)))

    _plot_accuracy_heatmap(ax_hm, all_conds, ns, ts)
    _plot_accuracy_vs_T(ax_acc, all_conds, ns, ts, colors_n)
    _plot_phase_heatmap(ax_ph, all_conds, ns, ts, qea_cache)
    _plot_Tc_boundary(ax_tc, all_conds, ns, ts)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"[SAVE] {out_path}")
    plt.close(fig)


# ===========================================================================
# Figure 2: P(q) 分布グリッド
# ===========================================================================

def plot_pq_dist(
    all_conds: dict,
    ns: list[int],
    ts_pq: list[float],
    out_path: Path,
    layer: str,
    qea_cache: dict,
) -> None:
    fig, axes = plt.subplots(
        len(ns), len(ts_pq),
        figsize=(2.2 * len(ts_pq), 2.0 * len(ns)),
        sharex=True, sharey=False,
    )
    fig.suptitle(f"P(q) Overlap Distribution  ({layer},  integrated)", fontsize=12, y=1.01)

    for i, N in enumerate(ns):
        for j, T in enumerate(ts_pq):
            ax = axes[i][j] if len(ns) > 1 else axes[j]
            cond = all_conds.get((N, T))

            if cond is None:
                ax.text(0.5, 0.5, "N/A", ha="center", va="center",
                        transform=ax.transAxes, fontsize=8, color="gray")
                ax.set_xticks([])
                ax.set_yticks([])
                continue

            q_vals = compute_pq(cond)
            q_ea   = qea_cache.get((N, T))
            phase  = classify_phase(cond, q_ea)
            color  = PHASE_COLORS[phase]

            ax.hist(q_vals, bins=Q_BINS, color=color, alpha=0.75, density=True)
            ax.axvline(float(np.nanmean(q_vals)), color="k", lw=1.2, ls="--", alpha=0.7)

            pm_str = f"{cond['pm_rate']:.0%}" if not np.isnan(cond["pm_rate"]) else "N/A"
            ax.text(0.04, 0.93, f"q̄={np.nanmean(q_vals):.2f}\npm={pm_str}",
                    transform=ax.transAxes, fontsize=6, va="top")

            if i == 0:
                ax.set_title(f"T={T}", fontsize=8)
            if j == 0:
                ax.set_ylabel(f"N={N}", fontsize=8)
            ax.set_xlim(-0.1, 1.05)
            ax.tick_params(labelsize=6)

    legend_elements = [
        Patch(facecolor=PHASE_COLORS[p], label=p.replace("_", " "))
        for p in ["ordered", "spin_glass", "mixed", "paramagnetic"]
    ]
    fig.legend(handles=legend_elements, loc="lower center",
               ncol=4, fontsize=8, bbox_to_anchor=(0.5, -0.02))

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"[SAVE] {out_path}")
    plt.close(fig)


# ===========================================================================
# Figure 3: 統合サマリー（4パネル）— private helpers
# ===========================================================================

def _plot_qea_vs_T(
    ax,
    qea_cache: dict,
    ns: list[int],
    ts: list[float],
    colors_n,
) -> None:
    """パネル1: q_EA vs Temperature を描画する。"""
    ax.set_title(r"$q_{EA}$  vs  Temperature")
    for idx, N in enumerate(ns):
        ts_v, qea_v = [], []
        for T in ts:
            q_ea = qea_cache.get((N, T))
            if q_ea is not None and not np.isnan(q_ea):
                ts_v.append(T)
                qea_v.append(q_ea)
        if ts_v:
            ax.plot(ts_v, qea_v, "o-", color=colors_n[idx],
                    lw=1.8, ms=5, label=f"N={N}")
    ax.axvline(1.0, color="k", ls=":", lw=1, alpha=0.5)
    ax.set_xlabel("Temperature  T")
    ax.set_ylabel(r"$q_{EA}$")
    ax.set_ylim(0.4, 1.02)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)


def _plot_pm_rate_vs_T(
    ax,
    all_conds: dict,
    ns: list[int],
    ts: list[float],
    colors_n,
) -> None:
    """パネル2: PM rate vs Temperature を描画する。"""
    ax.set_title("PM rate  vs  Temperature\n(paramagnetic phase indicator)")
    for idx, N in enumerate(ns):
        ts_v, pm_v = [], []
        for T in ts:
            cond = all_conds.get((N, T))
            if cond is not None and not np.isnan(cond["pm_rate"]):
                ts_v.append(T)
                pm_v.append(cond["pm_rate"])
        if ts_v:
            ax.plot(ts_v, pm_v, "s-", color=colors_n[idx],
                    lw=1.8, ms=5, label=f"N={N}")
    ax.axhline(0.5, color="gray", ls="--", alpha=0.6, label="50%")
    ax.axvline(1.0, color="k", ls=":", lw=1, alpha=0.5)
    ax.set_xlabel("Temperature  T")
    ax.set_ylabel("PM rate  (no_move_catchall + move_ceiling)")
    ax.set_ylim(-0.05, 1.05)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)


def _plot_autocorr(
    ax,
    all_conds: dict,
    ns: list[int],
    layer: str,  # noqa: ARG001  (layer は将来の拡張のために引数として保持)
) -> None:
    """パネル3: 代表条件の時間自己相関 C(Δt) を描画する。"""
    ax.set_title(r"Time autocorrelation  $C(\Delta t)$")
    palette = ["#1f77b4", "#ff7f0e", "#d62728", "#9467bd", "#2ca02c", "#8c564b"]
    rep_conds = [
        (ns[0],  0.2,  f"N={ns[0]}  T=0.2"),
        (ns[-1], 0.2,  f"N={ns[-1]}  T=0.2"),
        (ns[0],  1.5,  f"N={ns[0]}  T=1.5"),
        (ns[-1], 1.5,  f"N={ns[-1]}  T=1.5"),
    ]
    for k, (N, T, label) in enumerate(rep_conds):
        cond = all_conds.get((N, T))
        if cond is None:
            continue
        C     = compute_autocorr(cond, max_lag=8)
        lags  = np.arange(1, 9)
        valid = ~np.isnan(C)
        if valid.any():
            ax.plot(lags[valid], C[valid], "o-", color=palette[k],
                    lw=1.8, ms=6, label=label)
    ax.set_xlabel(r"$\Delta t$  (move steps)")
    ax.set_ylabel(r"$C(\Delta t)$")
    ax.set_ylim(0.4, 1.02)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)


def _plot_sg_rate_vs_T(
    ax,
    all_conds: dict,
    ns: list[int],
    ts: list[float],
    qea_cache: dict,
) -> None:
    """パネル4: Phase classification heatmap を描画する（summary パネル用）。"""
    ax.set_title("Phase classification")
    phase_mat = _build_phase_mat(all_conds, ns, ts, qea_cache)
    im = ax.imshow(phase_mat, aspect="auto", origin="lower",
                   vmin=-0.5, vmax=3.5, cmap=CMAP_PHASES)
    cbar = plt.colorbar(im, ax=ax, ticks=[0, 1, 2, 3])
    cbar.ax.set_yticklabels([INT_TO_LABEL[i] for i in [0, 1, 2, 3]], fontsize=8)
    ax.set_ylabel("Disk count  N")
    ax.set_xlabel("Temperature  T")
    ax.set_yticks(range(len(ns)))
    ax.set_yticklabels(ns)
    _set_T_ticks(ax, ts, step=3)
    sep = len(TS_FULL) - 1
    ax.axvline(sep + 0.5, color="k", ls=":", lw=1.5, alpha=0.7)


def plot_summary(
    all_conds: dict,
    ns: list[int],
    ts: list[float],
    out_path: Path,
    layer: str,
    qea_cache: dict,
) -> None:
    fig = plt.figure(figsize=(14, 10))
    gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.38, wspace=0.32)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[1, 0])
    ax4 = fig.add_subplot(gs[1, 1])
    fig.suptitle(f"Integrated P(q) Summary  ({layer})", fontsize=13)

    colors_n = plt.cm.tab10(np.linspace(0, 0.6, len(ns)))

    _plot_qea_vs_T(ax1, qea_cache, ns, ts, colors_n)
    _plot_pm_rate_vs_T(ax2, all_conds, ns, ts, colors_n)
    _plot_autocorr(ax3, all_conds, ns, layer)
    _plot_sg_rate_vs_T(ax4, all_conds, ns, ts, qea_cache)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"[SAVE] {out_path}")
    plt.close(fig)


# ===========================================================================
# エントリポイント
# ===========================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="full_sweep + collapse_phase 統合解析")
    parser.add_argument("--model",  type=str, default=MODEL_DEFAULT)
    parser.add_argument("--layer",  type=str, default=LAYER_DEFAULT)
    parser.add_argument("--ns",     type=int, nargs="+", default=NS_DEFAULT)
    parser.add_argument("--base",   type=str, default="results/hanoi")
    parser.add_argument("--out-dir", type=str, default="figures")
    return parser.parse_args()


def main() -> None:
    args  = parse_args()
    base  = Path(args.base)
    dirs  = [
        base / "full_sweep"     / args.model,
        base / "collapse_phase" / args.model,
    ]
    print(f"[INFO] モデル: {args.model}  layer: {args.layer}")
    for d in dirs:
        print(f"  {d}  ({'ok' if d.exists() else 'NOT FOUND'})")

    # --- データロード ---
    all_conds: dict = {}
    for N in args.ns:
        for T in TS_ALL:
            cond = load_condition(dirs, N, T, args.layer)
            if cond is not None:
                all_conds[(N, T)] = cond
    print(f"[INFO] {len(all_conds)} 条件をロードしました。")

    # --- q_EA を事前計算（一括）---
    print("[INFO] q_EA を計算中 ...")
    qea_cache: dict[tuple[int, float], float] = {}
    for (N, T), cond in all_conds.items():
        qea_cache[(N, T)] = compute_qea(cond)
    print("[INFO] q_EA 計算完了。")

    # --- 出力先 ---
    out_dir = Path(args.out_dir)
    prefix  = f"{args.model}_integrated"

    # --- 作図 ---
    plot_phase_diagram(
        all_conds, args.ns, TS_ALL,
        out_dir / f"{prefix}_phase.png",
        qea_cache,
    )
    plot_pq_dist(
        all_conds, args.ns, TS_PQ,
        out_dir / f"{prefix}_pq_dist.png",
        args.layer, qea_cache,
    )
    plot_summary(
        all_conds, args.ns, TS_ALL,
        out_dir / f"{prefix}_summary.png",
        args.layer, qea_cache,
    )

    print("\n[DONE]")
    print(f"  相図         : {out_dir}/{prefix}_phase.png")
    print(f"  P(q) 分布    : {out_dir}/{prefix}_pq_dist.png")
    print(f"  サマリー     : {out_dir}/{prefix}_summary.png")


if __name__ == "__main__":
    main()
