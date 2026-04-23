"""
Hanoi Inference Collapse: accuracy and token usage vs. N (number of disks).

Usage:
    python plot_scaling.py --n_min 2 --n_max 5
    python plot_scaling.py --n_min 2 --n_max 5 --out figures/scaling.png
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TypedDict

import matplotlib.pyplot as plt
import numpy as np


# --------------------------------------------------------------------------- #
# データ構造
# --------------------------------------------------------------------------- #
class Trial(TypedDict):
    trial: int
    accuracy: int           # 0 or 1
    total_tokens: int
    reasoning_tokens: int
    moves_extracted: int
    v_score: float
    elapsed_sec: float


def load_results(data_dir: Path, n: int) -> list[Trial]:
    """results_N{n}_test.json を読み込んで返す。"""
    path = data_dir / f"results_N{n}_test.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} が見つかりません")
    with path.open() as f:
        return json.load(f)


def aggregate(trials: list[Trial]) -> dict[str, float]:
    """accuracy の平均・標準誤差、total_tokens の平均・標準誤差を計算する。"""
    accs = np.array([t["accuracy"] for t in trials], dtype=float)
    toks = np.array([t["total_tokens"] for t in trials], dtype=float)
    n = len(trials)
    return {
        "acc_mean": float(np.mean(accs)),
        "acc_sem": float(np.std(accs, ddof=1) / np.sqrt(n)) if n > 1 else 0.0,
        "tok_mean": float(np.mean(toks)),
        "tok_sem": float(np.std(toks, ddof=1) / np.sqrt(n)) if n > 1 else 0.0,
        "n_trials": n,
    }


# --------------------------------------------------------------------------- #
# プロット
# --------------------------------------------------------------------------- #
def plot(
    ns: list[int],
    stats: list[dict[str, float]],
    out: Path | None = None,
) -> None:
    """2 段パネル: 上=accuracy, 下=total_tokens。エラーバーは SEM。"""
    fig, axes = plt.subplots(2, 1, figsize=(6, 8), sharex=True)
    fig.suptitle("Hanoi Inference Collapse: Scaling with N", fontsize=14, y=0.98)

    x = np.array(ns)
    acc_means = np.array([s["acc_mean"] for s in stats])
    acc_sems  = np.array([s["acc_sem"]  for s in stats])
    tok_means = np.array([s["tok_mean"] for s in stats])
    tok_sems  = np.array([s["tok_sem"]  for s in stats])

    # ---- accuracy --------------------------------------------------------- #
    ax0 = axes[0]
    ax0.errorbar(
        x, acc_means, yerr=acc_sems,
        marker="o", linewidth=2, capsize=5, color="steelblue",
        label="accuracy (mean ± SEM)",
    )
    ax0.axhline(1.0, linestyle="--", color="gray", linewidth=0.8, alpha=0.6)
    ax0.set_ylabel("Accuracy", fontsize=12)
    ax0.set_ylim(-0.05, 1.15)
    ax0.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax0.legend(fontsize=10)
    ax0.grid(axis="y", alpha=0.4)

    # 各点にサンプル数を表示
    for xi, s in zip(x, stats):
        ax0.annotate(
            f"n={s['n_trials']}",
            xy=(xi, s["acc_mean"]),
            xytext=(4, 8),
            textcoords="offset points",
            fontsize=8,
            color="steelblue",
        )

    # ---- total tokens ----------------------------------------------------- #
    ax1 = axes[1]
    ax1.errorbar(
        x, tok_means, yerr=tok_sems,
        marker="s", linewidth=2, capsize=5, color="tomato",
        label="total tokens (mean ± SEM)",
    )

    # 理論的最小手数 2^N - 1 を参考線として重ねる（任意のスケール）
    min_moves = 2.0 ** x - 1
    ax1_r = ax1.twinx()
    ax1_r.plot(
        x, min_moves,
        linestyle=":", color="goldenrod", linewidth=1.5,
        label=r"$2^N - 1$ (min moves)",
    )
    ax1_r.set_ylabel(r"$2^N - 1$ (min moves)", fontsize=10, color="goldenrod")
    ax1_r.tick_params(axis="y", labelcolor="goldenrod")

    ax1.set_xlabel("N (number of disks)", fontsize=12)
    ax1.set_ylabel("Total Tokens", fontsize=12)
    ax1.legend(fontsize=10, loc="upper left")
    ax1_r.legend(fontsize=10, loc="lower right")
    ax1.grid(axis="y", alpha=0.4)

    # x 軸を整数のみに
    ax1.set_xticks(x)
    ax1.set_xticklabels([str(n) for n in ns])

    plt.tight_layout()

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=150, bbox_inches="tight")
        print(f"[saved] {out}")
    else:
        plt.show()


# --------------------------------------------------------------------------- #
# エントリポイント
# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot accuracy and token usage vs N for Hanoi experiments."
    )
    parser.add_argument(
        "--n_min", type=int, default=2,
        help="最小ディスク数 (default: 2)",
    )
    parser.add_argument(
        "--n_max", type=int, default=5,
        help="最大ディスク数 (default: 5)",
    )
    parser.add_argument(
        "--data_dir", type=Path, default=Path(__file__).parent / "test_results" / "hanoi_test",
        help="results_N*_test.json が置かれたディレクトリ (default: test_results/hanoi_test)",
    )
    parser.add_argument(
        "--out", type=Path, default=None,
        help="保存先 PNG パス。省略時はウィンドウ表示。",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.n_min > args.n_max:
        raise ValueError(f"--n_min ({args.n_min}) > --n_max ({args.n_max})")

    ns: list[int] = list(range(args.n_min, args.n_max + 1))
    stats: list[dict[str, float]] = []

    for n in ns:
        trials = load_results(args.data_dir, n)
        s = aggregate(trials)
        stats.append(s)
        print(
            f"N={n}  trials={s['n_trials']}  "
            f"acc={s['acc_mean']:.3f}±{s['acc_sem']:.3f}  "
            f"tokens={s['tok_mean']:.0f}±{s['tok_sem']:.0f}"
        )

    plot(ns, stats, out=args.out)


if __name__ == "__main__":
    main()
