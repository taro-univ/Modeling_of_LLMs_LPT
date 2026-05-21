"""
analyze_pq.py — P(q) overlap 分布によるスピングラス・常磁性相の判別

pq_sweep の npz ファイルから以下の物理量を計算し可視化する:
  - P(q): replica 間 overlap 分布（スピングラス相：双峰, 常磁性相：q≈0 に集中）
  - q_EA : Edwards-Anderson order parameter（試行内自己相関のプラトー値）
  - C(Δt): ステップ間時間自己相関関数

使用例:
  python3 analyze_pq.py
  python3 analyze_pq.py --dir results/hanoi/pq_sweep --layer layer_m8
  python3 analyze_pq.py --out figures/pq_analysis.png
"""

from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

# ===========================================================================
# 定数
# ===========================================================================

LAYER_DEFAULT = "layer_m8"   # 中間層（最も識別的）
NS_DEFAULT    = [3, 4, 5]
TS_DEFAULT    = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0]

# P(q) の bin 設定
Q_BINS = np.linspace(-0.1, 1.05, 47)
Q_CENTERS = (Q_BINS[:-1] + Q_BINS[1:]) / 2


# ===========================================================================
# データロード
# ===========================================================================

def _load_npz_for_condition(cdir: Path, layer: str) -> tuple[list, list]:
    """
    ディレクトリ内の trial_*_hidden.npz を読み込み、
    hidden state リストと fallback フラグリストを返す。

    Returns:
        (hidden_list, is_fallback_list)
    """
    hidden_list: list[np.ndarray] = []
    is_fallback_list: list[bool] = []
    for npz_path in sorted(cdir.glob("trial_*_hidden.npz")):
        d = np.load(npz_path, allow_pickle=True)
        if layer not in d:
            continue
        H = d[layer].astype(np.float32)   # (steps, D)
        texts = list(d["move_texts"])
        is_fb = (len(texts) > 0 and texts[0] == "__fallback__")
        hidden_list.append(H)
        is_fallback_list.append(is_fb)
    return hidden_list, is_fallback_list


def _parse_summary(summary_path: Path, early_stop_keys: tuple[str, ...]) -> tuple[list, list, float]:
    """
    summary.json を読み込み accuracy・early_stop リストと pm_rate を返す。
    ファイルが存在しない場合は空リストと nan を返す。

    Returns:
        (accuracy, early_stop, pm_rate)
    """
    if not summary_path.exists():
        return [], [], float("nan")
    with open(summary_path) as f:
        summary = json.load(f)
    accuracy = [r["accuracy"] for r in summary]
    early_stop = [r.get("early_stop") for r in summary]
    pm_rate = (
        sum(1 for es in early_stop if es in early_stop_keys) / len(early_stop)
        if early_stop else float("nan")
    )
    return accuracy, early_stop, pm_rate


def load_condition(
    base_dir: Path,
    N: int,
    T: float,
    layer: str,
) -> Optional[dict]:
    """
    1 条件分の npz を読み込み、hidden state 行列と統計情報を返す。

    Returns:
        dict with keys:
            hidden     : list[np.ndarray]  各試行の hidden state 行列 (steps, D)
            is_fallback: list[bool]        各試行が fallback（no-move）か
            accuracy   : list[int]
            early_stop : list[str|None]
    """
    tag  = f"{T:.1f}".replace(".", "_")
    cdir = base_dir / f"N{N}_T{tag}"
    if not cdir.exists():
        return None

    hidden_list, is_fallback_list = _load_npz_for_condition(cdir, layer)
    if not hidden_list:
        return None

    pm_keys = ("no_move_catchall", "move_ceiling")
    accuracy, early_stop, pm_rate = _parse_summary(cdir / "summary.json", pm_keys)

    return {
        "hidden":      hidden_list,
        "is_fallback": is_fallback_list,  # npz由来：qEA/自己相関計算で使用
        "accuracy":    accuracy,
        "early_stop":  early_stop,
        "pm_rate":     pm_rate,           # summary.json由来：相分類で使用
        "n_trials":    len(hidden_list),
        "N": N, "T": T,
    }


# ===========================================================================
# 物理量の計算
# ===========================================================================

def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """1D ベクトル間のコサイン類似度。"""
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def trial_mean_hidden(H: np.ndarray) -> np.ndarray:
    """試行の hidden state 行列を平均して 1D ベクトルに集約する。"""
    return H.mean(axis=0)


def compute_pq(cond: dict) -> np.ndarray:
    """
    replica 間 overlap q^{αβ} を計算する。

    各試行の平均 hidden state をそれぞれの replica とみなし、
    全試行ペアのコサイン類似度を返す。

    Returns:
        shape (n_pairs,) の q 値配列。
    """
    means = [trial_mean_hidden(H) for H in cond["hidden"]]
    q_vals = [
        _cosine(means[i], means[j])
        for i, j in combinations(range(len(means)), 2)
    ]
    return np.array(q_vals, dtype=np.float32)


def compute_qea(cond: dict) -> float:
    """
    Edwards-Anderson order parameter q_EA を計算する。

    試行内の全ステップペアのコサイン類似度の平均。
    fallback（1 ステップ）は除外する。
    """
    vals = []
    for H, is_fb in zip(cond["hidden"], cond["is_fallback"]):
        if is_fb or H.shape[0] < 2:
            continue
        for i, j in combinations(range(H.shape[0]), 2):
            vals.append(_cosine(H[i], H[j]))
    return float(np.mean(vals)) if vals else float("nan")


def compute_autocorr(cond: dict, max_lag: int = 10) -> np.ndarray:
    """
    ステップ間時間自己相関 C(Δt) を計算する。

    C(Δt) = 全試行・全 (t, t+Δt) ペアのコサイン類似度の平均。
    fallback 試行は除外。

    Returns:
        shape (max_lag,) の C(Δt) 配列。Δt=1,2,...,max_lag。
    """
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


def compute_collapse_rates(cond: dict) -> dict[str, float]:
    """崩壊モード比率を返す。"""
    n = len(cond["early_stop"])
    if n == 0:
        fb = sum(cond["is_fallback"])
        return {"fallback": fb / cond["n_trials"]}
    counts: dict[str, int] = {}
    for es in cond["early_stop"]:
        k = es if es else "none"
        counts[k] = counts.get(k, 0) + 1
    return {k: v / n for k, v in counts.items()}


# ===========================================================================
# 描画ユーティリティ
# ===========================================================================

PHASE_COLORS = {
    "ordered":    "#1f77b4",   # 青
    "spin_glass": "#ff7f0e",   # オレンジ
    "paramagnetic": "#d62728", # 赤
    "mixed":      "#9467bd",   # 紫
}


def classify_phase(q_ea: float, pm_rate: float, fallback_rate: float, accuracy: float) -> str:
    """q_EA と PM率から相を分類する。
    pm_rate（summary.json の no_move_catchall 比率）を優先し、
    summary.json がない場合（nan）は fallback_rate（npz 由来）で代替する。
    """
    if accuracy > 0.4:
        return "ordered"
    effective_pm = pm_rate if not np.isnan(pm_rate) else fallback_rate
    if effective_pm > 0.6:
        return "paramagnetic"
    if not np.isnan(q_ea) and q_ea > 0.70:
        return "spin_glass"
    return "mixed"


# ===========================================================================
# plot_pq_distributions — サブパネル helper
# ===========================================================================

def _render_pq_cell(
    ax: plt.Axes,
    cond: dict,
    i: int,
    j: int,
    N: int,
    T: float,
) -> None:
    """plot_pq_distributions の 1 セル（N, T）を描画する。"""
    q_vals = compute_pq(cond)
    acc = float(np.mean(cond["accuracy"])) if cond["accuracy"] else 0.0
    q_ea = compute_qea(cond)
    fb_rate = sum(cond["is_fallback"]) / cond["n_trials"]
    phase = classify_phase(q_ea, cond["pm_rate"], fb_rate, acc)
    color = PHASE_COLORS[phase]

    ax.hist(q_vals, bins=Q_BINS, color=color, alpha=0.75, density=True)
    ax.axvline(np.nanmean(q_vals), color="k", lw=1.2, ls="--", alpha=0.7)

    pm_str = f"{cond['pm_rate']:.0%}" if not np.isnan(cond["pm_rate"]) else "N/A"
    label = f"q̄={np.nanmean(q_vals):.2f}\npm={pm_str}"
    ax.text(0.04, 0.93, label, transform=ax.transAxes,
            fontsize=6, va="top", color="black")

    if i == 0:
        ax.set_title(f"T={T}", fontsize=8)
    if j == 0:
        ax.set_ylabel(f"N={N}", fontsize=8)
    ax.set_xlim(-0.1, 1.05)
    ax.tick_params(labelsize=6)


def _render_pq_cell_na(ax: plt.Axes) -> None:
    """データがない（N/A）セルを描画する。"""
    ax.text(0.5, 0.5, "N/A", ha="center", va="center",
            transform=ax.transAxes, fontsize=8, color="gray")
    ax.set_xticks([])
    ax.set_yticks([])


# ===========================================================================
# メイン描画
# ===========================================================================

def plot_pq_distributions(
    all_conds: dict[tuple[int, float], dict],
    ns: list[int],
    ts: list[float],
    out_path: Path,
    layer: str = LAYER_DEFAULT,
) -> None:
    """
    P(q) 分布をグリッド状に配置した図を生成する。
    行 = N、列 = T。
    """
    fig, axes = plt.subplots(
        len(ns), len(ts),
        figsize=(2.2 * len(ts), 2.0 * len(ns)),
        sharex=True, sharey=False,
    )
    fig.suptitle(f"P(q) Overlap Distribution  ({layer})", fontsize=12, y=1.01)

    for i, N in enumerate(ns):
        for j, T in enumerate(ts):
            ax = axes[i][j] if len(ns) > 1 else axes[j]
            cond = all_conds.get((N, T))
            if cond is None:
                _render_pq_cell_na(ax)
            else:
                _render_pq_cell(ax, cond, i, j, N, T)

    # 凡例
    from matplotlib.patches import Patch
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
# plot_summary — サブパネル helpers
# ===========================================================================

def _plot_qea_vs_t(
    ax: plt.Axes,
    all_conds: dict[tuple[int, float], dict],
    ns: list[int],
    ts: list[float],
    colors: np.ndarray,
) -> None:
    """(1) q_EA vs T を描画する。"""
    ax.set_title("q_EA  vs  Temperature")
    for idx, N in enumerate(ns):
        qea_row, ts_valid = [], []
        for T in ts:
            cond = all_conds.get((N, T))
            if cond is None:
                continue
            qea_row.append(compute_qea(cond))
            ts_valid.append(T)
        ax.plot(ts_valid, qea_row, "o-", color=colors[idx],
                linewidth=1.8, markersize=6, label=f"N={N}")
    ax.set_xlabel("Temperature  T")
    ax.set_ylabel(r"$q_{EA}$")
    ax.set_ylim(0.4, 1.02)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)


def _plot_pm_rate_vs_t(
    ax: plt.Axes,
    all_conds: dict[tuple[int, float], dict],
    ns: list[int],
    ts: list[float],
    colors: np.ndarray,
) -> None:
    """(2) PM率 vs T を描画する。"""
    ax.set_title("PM rate  vs  Temperature\n(no_move_catchall fraction)")
    for idx, N in enumerate(ns):
        pm_row, ts_valid = [], []
        for T in ts:
            cond = all_conds.get((N, T))
            if cond is None:
                continue
            pm_row.append(cond["pm_rate"])
            ts_valid.append(T)
        ax.plot(ts_valid, pm_row, "s-", color=colors[idx],
                linewidth=1.8, markersize=6, label=f"N={N}")
    ax.axhline(0.5, color="gray", ls="--", alpha=0.6, label="50%")
    ax.set_xlabel("Temperature  T")
    ax.set_ylabel("PM rate  (no_move_catchall)")
    ax.set_ylim(-0.05, 1.05)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)


def _plot_autocorr(
    ax: plt.Axes,
    all_conds: dict[tuple[int, float], dict],
    ns: list[int],
    ts: list[float],
) -> None:
    """(3) 時間自己相関 C(Δt) を代表条件で描画する。"""
    ax.set_title(r"Time autocorrelation  $C(\Delta t)$")
    T_lo  = ts[len(ts) // 4]
    T_mid = ts[len(ts) // 2]
    T_hi  = ts[-1]
    N_lo  = ns[0]
    N_hi  = ns[-1]
    palette = ["#1f77b4", "#ff7f0e", "#d62728", "#9467bd"]
    rep_conds = [
        (N_lo,  T_lo,  f"N={N_lo}  T={T_lo}",  palette[0]),
        (N_lo,  T_hi,  f"N={N_lo}  T={T_hi}",  palette[2]),
        (N_hi,  T_lo,  f"N={N_hi}  T={T_lo}",  palette[1]),
        (N_hi,  T_mid, f"N={N_hi}  T={T_mid}", palette[3]),
    ]
    max_lag = 8
    for N, T, label, color in rep_conds:
        cond = all_conds.get((N, T))
        if cond is None:
            continue
        C = compute_autocorr(cond, max_lag=max_lag)
        lags = np.arange(1, max_lag + 1)
        valid = ~np.isnan(C)
        if valid.any():
            ax.plot(lags[valid], C[valid], "o-", color=color,
                    linewidth=1.8, markersize=6, label=label)
    ax.set_xlabel(r"$\Delta t$  (move steps)")
    ax.set_ylabel(r"$C(\Delta t)$")
    ax.set_ylim(0.4, 1.02)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)


def _plot_phase_heatmap(
    ax: plt.Axes,
    all_conds: dict[tuple[int, float], dict],
    ns: list[int],
    ts: list[float],
) -> None:
    """(4) 相分類ヒートマップを描画する。"""
    ax.set_title("Phase classification")
    phase_to_int = {"ordered": 3, "spin_glass": 2, "mixed": 1, "paramagnetic": 0}
    int_to_label = {3: "ordered", 2: "spin glass", 1: "mixed", 0: "paramagnetic"}
    cmap_phases  = plt.cm.colors.ListedColormap(
        [PHASE_COLORS["paramagnetic"], PHASE_COLORS["mixed"],
         PHASE_COLORS["spin_glass"],   PHASE_COLORS["ordered"]]
    )

    mat = np.full((len(ns), len(ts)), np.nan)
    for i, N in enumerate(ns):
        for j, T in enumerate(ts):
            cond = all_conds.get((N, T))
            if cond is None:
                continue
            acc   = float(np.mean(cond["accuracy"])) if cond["accuracy"] else 0.0
            qea   = compute_qea(cond)
            fb    = sum(cond["is_fallback"]) / cond["n_trials"]
            phase = classify_phase(qea, cond["pm_rate"], fb, acc)
            mat[i, j] = phase_to_int[phase]

    im = ax.imshow(mat, aspect="auto", origin="lower",
                   vmin=-0.5, vmax=3.5, cmap=cmap_phases,
                   extent=[ts[0]-0.1, ts[-1]+0.1, ns[0]-0.5, ns[-1]+0.5])
    cbar = plt.colorbar(im, ax=ax, ticks=[0, 1, 2, 3])
    cbar.ax.set_yticklabels([int_to_label[i] for i in [0, 1, 2, 3]], fontsize=8)
    ax.set_xlabel("Temperature  T")
    ax.set_ylabel("Disk count  N")
    ax.set_yticks(ns)
    ax.set_xticks(ts)
    ax.tick_params(axis="x", rotation=45)


def plot_summary(
    all_conds: dict[tuple[int, float], dict],
    ns: list[int],
    ts: list[float],
    out_path: Path,
    layer: str = LAYER_DEFAULT,
) -> None:
    """
    4 パネルのサマリー図を生成する:
      (1) q_EA vs T（各 N）
      (2) fallback 率 vs T（各 N）
      (3) C(Δt) — 代表条件（spin glass / paramagnetic）
      (4) 相分類ヒートマップ
    """
    fig = plt.figure(figsize=(14, 10))
    gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.38, wspace=0.32)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[1, 0])
    ax4 = fig.add_subplot(gs[1, 1])

    fig.suptitle(f"P(q) Analysis Summary  ({layer})", fontsize=13)
    colors = plt.cm.tab10(np.linspace(0, 0.6, len(ns)))

    _plot_qea_vs_t(ax1, all_conds, ns, ts, colors)
    _plot_pm_rate_vs_t(ax2, all_conds, ns, ts, colors)
    _plot_autocorr(ax3, all_conds, ns, ts)
    _plot_phase_heatmap(ax4, all_conds, ns, ts)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"[SAVE] {out_path}")
    plt.close(fig)


# ===========================================================================
# print_report — セクション helpers
# ===========================================================================

def _print_main_table(
    all_conds: dict[tuple[int, float], dict],
    ns: list[int],
    ts: list[float],
) -> None:
    """精度・q_EA・pm率・相分類のテーブルを出力する。"""
    header = f"{'N':>3} {'T':>5} | {'q_EA':>6} | {'q̄_inter':>8} | {'q_std':>6} | {'pm%':>5} | {'acc':>5} | phase"
    print(header)
    print("-" * len(header))

    for N in ns:
        for T in ts:
            cond = all_conds.get((N, T))
            if cond is None:
                continue
            q_vals = compute_pq(cond)
            qea    = compute_qea(cond)
            acc    = float(np.mean(cond["accuracy"])) if cond["accuracy"] else 0.0
            pm     = cond["pm_rate"]
            fb     = sum(cond["is_fallback"]) / cond["n_trials"]
            phase  = classify_phase(qea, pm, fb, acc)

            q_mean = np.nanmean(q_vals)
            q_std  = np.nanstd(q_vals)
            qea_s  = f"{qea:.3f}" if not np.isnan(qea) else "  nan"
            pm_s   = f"{pm:.0%}" if not np.isnan(pm) else " N/A"

            print(f"{N:>3} {T:>5.1f} | {qea_s:>6} | {q_mean:>8.4f} | {q_std:>6.4f}"
                  f" | {pm_s:>5} | {acc:>5.2f} | {phase}")
        print()


def _print_transition_temperatures(
    all_conds: dict[tuple[int, float], dict],
    ns: list[int],
    ts: list[float],
) -> None:
    """SG→PM 遷移温度（PM率=50%交差点）を出力する。"""
    print(f"\n{'='*80}")
    print("  崩壊モード遷移温度 T_SG→PM（PM率 = 50% 交差点、no_move_catchall 基準）")
    print(f"{'='*80}")
    for N in ns:
        pm_vals, ts_valid = [], []
        for T in ts:
            cond = all_conds.get((N, T))
            if cond is None:
                continue
            pm = cond["pm_rate"]
            if np.isnan(pm):
                continue
            pm_vals.append(pm)
            ts_valid.append(T)

        T_trans = _find_crossing(pm_vals, ts_valid, threshold=0.5)

        if T_trans is not None:
            print(f"  N={N}: T_{{SG→PM}} ≈ {T_trans:.2f}")
        else:
            pm_max = max(pm_vals) if pm_vals else float("nan")
            print(f"  N={N}: 遷移が範囲内に見つからない（PM率最大={pm_max:.0%}）")


def _find_crossing(vals: list[float], xs: list[float], threshold: float) -> Optional[float]:
    """
    vals が threshold を下から上へ超える点を線形補間で求める。
    見つからない場合は None を返す。
    """
    for j in range(len(xs) - 1):
        if vals[j] < threshold <= vals[j + 1]:
            slope = (vals[j+1] - vals[j]) / (xs[j+1] - xs[j])
            return xs[j] + (threshold - vals[j]) / slope
    return None


# ===========================================================================
# コンソールレポート
# ===========================================================================

def print_report(
    all_conds: dict[tuple[int, float], dict],
    ns: list[int],
    ts: list[float],
) -> None:
    print(f"\n{'='*80}")
    print("  P(q) Analysis Report")
    print(f"{'='*80}")

    _print_main_table(all_conds, ns, ts)
    _print_transition_temperatures(all_conds, ns, ts)


# ===========================================================================
# エントリポイント
# ===========================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P(q) overlap 分布によるスピングラス・常磁性相の判別"
    )
    parser.add_argument("--dir",   type=str, default="results/hanoi/pq_sweep",
                        help="pq_sweep 結果ディレクトリ")
    parser.add_argument("--layer", type=str, default=LAYER_DEFAULT,
                        help="解析対象レイヤー (default: layer_m8)")
    parser.add_argument("--ns",    type=int, nargs="+", default=NS_DEFAULT)
    parser.add_argument("--ts",    type=float, nargs="+", default=TS_DEFAULT)
    parser.add_argument("--out-dist",    type=str, default="figures/pq_dist.png",
                        help="P(q) 分布グリッド図の出力先")
    parser.add_argument("--out-summary", type=str, default="figures/pq_summary.png",
                        help="サマリー4パネル図の出力先")
    return parser.parse_args()


def main() -> None:
    args     = parse_args()
    base_dir = Path(args.dir)
    layer    = args.layer

    print(f"[INFO] データロード中: {base_dir}  layer={layer}")

    all_conds: dict[tuple[int, float], dict] = {}
    for N in args.ns:
        for T in args.ts:
            cond = load_condition(base_dir, N, T, layer)
            if cond is not None:
                all_conds[(N, T)] = cond

    if not all_conds:
        print("[ERROR] データが見つかりません。run_pq_sweep.sh を先に実行してください。")
        return

    print(f"[INFO] {len(all_conds)} 条件をロードしました。")

    print_report(all_conds, args.ns, args.ts)
    plot_pq_distributions(all_conds, args.ns, args.ts, Path(args.out_dist), layer=layer)
    plot_summary(all_conds, args.ns, args.ts, Path(args.out_summary), layer=layer)

    print("\n[DONE]")
    print(f"  P(q) 分布グリッド : {args.out_dist}")
    print(f"  サマリー4パネル   : {args.out_summary}")


if __name__ == "__main__":
    main()
