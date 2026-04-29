"""
analyze_temp_sweep.py — Temperature sweep 結果の可視化・考察

Accuracy vs T, Token vs T をプロットし、
N=4 以降のモデル構築に向けた最適温度を特定する。

使用例:
  python3 analyze_temp_sweep.py
  python3 analyze_temp_sweep.py --N 3 --out figures/temp_sweep_N3.png
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np


TEMPERATURES = [0.2, 0.3, 0.4, 0.5, 0.6]


def load_results(base_dir: Path, N: int) -> dict[float, list[dict]]:
    """各温度の summary.json を読み込んで返す。"""
    data: dict[float, list[dict]] = {}
    for T in TEMPERATURES:
        tag = f"{T:.1f}".replace(".", "_")
        path = base_dir / f"N{N}_T{tag}" / "summary.json"
        if not path.exists():
            print(f"[WARN] 見つかりません: {path}")
            continue
        with open(path) as f:
            data[T] = json.load(f)
    return data


def compute_stats(trials: list[dict]) -> dict:
    """1温度分の統計量を計算する。"""
    n = len(trials)
    acc   = [r["accuracy"]         for r in trials]
    tok   = [r["total_tokens"]     for r in trials]
    reas  = [r["reasoning_tokens"] for r in trials]
    v     = [r["v_score"]          for r in trials]

    es_counts: dict[str, int] = {}
    for r in trials:
        key = r.get("early_stop") or "none"
        es_counts[key] = es_counts.get(key, 0) + 1

    return {
        "accuracy_mean":  np.mean(acc),
        "accuracy_std":   np.std(acc),
        "token_mean":     np.mean(tok),
        "token_std":      np.std(tok),
        "reasoning_mean": np.mean(reas),
        "reasoning_std":  np.std(reas),
        "v_mean":         np.mean(v),
        "v_std":          np.std(v),
        "n_trials":       n,
        "early_stop":     es_counts,
    }


def plot_sweep(
    stats_by_T: dict[float, dict],
    N: int,
    out_path: Path,
) -> None:
    """Accuracy / Token / V(x) vs Temperature を 3 段プロットで保存する。"""
    Ts      = sorted(stats_by_T.keys())
    acc_m   = [stats_by_T[T]["accuracy_mean"]  for T in Ts]
    acc_s   = [stats_by_T[T]["accuracy_std"]   for T in Ts]
    tok_m   = [stats_by_T[T]["token_mean"]     for T in Ts]
    tok_s   = [stats_by_T[T]["token_std"]      for T in Ts]
    v_m     = [stats_by_T[T]["v_mean"]         for T in Ts]
    v_s     = [stats_by_T[T]["v_std"]          for T in Ts]

    fig = plt.figure(figsize=(8, 10))
    gs  = gridspec.GridSpec(3, 1, hspace=0.45)

    # --- Accuracy vs T ---
    ax1 = fig.add_subplot(gs[0])
    ax1.errorbar(Ts, acc_m, yerr=acc_s, fmt="o-", capsize=5,
                 color="steelblue", linewidth=2, markersize=7)
    ax1.set_xlabel("Temperature")
    ax1.set_ylabel("Accuracy")
    ax1.set_title(f"N={N}  Accuracy vs Temperature")
    ax1.set_ylim(-0.05, 1.05)
    ax1.set_xticks(Ts)
    ax1.axhline(y=np.mean(acc_m), color="gray", linestyle="--", alpha=0.5,
                label=f"mean={np.mean(acc_m):.2f}")
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)

    # --- Total Tokens vs T ---
    ax2 = fig.add_subplot(gs[1])
    ax2.errorbar(Ts, tok_m, yerr=tok_s, fmt="s-", capsize=5,
                 color="coral", linewidth=2, markersize=7)
    ax2.set_xlabel("Temperature")
    ax2.set_ylabel("Total Tokens")
    ax2.set_title(f"N={N}  Total Tokens vs Temperature")
    ax2.set_xticks(Ts)
    ax2.grid(True, alpha=0.3)

    # --- V(x) vs T ---
    ax3 = fig.add_subplot(gs[2])
    ax3.errorbar(Ts, v_m, yerr=v_s, fmt="^-", capsize=5,
                 color="seagreen", linewidth=2, markersize=7)
    ax3.set_xlabel("Temperature")
    ax3.set_ylabel("V(x) score  (0=goal, 1=initial)")
    ax3.set_title(f"N={N}  Inference Potential V(x) vs Temperature")
    ax3.set_xticks(Ts)
    ax3.axhline(y=0.0, color="gray", linestyle="--", alpha=0.5)
    ax3.grid(True, alpha=0.3)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"[SAVE] {out_path}")
    plt.close(fig)


def print_report(stats_by_T: dict[float, dict], N: int) -> None:
    """コンソールにサマリーテーブルと考察を出力する。"""
    print(f"\n{'='*65}")
    print(f"  Temperature Sweep Report  N={N}")
    print(f"{'='*65}")
    print(f"{'T':>6} {'Acc':>8} {'±':>6} {'Tokens':>8} {'±':>6} {'V(x)':>7} {'±':>6}")
    print(f"{'-'*65}")

    best_T_acc = max(stats_by_T, key=lambda T: stats_by_T[T]["accuracy_mean"])
    best_T_tok = min(stats_by_T, key=lambda T: stats_by_T[T]["token_mean"])

    for T in sorted(stats_by_T):
        s = stats_by_T[T]
        marker = " ← best acc" if T == best_T_acc else ""
        print(f"{T:>6.1f} "
              f"{s['accuracy_mean']:>8.3f} "
              f"{s['accuracy_std']:>6.3f} "
              f"{s['token_mean']:>8.1f} "
              f"{s['token_std']:>6.1f} "
              f"{s['v_mean']:>7.4f} "
              f"{s['v_std']:>6.4f}"
              f"{marker}")

    print(f"{'='*65}")

    # 考察
    s_best = stats_by_T[best_T_acc]
    s_low  = stats_by_T[min(stats_by_T)]
    s_high = stats_by_T[max(stats_by_T)]

    print(f"\n[考察]")
    print(f"  最高精度温度: T={best_T_acc}  accuracy={s_best['accuracy_mean']:.3f}")
    print(f"  低温(T={min(stats_by_T):.1f}): acc={s_low['accuracy_mean']:.3f}  "
          f"tokens={s_low['token_mean']:.0f}  "
          f"（決定論的寄り → ヒントへの追従度高）")
    print(f"  高温(T={max(stats_by_T):.1f}): acc={s_high['accuracy_mean']:.3f}  "
          f"tokens={s_high['token_mean']:.0f}  "
          f"（探索的 → 崩壊リスク上昇）")

    # N=4 以降への推奨
    # V(x) が最小 = ゴールに最も近い状態
    best_T_v = min(stats_by_T, key=lambda T: stats_by_T[T]["v_mean"])
    print(f"\n[N=4 以降への推奨温度]")
    print(f"  精度・V(x) 観点: T={best_T_acc}  →  few-shot の転移効果を最大化")
    print(f"  崩壊観測 観点 : T={max(stats_by_T):.1f}  →  高温で相転移が明確に現れやすい")
    print(f"  推奨: N=4,5 は T={best_T_acc} で正常相データを確保し、")
    print(f"        N=6,7 は T={max(stats_by_T):.1f} で崩壊相データを収集。")

    # Early stop 内訳
    print(f"\n[Early Stop 内訳]")
    for T in sorted(stats_by_T):
        es = stats_by_T[T]["early_stop"]
        print(f"  T={T:.1f}: {es}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--N",   type=int, default=3)
    parser.add_argument("--dir", type=str, default="results/hanoi/temp_sweep")
    parser.add_argument("--out", type=str, default=None)
    return parser.parse_args()


def main() -> None:
    args     = parse_args()
    base_dir = Path(args.dir)
    out_path = Path(args.out) if args.out else Path(f"figures/temp_sweep_N{args.N}.png")

    data = load_results(base_dir, args.N)
    if not data:
        print("[ERROR] 結果ファイルが見つかりません。run_temp_sweep.sh を先に実行してください。")
        return

    stats_by_T = {T: compute_stats(trials) for T, trials in data.items()}

    print_report(stats_by_T, args.N)
    plot_sweep(stats_by_T, args.N, out_path)


if __name__ == "__main__":
    main()
