"""
analyze_phase_diagram.py — 案A フルグリッドスイープの可視化・解析

(N, T) 2次元グリッドの accuracy から秩序-無秩序相図を描き、
相境界 T_c(N) を推定する。案B・案C への橋渡しとなる解析を行う。

使用例:
  python3 analyze_phase_diagram.py
  python3 analyze_phase_diagram.py --dir results/hanoi/phase_diagram --out figures/phase_diagram.png
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

# ===========================================================================
# 定数
# ===========================================================================

NS_DEFAULT: list[int]   = [2, 3, 4, 5, 6]
TS_DEFAULT: list[float] = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0]

# 相境界の閾値（accuracy がこの値を下回ったら崩壊相とみなす）
BOUNDARY_THRESHOLD = 0.5


# ===========================================================================
# データロード・統計
# ===========================================================================

def load_all(base_dir: Path, ns: list[int], ts: list[float]) -> dict[tuple[int, float], list[dict]]:
    """全 (N, T) セルの summary.json を読み込む。"""
    data: dict[tuple[int, float], list[dict]] = {}
    for N in ns:
        for T in ts:
            tag  = f"{T:.1f}".replace(".", "_")
            path = base_dir / f"N{N}_T{tag}" / "summary.json"
            if not path.exists():
                continue
            with open(path) as f:
                data[(N, T)] = json.load(f)
    return data


def compute_stats(trials: list[dict]) -> dict:
    """1セル分の統計量を返す。"""
    acc  = [r["accuracy"]     for r in trials]
    tok  = [r["total_tokens"] for r in trials]
    v    = [r["v_score"]      for r in trials]
    es: dict[str, int] = {}
    for r in trials:
        k = r.get("early_stop") or "none"
        es[k] = es.get(k, 0) + 1
    return {
        "accuracy_mean": float(np.mean(acc)),
        "accuracy_std":  float(np.std(acc)),
        "token_mean":    float(np.mean(tok)),
        "token_std":     float(np.std(tok)),
        "v_mean":        float(np.mean(v)),
        "v_std":         float(np.std(v)),
        "n_trials":      len(trials),
        "early_stop":    es,
    }


def build_matrix(
    stats: dict[tuple[int, float], dict],
    ns: list[int],
    ts: list[float],
    key: str,
) -> np.ndarray:
    """(N, T) グリッドを ndarray に変換する。行=N, 列=T。欠損は nan。"""
    mat = np.full((len(ns), len(ts)), np.nan)
    for i, N in enumerate(ns):
        for j, T in enumerate(ts):
            if (N, T) in stats:
                mat[i, j] = stats[(N, T)][key]
    return mat


# ===========================================================================
# 相境界推定
# ===========================================================================

def estimate_phase_boundary(
    acc_mat: np.ndarray,
    ns: list[int],
    ts: list[float],
    threshold: float = BOUNDARY_THRESHOLD,
) -> dict[int, float | None]:
    """
    各 N について accuracy が threshold を下回る最小の T（= T_c(N)）を推定する。

    線形補間で閾値交差点を求める。T が全域で threshold 以上なら None を返す。
    """
    boundary: dict[int, float | None] = {}
    for i, N in enumerate(ns):
        row = acc_mat[i, :]
        valid = ~np.isnan(row)
        if valid.sum() < 2:
            boundary[N] = None
            continue

        ts_v   = np.array(ts)[valid]
        row_v  = row[valid]

        # threshold を最初に下回るインターバルを探す
        Tc = None
        for j in range(len(ts_v) - 1):
            if row_v[j] >= threshold > row_v[j + 1]:
                # 線形補間
                slope = (row_v[j + 1] - row_v[j]) / (ts_v[j + 1] - ts_v[j])
                Tc    = ts_v[j] + (threshold - row_v[j]) / slope
                break
        boundary[N] = Tc
    return boundary


# ===========================================================================
# プロット
# ===========================================================================

def plot_phase_diagram(
    stats: dict[tuple[int, float], dict],
    ns: list[int],
    ts: list[float],
    boundary: dict[int, float | None],
    out_path: Path,
) -> None:
    """
    4 パネル図を生成する:
      (1) 相図ヒートマップ (accuracy)
      (2) 各 N の accuracy vs T カーブ
      (3) 各 N の token vs T カーブ
      (4) 相境界 T_c(N)
    """
    acc_mat = build_matrix(stats, ns, ts, "accuracy_mean")
    acc_std = build_matrix(stats, ns, ts, "accuracy_std")
    tok_mat = build_matrix(stats, ns, ts, "token_mean")
    tok_std = build_matrix(stats, ns, ts, "token_std")

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Inference Collapse Phase Diagram  (DeepSeek-R1-Distill-Qwen-7B)", fontsize=13)

    colors = plt.cm.tab10(np.linspace(0, 0.6, len(ns)))

    # -----------------------------------------------------------------------
    # (1) 相図ヒートマップ
    # -----------------------------------------------------------------------
    ax = axes[0, 0]
    cmap = mcolors.LinearSegmentedColormap.from_list(
        "order_disorder", ["#d62728", "#ffffff", "#1f77b4"]
    )
    im = ax.imshow(
        acc_mat, aspect="auto", origin="lower",
        vmin=0.0, vmax=1.0, cmap=cmap,
        extent=[ts[0] - 0.1, ts[-1] + 0.1, ns[0] - 0.5, ns[-1] + 0.5],
    )
    plt.colorbar(im, ax=ax, label="Accuracy  m(N, T)")

    # 相境界を重ねてプロット
    bc_ns  = [N for N in ns if boundary.get(N) is not None]
    bc_Tcs = [boundary[N] for N in bc_ns]
    if bc_ns:
        ax.plot(bc_Tcs, bc_ns, "k--o", linewidth=2, markersize=7, label=r"$T_c(N)$  boundary")
        ax.legend(fontsize=9)

    ax.set_xlabel("Temperature  T")
    ax.set_ylabel("Disk count  N")
    ax.set_title("Phase Diagram  (accuracy heatmap)")
    ax.set_yticks(ns)
    ax.set_xticks(ts)
    ax.tick_params(axis="x", rotation=45)

    # -----------------------------------------------------------------------
    # (2) Accuracy vs T  (各 N)
    # -----------------------------------------------------------------------
    ax = axes[0, 1]
    for i, N in enumerate(ns):
        row    = acc_mat[i, :]
        row_s  = acc_std[i, :]
        valid  = ~np.isnan(row)
        ts_v   = np.array(ts)[valid]
        ax.errorbar(ts_v, row[valid], yerr=row_s[valid],
                    fmt="o-", capsize=4, color=colors[i],
                    linewidth=1.8, markersize=6, label=f"N={N}")
    ax.axhline(y=BOUNDARY_THRESHOLD, color="gray", linestyle="--",
               alpha=0.6, label=f"threshold={BOUNDARY_THRESHOLD}")
    ax.set_xlabel("Temperature  T")
    ax.set_ylabel("Accuracy")
    ax.set_title("Accuracy vs Temperature  (per N)")
    ax.set_ylim(-0.05, 1.05)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # -----------------------------------------------------------------------
    # (3) Total Tokens vs T  (各 N)
    # -----------------------------------------------------------------------
    ax = axes[1, 0]
    for i, N in enumerate(ns):
        row   = tok_mat[i, :]
        row_s = tok_std[i, :]
        valid = ~np.isnan(row)
        ts_v  = np.array(ts)[valid]
        ax.errorbar(ts_v, row[valid], yerr=row_s[valid],
                    fmt="s-", capsize=4, color=colors[i],
                    linewidth=1.8, markersize=6, label=f"N={N}")
    ax.set_xlabel("Temperature  T")
    ax.set_ylabel("Total Tokens")
    ax.set_title("Total Tokens vs Temperature  (per N)")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    # -----------------------------------------------------------------------
    # (4) 相境界 T_c(N)
    # -----------------------------------------------------------------------
    ax = axes[1, 1]
    bc_ns_plot  = [N for N in ns if boundary.get(N) is not None]
    bc_Tcs_plot = [boundary[N] for N in bc_ns_plot]

    if bc_ns_plot:
        ax.plot(bc_ns_plot, bc_Tcs_plot, "ko-", linewidth=2,
                markersize=9, zorder=5, label=r"$T_c(N)$  (interpolated)")

        # 指数・冪乗フィットを試みる（点が3つ以上あれば）
        if len(bc_ns_plot) >= 3:
            ns_arr  = np.array(bc_ns_plot, dtype=float)
            Tcs_arr = np.array(bc_Tcs_plot, dtype=float)

            # 冪乗則フィット: T_c = a * N^(-alpha)
            try:
                coeffs = np.polyfit(np.log(ns_arr), np.log(Tcs_arr), 1)
                alpha  = -coeffs[0]
                a      = np.exp(coeffs[1])
                ns_fine = np.linspace(ns_arr[0], ns_arr[-1], 100)
                ax.plot(ns_fine, a * ns_fine ** (-alpha), "r--",
                        linewidth=1.5,
                        label=fr"Power law: $T_c \propto N^{{-{alpha:.2f}}}$")
            except Exception:
                pass

            # 指数則フィット: T_c = a * exp(-beta * N)
            try:
                coeffs2 = np.polyfit(ns_arr, np.log(Tcs_arr), 1)
                beta    = -coeffs2[0]
                a2      = np.exp(coeffs2[1])
                ax.plot(ns_fine, a2 * np.exp(-beta * ns_fine), "b-.",
                        linewidth=1.5,
                        label=fr"Exp law: $T_c \propto e^{{-{beta:.2f}N}}$")
            except Exception:
                pass

    ax.set_xlabel("Disk count  N")
    ax.set_ylabel(r"$T_c(N)$")
    ax.set_title(r"Phase Boundary $T_c(N)$")
    ax.set_xticks(ns)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"[SAVE] {out_path}")
    plt.close(fig)


# ===========================================================================
# コンソールレポート
# ===========================================================================

def print_report(
    stats: dict[tuple[int, float], dict],
    ns: list[int],
    ts: list[float],
    boundary: dict[int, float | None],
) -> None:
    """相図のサマリーテーブルと相境界の考察をコンソールに出力する。"""
    print(f"\n{'='*75}")
    print(f"  Phase Diagram Report")
    print(f"{'='*75}")

    # 精度テーブル
    header = f"{'N':>3} |" + "".join(f"  T={T:<4}" for T in ts)
    print(header)
    print("-" * len(header))
    for N in ns:
        row_str = f"{N:>3} |"
        for T in ts:
            if (N, T) in stats:
                acc = stats[(N, T)]["accuracy_mean"]
                row_str += f"  {acc:.2f}  "
            else:
                row_str += "   --   "
        print(row_str)

    # 相境界
    print(f"\n{'='*75}")
    print(f"  推定相境界 T_c(N)  (accuracy = {BOUNDARY_THRESHOLD} 交差点)")
    print(f"{'='*75}")
    for N in ns:
        Tc = boundary.get(N)
        if Tc is None:
            print(f"  N={N}: T_c > {max(ts):.1f}  (全温度域で acc >= {BOUNDARY_THRESHOLD})")
        else:
            print(f"  N={N}: T_c ≈ {Tc:.2f}")

    # Early stop 崩壊モード分析
    print(f"\n{'='*75}")
    print(f"  Early Stop 崩壊モード内訳")
    print(f"{'='*75}")
    for N in ns:
        print(f"  N={N}:")
        for T in ts:
            if (N, T) not in stats:
                continue
            es = stats[(N, T)]["early_stop"]
            total = sum(es.values())
            breakdown = "  ".join(f"{k}:{v}/{total}" for k, v in sorted(es.items()))
            print(f"    T={T:.1f}: {breakdown}")

    # 案B・案C への示唆
    print(f"\n{'='*75}")
    print(f"  次ステップへの示唆")
    print(f"{'='*75}")
    bc_ns  = [N for N in ns if boundary.get(N) is not None]
    bc_Tcs = [boundary[N] for N in bc_ns]
    if len(bc_ns) >= 2:
        print(f"  [案B] 相境界付近で trials を増やして T_c(N) を精密化:")
        for N, Tc in zip(bc_ns, bc_Tcs):
            print(f"    N={N}: T ∈ [{max(0.1, Tc-0.3):.1f}, {Tc+0.3:.1f}] で追加測定推奨")
        print(f"  [案C] 隠れ状態解析の優先ターゲット:")
        for N, Tc in zip(bc_ns, bc_Tcs):
            print(f"    N={N}: T={Tc:.1f} 付近（臨界点）で phi(t), norm(t) の揺動を確認")
    else:
        print(f"  データが不足しています。まず run_phase_diagram.sh を完走させてください。")


# ===========================================================================
# エントリポイント
# ===========================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="案A フルグリッドスイープ結果の可視化・相境界推定"
    )
    parser.add_argument("--dir",       type=str, default="results/hanoi/phase_diagram")
    parser.add_argument("--out",       type=str, default="figures/phase_diagram.png")
    parser.add_argument("--ns",        type=int, nargs="+", default=NS_DEFAULT)
    parser.add_argument("--ts",        type=float, nargs="+", default=TS_DEFAULT)
    parser.add_argument("--threshold", type=float, default=BOUNDARY_THRESHOLD,
                        help=f"相境界とみなす accuracy 閾値 (default: {BOUNDARY_THRESHOLD})")
    return parser.parse_args()


def main() -> None:
    args     = parse_args()
    base_dir = Path(args.dir)
    out_path = Path(args.out)

    print(f"[INFO] データ読み込み中: {base_dir}")
    raw = load_all(base_dir, args.ns, args.ts)
    if not raw:
        print("[ERROR] 結果ファイルが見つかりません。run_phase_diagram.sh を先に実行してください。")
        return

    stats    = {k: compute_stats(v) for k, v in raw.items()}
    boundary = estimate_phase_boundary(
        build_matrix(stats, args.ns, args.ts, "accuracy_mean"),
        args.ns, args.ts, args.threshold,
    )

    print_report(stats, args.ns, args.ts, boundary)
    plot_phase_diagram(stats, args.ns, args.ts, boundary, out_path)


if __name__ == "__main__":
    main()
