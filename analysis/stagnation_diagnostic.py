"""
stagnation_diagnostic.py — stagnation_after_move 相帰属診断スクリプト

各 (N, T) 条件について early_stop ラベル別に P(q) 分布を比較し、
stagnation_after_move が SG 的（move_loop に近い）か PM 的（no_move に近い）かを判定する。

SPEC: specs/draft/SPEC-2026-05-21-001.md
物理的根拠: Section 2（physics-agent 審査済み — 2026-05-21）

使用例:
  python3 analysis/stagnation_diagnostic.py \\
      --dir results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b \\
      --dir results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b \\
      --layer layer_top \\
      --ns 2 3 4 5 6 \\
      --ts 0.2 0.4 0.6 0.8 1.0 1.2 1.5 2.0 \\
      --out-dir figures/stagnation_diagnostic
"""

from __future__ import annotations

import argparse
from itertools import combinations
from pathlib import Path
from typing import Callable, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import gaussian_kde

from analysis.analyze_integrated import _cosine, load_condition

# ===========================================================================
# グループ定義（SPEC Section 4.1 / 仕様書 Section 2.2）
# ===========================================================================

LOOP_LABELS: set[str] = {"move_loop_repeat", "move_loop_reverse"}
NO_MOVE_LABELS: set[str] = {"no_move_catchall", "move_ceiling"}

_GroupPred = Callable[[Optional[str]], bool]

GROUPS: dict[str, _GroupPred] = {
    "ordered":      lambda es: es == "goal_reached",
    "move_loop":    lambda es: es in LOOP_LABELS,
    "stagnation":   lambda es: es == "stagnation_after_move",
    "no_move":      lambda es: es in NO_MOVE_LABELS,
    "think_budget": lambda es: es == "think_budget",
}

GROUP_COLORS: dict[str, str] = {
    "ordered":      "#3fb950",  # green
    "move_loop":    "#f0883e",  # orange
    "stagnation":   "#f85149",  # red
    "no_move":      "#58a6ff",  # blue
    "think_budget": "#8b949e",  # gray
}

# P(q) 計算に使うカーネル密度推定の x グリッド
Q_GRID = np.linspace(0.35, 1.08, 300)

# 統計テーブル列幅
_COL_W = {"group": 14, "n_trials": 10, "n_pairs": 9,
          "mean_q": 9, "std_q": 9, "median_q": 10}


# move を出さない（または出せない）グループ：fallback hidden state が唯一の状態表現
# → is_fallback=True でも除外せず、end-of-generation hidden state を使う
_ALLOW_FALLBACK_GROUPS: frozenset[str] = frozenset({"no_move", "think_budget"})


# ===========================================================================
# データ計算
# ===========================================================================

def _compute_group_indices(
    early_stops: list[Optional[str]],
    is_fallback: list[bool],
) -> dict[str, list[int]]:
    """
    early_stop ラベルと fallback フラグから、グループ別の試行インデックスを返す。

    Parameters
    ----------
    early_stops : early_stop ラベルのリスト（summary.json 由来）。
    is_fallback : npz 由来の fallback フラグリスト。

    Returns
    -------
    各グループ名 → 有効な試行インデックスのリスト。

    Notes
    -----
    move を出したグループ（ordered / move_loop / stagnation）は
    is_fallback=True の試行を除外する（本来は move ステップで hidden state を取得済みのはず）。

    move を出さないグループ（no_move / think_budget）は is_fallback=True も含める。
    no_move_catchall 試行は必ず fallback capture になるため、除外すると PM ベースラインが消える。
    """
    n = min(len(early_stops), len(is_fallback))
    result: dict[str, list[int]] = {g: [] for g in GROUPS}
    for i in range(n):
        es = early_stops[i]
        for group_name, pred in GROUPS.items():
            if pred(es):
                if is_fallback[i] and group_name not in _ALLOW_FALLBACK_GROUPS:
                    break  # move ベースグループの fallback は除外
                result[group_name].append(i)
                break
    return result


def _compute_h_bars(
    hidden: list[np.ndarray],
    is_fallback: list[bool],
) -> dict[int, np.ndarray]:
    """
    各試行の時間平均 hidden state を計算する。

    Parameters
    ----------
    hidden      : 各試行の hidden state 行列 (n_steps, hidden_dim) のリスト。
    is_fallback : fallback フラグリスト。

    Returns
    -------
    試行インデックス → 時間平均 hidden state ベクトルのマッピング。

    Notes
    -----
    fallback 試行（no_move 等）は n_steps=1 の行列を持つ。
    mean(axis=0) は 1 行でも有効なので全試行を対象にする。
    グループ別の除外制御は _compute_group_indices 側で行う。
    """
    h_bars: dict[int, np.ndarray] = {}
    for i, H in enumerate(hidden):
        if H.shape[0] == 0:
            continue  # 空行列（npz に hidden state がないケース）はスキップ
        h_bars[i] = H.mean(axis=0)
    return h_bars


def compute_group_pq(
    cond: dict,
) -> dict[str, np.ndarray]:
    """
    条件データから early_stop グループ別の P(q) 値を計算する。

    Parameters
    ----------
    cond : load_condition() が返す辞書。

    Returns
    -------
    グループ名 → q 値配列のマッピング（n_trials < 2 のグループは除外）。
    """
    hidden: list[np.ndarray] = cond["hidden"]
    is_fallback: list[bool] = cond["is_fallback"]
    early_stops: list[Optional[str]] = cond["early_stop"]

    h_bars = _compute_h_bars(hidden, is_fallback)
    group_indices = _compute_group_indices(early_stops, is_fallback)

    pq_by_group: dict[str, np.ndarray] = {}
    for group_name, trial_indices in group_indices.items():
        # h_bars に存在するインデックスのみ使用
        valid_indices = [i for i in trial_indices if i in h_bars]
        if len(valid_indices) < 2:
            continue
        q_vals = [
            _cosine(h_bars[i], h_bars[j])
            for i, j in combinations(valid_indices, 2)
        ]
        pq_by_group[group_name] = np.array(q_vals, dtype=np.float32)

    return pq_by_group


def compute_group_pq_stats(
    pq_by_group: dict[str, np.ndarray],
    group_indices: dict[str, list[int]],
) -> dict[str, dict]:
    """
    グループ別の統計量を計算する。

    Returns
    -------
    グループ名 → {"n_trials", "n_pairs", "mean_q", "std_q", "median_q"} の辞書。
    """
    stats: dict[str, dict] = {}
    for group_name in GROUPS:
        n_trials = len(group_indices.get(group_name, []))
        if group_name in pq_by_group:
            q = pq_by_group[group_name]
            stats[group_name] = {
                "n_trials": n_trials,
                "n_pairs":  len(q),
                "mean_q":   float(np.mean(q)),
                "std_q":    float(np.std(q)),
                "median_q": float(np.median(q)),
            }
        else:
            stats[group_name] = {
                "n_trials": n_trials,
                "n_pairs":  None,
                "mean_q":   None,
                "std_q":    None,
                "median_q": None,
            }
    return stats


# ===========================================================================
# 可視化：1セル図（P(q) 比較）
# ===========================================================================

def _plot_kde_histogram(
    ax: plt.Axes,
    q_vals: np.ndarray,
    color: str,
    label: str,
    n_trials: int,
) -> None:
    """
    1グループ分のヒストグラム + KDE を ax に描画する。

    n_pairs < 5 の場合は KDE を省略してヒストグラムのみ描画する。
    """
    bins = np.linspace(0.35, 1.08, 25)
    ax.hist(q_vals, bins=bins, color=color, alpha=0.35, density=True)

    full_label = f"{label} (n={n_trials})"

    if len(q_vals) >= 5:
        try:
            kde = gaussian_kde(q_vals)
            ax.plot(Q_GRID, kde(Q_GRID), color=color, lw=2.0, label=full_label)
        except np.linalg.LinAlgError:
            # KDE が singular になる場合はヒストグラムのみ
            ax.axvline(float(np.mean(q_vals)), color=color, lw=1.5, ls="--",
                       label=full_label)
    else:
        ax.axvline(float(np.mean(q_vals)), color=color, lw=1.5, ls="--",
                   label=full_label)


def plot_pq_cell(
    pq_by_group: dict[str, np.ndarray],
    group_n_trials: dict[str, int],
    N: int,
    T: float,
    layer: str,
    out_path: Path,
) -> None:
    """
    1 (N, T) 条件の P(q) 比較図を生成して保存する。

    SPEC Section 4.4「1セル図」仕様に対応。
    """
    fig, ax = plt.subplots(figsize=(6, 4))

    for group_name in GROUPS:
        if group_name not in pq_by_group:
            continue
        q_vals = pq_by_group[group_name]
        n_trials = group_n_trials.get(group_name, 0)
        _plot_kde_histogram(
            ax, q_vals,
            color=GROUP_COLORS[group_name],
            label=group_name,
            n_trials=n_trials,
        )

    ax.set_xlim(0.4, 1.05)
    ax.set_xlabel("q  (cosine similarity)")
    ax.set_ylabel("density")
    ax.set_title(f"N={N}, T={T:.1f}  [{layer}]")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(True, alpha=0.25)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)


# ===========================================================================
# 可視化：aggregate 図（mean(q) vs T）
# ===========================================================================

def plot_aggregate(
    agg_data: dict[str, dict[float, dict]],
    N: int,
    layer: str,
    out_path: Path,
) -> None:
    """
    1 N 値についての aggregate 図を生成して保存する。

    Parameters
    ----------
    agg_data : グループ名 → {T: {"mean_q", "std_q", "n_pairs"}} のネスト辞書。
    N        : ディスク数。
    layer    : レイヤー名（タイトル表示用）。
    out_path : 出力先パス。

    SPEC Section 4.4「aggregate 図」仕様に対応。
    """
    fig, ax = plt.subplots(figsize=(7, 4.5))

    for group_name in GROUPS:
        if group_name not in agg_data:
            continue
        t_series = sorted(agg_data[group_name].keys())
        ts_valid, mean_vals, std_vals = [], [], []
        for T in t_series:
            entry = agg_data[group_name][T]
            if entry["mean_q"] is None:
                continue
            ts_valid.append(T)
            mean_vals.append(entry["mean_q"])
            std_vals.append(entry["std_q"])

        if not ts_valid:
            continue

        color = GROUP_COLORS[group_name]
        # pass yerr only when all std values are available
        yerr = std_vals if all(s is not None for s in std_vals) else None
        ax.errorbar(
            ts_valid, mean_vals, yerr=yerr,
            fmt="o-", color=color, lw=1.8, ms=5, capsize=3,
            label=group_name,
        )

    ax.set_xlabel("Temperature  T")
    ax.set_ylabel("mean(q)")
    ax.set_title(f"N={N}  mean(q) vs T  [{layer}]")
    ax.legend(fontsize=9, loc="best")
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0.3, 1.05)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)


# ===========================================================================
# 統計テーブル出力
# ===========================================================================

def print_stats_table(
    stats: dict[str, dict],
    N: int,
    T: float,
    layer: str,
) -> None:
    """
    (N, T, layer) の統計テーブルを端末に出力する。

    SPEC Section 4.4「統計テーブル」仕様に対応。
    """
    print(f"\n=== N={N}, T={T:.1f} [{layer}] ===")
    header = (
        f"  {'group':<{_COL_W['group']}} "
        f"{'n_trials':>{_COL_W['n_trials']}} "
        f"{'n_pairs':>{_COL_W['n_pairs']}} "
        f"{'mean_q':>{_COL_W['mean_q']}} "
        f"{'std_q':>{_COL_W['std_q']}} "
        f"{'median_q':>{_COL_W['median_q']}}"
    )
    print(header)
    print("  " + "-" * (len(header) - 2))

    for group_name in GROUPS:
        s = stats.get(group_name, {})
        n_t = s.get("n_trials", 0)
        n_p = s.get("n_pairs")
        mq  = s.get("mean_q")
        sq  = s.get("std_q")
        med = s.get("median_q")

        n_p_str  = f"{n_p}"    if n_p  is not None else "—"
        mq_str   = f"{mq:.4f}" if mq   is not None else "—"
        sq_str   = f"{sq:.4f}" if sq   is not None else "—"
        med_str  = f"{med:.4f}" if med is not None else "—"

        print(
            f"  {group_name:<{_COL_W['group']}} "
            f"{n_t:>{_COL_W['n_trials']}} "
            f"{n_p_str:>{_COL_W['n_pairs']}} "
            f"{mq_str:>{_COL_W['mean_q']}} "
            f"{sq_str:>{_COL_W['std_q']}} "
            f"{med_str:>{_COL_W['median_q']}}"
        )


# ===========================================================================
# メイン処理
# ===========================================================================

def run_diagnostic(
    dirs: list[Path],
    ns: list[int],
    ts: list[float],
    layer: str,
    out_base: Path,
    model_slug: str,
) -> None:
    """
    全 (N, T) 条件に対して診断を実行し、図と統計テーブルを出力する。

    Parameters
    ----------
    dirs       : データ検索対象ディレクトリのリスト。
    ns         : ディスク数リスト。
    ts         : 温度リスト。
    layer      : 解析対象レイヤー名。
    out_base   : 出力ルートディレクトリ。
    model_slug : 出力パス構築に使うモデルスラグ。
    """
    fig_dir = out_base / model_slug / layer
    fig_dir.mkdir(parents=True, exist_ok=True)

    # agg_data[N][group_name][T] = {"mean_q", "std_q", "n_pairs"}
    agg_data: dict[int, dict[str, dict[float, dict]]] = {N: {} for N in ns}

    for N in ns:
        for T in ts:
            cond = load_condition(dirs, N, T, layer)
            if cond is None:
                continue

            group_indices = _compute_group_indices(cond["early_stop"], cond["is_fallback"])
            pq_by_group   = compute_group_pq(cond)
            group_n_trials = {g: len(idxs) for g, idxs in group_indices.items()}
            stats          = compute_group_pq_stats(pq_by_group, group_indices)

            print_stats_table(stats, N, T, layer)

            for group_name, s in stats.items():
                agg_data[N].setdefault(group_name, {})[T] = {
                    "mean_q":  s["mean_q"],
                    "std_q":   s["std_q"],
                    "n_pairs": s["n_pairs"],
                }

            if pq_by_group:
                t_str = f"{T:.1f}".replace(".", "_")
                cell_path = fig_dir / f"N{N}_T{t_str}.png"
                plot_pq_cell(pq_by_group, group_n_trials, N, T, layer, cell_path)
                print(f"[SAVE] {cell_path}")

    for N in ns:
        if agg_data[N]:
            agg_path = fig_dir / f"aggregate_N{N}.png"
            plot_aggregate(agg_data[N], N, layer, agg_path)
            print(f"[SAVE] {agg_path}")


# ===========================================================================
# CLI
# ===========================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="stagnation_after_move 相帰属診断スクリプト"
    )
    parser.add_argument(
        "--dir", type=str, action="append", dest="dirs", required=True,
        metavar="DIR",
        help="データディレクトリ（複数指定可：--dir path1 --dir path2）",
    )
    parser.add_argument(
        "--layer", type=str, default="layer_top",
        help="解析対象レイヤー (default: layer_top)",
    )
    parser.add_argument(
        "--ns", type=int, nargs="+", default=[2, 3, 4, 5, 6],
        help="ディスク数リスト (default: 2 3 4 5 6)",
    )
    parser.add_argument(
        "--ts", type=float, nargs="+",
        default=[0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0],
        help="温度リスト (default: 0.2 0.4 0.6 0.8 1.0 1.2 1.5 2.0)",
    )
    parser.add_argument(
        "--out-dir", type=str, default="figures/stagnation_diagnostic",
        help="出力ルートディレクトリ (default: figures/stagnation_diagnostic)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dirs = [Path(d) for d in args.dirs]
    layer = args.layer
    out_base = Path(args.out_dir)

    # model_slug: 最初の dir のパス末尾から自動推定
    model_slug = dirs[0].name

    print(f"[INFO] model_slug: {model_slug}  layer: {layer}")
    for d in dirs:
        status = "ok" if d.exists() else "NOT FOUND"
        print(f"  {d}  ({status})")

    run_diagnostic(
        dirs=dirs,
        ns=args.ns,
        ts=args.ts,
        layer=layer,
        out_base=out_base,
        model_slug=model_slug,
    )

    print("\n[DONE]")
    print(f"  出力先: {out_base / model_slug / layer}/")


if __name__ == "__main__":
    main()
