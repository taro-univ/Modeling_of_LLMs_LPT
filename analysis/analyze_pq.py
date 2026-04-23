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
    summary_path = cdir / "summary.json"
    if not cdir.exists():
        return None

    summary = []
    if summary_path.exists():
        with open(summary_path) as f:
            summary = json.load(f)

    hidden_list: list[np.ndarray] = []
    is_fallback_list: list[bool]  = []

    npz_files = sorted(cdir.glob("trial_*_hidden.npz"))
    for i, npz_path in enumerate(npz_files):
        d = np.load(npz_path, allow_pickle=True)
        if layer not in d:
            continue
        H = d[layer].astype(np.float32)           # (steps, D)
        texts = list(d["move_texts"])
        is_fb = (len(texts) > 0 and texts[0] == "__fallback__")

        hidden_list.append(H)
        is_fallback_list.append(is_fb)

    if not hidden_list:
        return None

    accuracy   = [r["accuracy"]              for r in summary] if summary else []
    early_stop = [r.get("early_stop")        for r in summary] if summary else []

    return {
        "hidden":      hidden_list,
        "is_fallback": is_fallback_list,
        "accuracy":    accuracy,
        "early_stop":  early_stop,
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


def classify_phase(q_ea: float, fallback_rate: float, accuracy: float) -> str:
    """q_EA と fallback 率から相を大まかに分類する。"""
    if accuracy > 0.4:
        return "ordered"
    if fallback_rate > 0.6:
        return "paramagnetic"
    if not np.isnan(q_ea) and q_ea > 0.70:
        return "spin_glass"
    return "mixed"


# ===========================================================================
# メイン描画
# ===========================================================================

def plot_pq_distributions(
    all_conds: dict[tuple[int, float], dict],
    ns: list[int],
    ts: list[float],
    out_path: Path,
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
    fig.suptitle("P(q) Overlap Distribution  (layer_m8)", fontsize=12, y=1.01)

    for i, N in enumerate(ns):
        for j, T in enumerate(ts):
            ax = axes[i][j] if len(ns) > 1 else axes[j]
            cond = all_conds.get((N, T))

            if cond is None:
                ax.text(0.5, 0.5, "N/A", ha="center", va="center",
                        transform=ax.transAxes, fontsize=8, color="gray")
                ax.set_xticks([])
                ax.set_yticks([])
                continue

            q_vals = compute_pq(cond)
            fb_rate = sum(cond["is_fallback"]) / cond["n_trials"]
            acc = float(np.mean(cond["accuracy"])) if cond["accuracy"] else 0.0
            q_ea = compute_qea(cond)
            phase = classify_phase(q_ea, fb_rate, acc)
            color = PHASE_COLORS[phase]

            ax.hist(q_vals, bins=Q_BINS, color=color, alpha=0.75, density=True)
            ax.axvline(np.nanmean(q_vals), color="k", lw=1.2, ls="--", alpha=0.7)

            label = f"q̄={np.nanmean(q_vals):.2f}\nfb={fb_rate:.0%}"
            ax.text(0.04, 0.93, label, transform=ax.transAxes,
                    fontsize=6, va="top", color="black")

            if i == 0:
                ax.set_title(f"T={T}", fontsize=8)
            if j == 0:
                ax.set_ylabel(f"N={N}", fontsize=8)
            ax.set_xlim(-0.1, 1.05)
            ax.tick_params(labelsize=6)

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


def plot_summary(
    all_conds: dict[tuple[int, float], dict],
    ns: list[int],
    ts: list[float],
    out_path: Path,
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

    fig.suptitle("P(q) Analysis Summary  (pq_sweep, layer_m8)", fontsize=13)
    colors = plt.cm.tab10(np.linspace(0, 0.6, len(ns)))

    # --- (1) q_EA vs T ---
    ax1.set_title("q_EA  vs  Temperature")
    for idx, N in enumerate(ns):
        qea_row, ts_valid = [], []
        for T in ts:
            cond = all_conds.get((N, T))
            if cond is None:
                continue
            qea = compute_qea(cond)
            qea_row.append(qea)
            ts_valid.append(T)
        ax1.plot(ts_valid, qea_row, "o-", color=colors[idx],
                 linewidth=1.8, markersize=6, label=f"N={N}")
    ax1.set_xlabel("Temperature  T")
    ax1.set_ylabel(r"$q_{EA}$")
    ax1.set_ylim(0.4, 1.02)
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)

    # --- (2) fallback 率 vs T ---
    ax2.set_title("Fallback rate  vs  Temperature\n(paramagnetic phase indicator)")
    for idx, N in enumerate(ns):
        fb_row, ts_valid = [], []
        for T in ts:
            cond = all_conds.get((N, T))
            if cond is None:
                continue
            fb = sum(cond["is_fallback"]) / cond["n_trials"]
            fb_row.append(fb)
            ts_valid.append(T)
        ax2.plot(ts_valid, fb_row, "s-", color=colors[idx],
                 linewidth=1.8, markersize=6, label=f"N={N}")
    ax2.axhline(0.5, color="gray", ls="--", alpha=0.6, label="50%")
    ax2.set_xlabel("Temperature  T")
    ax2.set_ylabel("Fallback rate")
    ax2.set_ylim(-0.05, 1.05)
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)

    # --- (3) C(Δt) — 代表条件 ---
    ax3.set_title(r"Time autocorrelation  $C(\Delta t)$")
    rep_conds = [
        (5, 0.2, "N5 T=0.2  [spin glass]",   "#ff7f0e"),
        (3, 0.2, "N3 T=0.2  [ordered]",       "#1f77b4"),
        (3, 1.5, "N3 T=1.5  [paramagnetic]",  "#d62728"),
        (4, 0.8, "N4 T=0.8  [mixed]",         "#9467bd"),
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
            ax3.plot(lags[valid], C[valid], "o-", color=color,
                     linewidth=1.8, markersize=6, label=label)
    ax3.set_xlabel(r"$\Delta t$  (move steps)")
    ax3.set_ylabel(r"$C(\Delta t)$")
    ax3.set_ylim(0.4, 1.02)
    ax3.legend(fontsize=8)
    ax3.grid(True, alpha=0.3)

    # --- (4) 相分類ヒートマップ ---
    ax4.set_title("Phase classification")
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
            fb   = sum(cond["is_fallback"]) / cond["n_trials"]
            acc  = float(np.mean(cond["accuracy"])) if cond["accuracy"] else 0.0
            qea  = compute_qea(cond)
            phase = classify_phase(qea, fb, acc)
            mat[i, j] = phase_to_int[phase]

    im = ax4.imshow(mat, aspect="auto", origin="lower",
                    vmin=-0.5, vmax=3.5, cmap=cmap_phases,
                    extent=[ts[0]-0.1, ts[-1]+0.1, ns[0]-0.5, ns[-1]+0.5])
    cbar = plt.colorbar(im, ax=ax4, ticks=[0, 1, 2, 3])
    cbar.ax.set_yticklabels([int_to_label[i] for i in [0, 1, 2, 3]], fontsize=8)
    ax4.set_xlabel("Temperature  T")
    ax4.set_ylabel("Disk count  N")
    ax4.set_yticks(ns)
    ax4.set_xticks(ts)
    ax4.tick_params(axis="x", rotation=45)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"[SAVE] {out_path}")
    plt.close(fig)


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

    header = f"{'N':>3} {'T':>5} | {'q_EA':>6} | {'q̄_inter':>8} | {'q_std':>6} | {'fb%':>5} | {'acc':>5} | phase"
    print(header)
    print("-" * len(header))

    for N in ns:
        for T in ts:
            cond = all_conds.get((N, T))
            if cond is None:
                continue
            q_vals = compute_pq(cond)
            qea    = compute_qea(cond)
            fb     = sum(cond["is_fallback"]) / cond["n_trials"]
            acc    = float(np.mean(cond["accuracy"])) if cond["accuracy"] else 0.0
            phase  = classify_phase(qea, fb, acc)

            q_mean = np.nanmean(q_vals)
            q_std  = np.nanstd(q_vals)
            qea_s  = f"{qea:.3f}" if not np.isnan(qea) else "  nan"

            print(f"{N:>3} {T:>5.1f} | {qea_s:>6} | {q_mean:>8.4f} | {q_std:>6.4f}"
                  f" | {fb:>4.0%} | {acc:>5.2f} | {phase}")
        print()

    # スピングラス・常磁性の境界推定
    print(f"\n{'='*80}")
    print("  崩壊モード遷移温度 T_SG→PM（fallback率 = 50% 交差点）")
    print(f"{'='*80}")
    for N in ns:
        fb_vals, ts_valid = [], []
        for T in ts:
            cond = all_conds.get((N, T))
            if cond is None:
                continue
            fb = sum(cond["is_fallback"]) / cond["n_trials"]
            fb_vals.append(fb)
            ts_valid.append(T)

        T_trans = None
        for j in range(len(ts_valid) - 1):
            if fb_vals[j] < 0.5 <= fb_vals[j + 1]:
                slope  = (fb_vals[j+1] - fb_vals[j]) / (ts_valid[j+1] - ts_valid[j])
                T_trans = ts_valid[j] + (0.5 - fb_vals[j]) / slope
                break

        if T_trans is not None:
            print(f"  N={N}: T_{{SG→PM}} ≈ {T_trans:.2f}")
        else:
            print(f"  N={N}: 遷移が範囲内に見つからない（fb最大={max(fb_vals):.0%}）")


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
                        choices=["layer_m1", "layer_m8", "layer_m16"],
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
    plot_pq_distributions(all_conds, args.ns, args.ts, Path(args.out_dist))
    plot_summary(all_conds, args.ns, args.ts, Path(args.out_summary))

    print("\n[DONE]")
    print(f"  P(q) 分布グリッド : {args.out_dist}")
    print(f"  サマリー4パネル   : {args.out_summary}")


if __name__ == "__main__":
    main()
