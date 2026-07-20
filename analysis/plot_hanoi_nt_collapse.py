"""Plot Hanoi accuracy and collapse modes on the N-T plane.

The input is the existing per-condition ``summary.json`` produced under
``results/hanoi/{full_sweep,collapse_phase}/<model>/N*_T*/``.  Hidden-state
NPZ files are not required for the plot, but can be counted with
``--check-npz`` to catch missing trial artifacts.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import sys

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import matplotlib.colors as mcolors
from matplotlib.patches import Patch
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


COND_RE = re.compile(r"^N(?P<N>\d+)_T(?P<T>\d+(?:_\d+)?)$")

MOVE_LOOP_KEYS = {"move_loop_repeat"}
NO_MOVE_KEYS = {"no_move_catchall", "no_move"}

STATE_COLORS = {
    "solved": "#2ca25f",
    "move_loop": "#f28e2b",
    "no_move": "#4e79a7",
    "mixed": "#9b9b9b",
    "other": "#b07aa1",
    "missing": "#f2f2f2",
}

STATE_LABELS = {
    "solved": "Correct",
    "move_loop": "Move loop",
    "no_move": "No move",
    "mixed": "Mixed",
    "other": "Other stop",
    "missing": "Missing",
}


@dataclass
class ConditionStats:
    N: int
    T: float
    source: Path
    n_trials: int
    accuracy: float
    failures: int
    move_loop_rate_all: float
    no_move_rate_all: float
    move_loop_rate_failed: float
    no_move_rate_failed: float
    early_stop: Counter[str]
    dominant_state: str
    npz_count: int | None = None


def parse_condition_name(path: Path) -> tuple[int, float] | None:
    match = COND_RE.match(path.name)
    if not match:
        return None
    N = int(match.group("N"))
    T = float(match.group("T").replace("_", "."))
    return N, T


def canonical_stop(raw: str | None) -> str:
    key = raw or "none"
    if key in MOVE_LOOP_KEYS:
        return "move_loop"
    if key in NO_MOVE_KEYS:
        return "no_move"
    return key


def dominant_collapse_state(
    accuracy: float,
    failures: int,
    move_loop_rate_failed: float,
    no_move_rate_failed: float,
    other_failed_rate: float,
) -> str:
    if failures == 0 and accuracy >= 0.999:
        return "solved"
    rates = {
        "move_loop": move_loop_rate_failed,
        "no_move": no_move_rate_failed,
        "other": other_failed_rate,
    }
    state, value = max(rates.items(), key=lambda item: item[1])
    if value < 0.5 and failures > 0:
        return "mixed"
    return state


def load_summary(path: Path, check_npz: bool) -> ConditionStats | None:
    parsed = parse_condition_name(path)
    if parsed is None:
        return None
    summary_path = path / "summary.json"
    if not summary_path.exists():
        return None
    with summary_path.open("r", encoding="utf-8") as f:
        rows = json.load(f)
    if not isinstance(rows, list) or not rows:
        return None

    N, T = parsed
    n_trials = len(rows)
    acc_values = [float(row.get("accuracy", 0.0)) for row in rows]
    accuracy = float(np.mean(acc_values))
    failures = sum(1 for value in acc_values if value < 0.5)

    stops = Counter(canonical_stop(row.get("early_stop")) for row in rows)
    move_loop = stops.get("move_loop", 0)
    no_move = stops.get("no_move", 0)
    other_failed = max(0, failures - move_loop - no_move)

    denom_all = max(1, n_trials)
    denom_fail = max(1, failures)
    move_loop_rate_failed = move_loop / denom_fail if failures else 0.0
    no_move_rate_failed = no_move / denom_fail if failures else 0.0
    other_failed_rate = other_failed / denom_fail if failures else 0.0

    npz_count = len(list(path.glob("trial_*_hidden.npz"))) if check_npz else None
    dominant = dominant_collapse_state(
        accuracy=accuracy,
        failures=failures,
        move_loop_rate_failed=move_loop_rate_failed,
        no_move_rate_failed=no_move_rate_failed,
        other_failed_rate=other_failed_rate,
    )

    return ConditionStats(
        N=N,
        T=T,
        source=path,
        n_trials=n_trials,
        accuracy=accuracy,
        failures=failures,
        move_loop_rate_all=move_loop / denom_all,
        no_move_rate_all=no_move / denom_all,
        move_loop_rate_failed=move_loop_rate_failed,
        no_move_rate_failed=no_move_rate_failed,
        early_stop=stops,
        dominant_state=dominant,
        npz_count=npz_count,
    )


def discover_models(input_dirs: list[Path]) -> list[str]:
    models: set[str] = set()
    for input_dir in input_dirs:
        if not input_dir.exists():
            continue
        models.update(p.name for p in input_dir.iterdir() if p.is_dir())
    return sorted(models)


def load_model_stats(input_dirs: list[Path], model: str, check_npz: bool) -> dict[tuple[int, float], ConditionStats]:
    stats: dict[tuple[int, float], ConditionStats] = {}
    # Later input directories override earlier ones.  By default that means
    # collapse_phase refines full_sweep in the high-temperature region.
    for input_dir in input_dirs:
        model_dir = input_dir / model
        if not model_dir.exists():
            continue
        for cond_dir in sorted(p for p in model_dir.iterdir() if p.is_dir()):
            stat = load_summary(cond_dir, check_npz=check_npz)
            if stat is not None:
                stats[(stat.N, stat.T)] = stat
    return stats


def grid_values(stats: dict[tuple[int, float], ConditionStats]) -> tuple[list[int], list[float]]:
    ns = sorted({key[0] for key in stats})
    ts = sorted({key[1] for key in stats})
    return ns, ts


def matrix_for(
    stats: dict[tuple[int, float], ConditionStats],
    ns: list[int],
    ts: list[float],
    attr: str,
    fill: float = np.nan,
) -> np.ndarray:
    mat = np.full((len(ns), len(ts)), fill, dtype=float)
    for i, N in enumerate(ns):
        for j, T in enumerate(ts):
            stat = stats.get((N, T))
            if stat is not None:
                mat[i, j] = float(getattr(stat, attr))
    return mat


def state_matrix(
    stats: dict[tuple[int, float], ConditionStats],
    ns: list[int],
    ts: list[float],
) -> np.ndarray:
    order = ["missing", "solved", "move_loop", "no_move", "mixed", "other"]
    index = {state: idx for idx, state in enumerate(order)}
    mat = np.zeros((len(ns), len(ts)), dtype=float)
    for i, N in enumerate(ns):
        for j, T in enumerate(ts):
            state = stats.get((N, T)).dominant_state if (N, T) in stats else "missing"
            mat[i, j] = index.get(state, index["other"])
    return mat


def add_cell_text(ax, stats: dict[tuple[int, float], ConditionStats], ns: list[int], ts: list[float]) -> None:
    for i, N in enumerate(ns):
        for j, T in enumerate(ts):
            stat = stats.get((N, T))
            if stat is None:
                continue
            ax.text(j, i, f"{stat.accuracy:.0%}", ha="center", va="center", fontsize=8, fontweight="bold")


def add_collapse_text(ax, stats: dict[tuple[int, float], ConditionStats], ns: list[int], ts: list[float]) -> None:
    for i, N in enumerate(ns):
        for j, T in enumerate(ts):
            stat = stats.get((N, T))
            if stat is None:
                continue
            ml = stat.move_loop_rate_failed
            nm = stat.no_move_rate_failed
            if stat.failures == 0:
                label = "OK"
            elif ml >= nm:
                label = f"Loop\n{ml:.0%}"
            else:
                label = f"No move\n{nm:.0%}"
            if stat.dominant_state == "mixed":
                label = "Mixed"
            elif stat.dominant_state == "other":
                label = "Other"
            ax.text(j, i, label, ha="center", va="center", fontsize=7.2, color="#111111")


def setup_nt_axis(ax, ns: list[int], ts: list[float]) -> None:
    ax.set_xticks(np.arange(len(ts)))
    ax.set_xticklabels([f"{T:g}" for T in ts], rotation=45, ha="right")
    ax.set_yticks(np.arange(len(ns)))
    ax.set_yticklabels([str(N) for N in ns])
    ax.set_xlabel("Temperature T")
    ax.set_ylabel("Disk count N")
    ax.set_xlim(-0.5, len(ts) - 0.5)
    ax.set_ylim(-0.5, len(ns) - 0.5)
    ax.grid(which="major", color="#ffffff", linewidth=1.0)


def plot_model(
    model: str,
    stats: dict[tuple[int, float], ConditionStats],
    out_dir: Path,
    dpi: int,
    contours: bool,
) -> Path:
    ns, ts = grid_values(stats)
    acc_mat = matrix_for(stats, ns, ts, "accuracy")
    ml_mat = matrix_for(stats, ns, ts, "move_loop_rate_all", fill=0.0)
    nm_mat = matrix_for(stats, ns, ts, "no_move_rate_all", fill=0.0)
    st_mat = state_matrix(stats, ns, ts)

    fig, axes = plt.subplots(1, 2, figsize=(max(11, 0.9 * len(ts) + 5), max(5.2, 0.52 * len(ns) + 3)))
    fig.suptitle(f"Hanoi N-T plane: accuracy and post-collapse modes ({model})", fontsize=13)

    acc_cmap = mcolors.LinearSegmentedColormap.from_list("acc", ["#d73027", "#fee08b", "#1a9850"])
    im0 = axes[0].imshow(acc_mat, origin="lower", aspect="auto", cmap=acc_cmap, vmin=0.0, vmax=1.0)
    setup_nt_axis(axes[0], ns, ts)
    axes[0].set_title("Accuracy")
    add_cell_text(axes[0], stats, ns, ts)
    cbar = fig.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04)
    cbar.set_label("mean accuracy")

    state_order = ["missing", "solved", "move_loop", "no_move", "mixed", "other"]
    state_cmap = mcolors.ListedColormap([STATE_COLORS[state] for state in state_order])
    bounds = np.arange(len(state_order) + 1) - 0.5
    norm = mcolors.BoundaryNorm(bounds, state_cmap.N)
    axes[1].imshow(st_mat, origin="lower", aspect="auto", cmap=state_cmap, norm=norm)
    setup_nt_axis(axes[1], ns, ts)
    axes[1].set_title("Dominant mode among failed trials")
    add_collapse_text(axes[1], stats, ns, ts)
    handles = [
        Patch(facecolor=STATE_COLORS[state], edgecolor="none", label=STATE_LABELS[state])
        for state in ["solved", "move_loop", "no_move", "mixed", "other"]
    ]
    axes[1].legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1.0), borderaxespad=0.0, fontsize=8)

    # Optional contours expose absolute rates, but they are off by default
    # because dense N-T grids are easier to read as labeled tiles.
    if contours and len(ts) >= 2 and len(ns) >= 2:
        x = np.arange(len(ts))
        y = np.arange(len(ns))
        axes[1].contour(x, y, ml_mat, levels=[0.25, 0.5, 0.75], colors="#7f3b08", linewidths=0.8, alpha=0.8)
        axes[1].contour(x, y, nm_mat, levels=[0.25, 0.5, 0.75], colors="#08306b", linewidths=0.8, linestyles="--", alpha=0.8)

    fig.text(
        0.5,
        0.015,
        "Collapse labels use failed trials only. Loop=move loop, No move=hand does not move. "
        "Exact all-trial and failed-trial rates are written to the CSV.",
        ha="center",
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"hanoi_nt_collapse_{model}.png"
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)
    return out_path


def write_table(
    model: str,
    stats: dict[tuple[int, float], ConditionStats],
    out_dir: Path,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"hanoi_nt_collapse_{model}.csv"
    rows = [
        "model,N,T,n_trials,accuracy,failures,move_loop_rate_all,no_move_rate_all,"
        "move_loop_rate_failed,no_move_rate_failed,dominant_state,npz_count,source"
    ]
    for _, stat in sorted(stats.items()):
        rows.append(
            ",".join(
                [
                    model,
                    str(stat.N),
                    f"{stat.T:g}",
                    str(stat.n_trials),
                    f"{stat.accuracy:.6f}",
                    str(stat.failures),
                    f"{stat.move_loop_rate_all:.6f}",
                    f"{stat.no_move_rate_all:.6f}",
                    f"{stat.move_loop_rate_failed:.6f}",
                    f"{stat.no_move_rate_failed:.6f}",
                    stat.dominant_state,
                    "" if stat.npz_count is None else str(stat.npz_count),
                    str(stat.source),
                ]
            )
        )
    out_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return out_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot Hanoi accuracy and collapse modes on the N-T plane.")
    parser.add_argument(
        "--input-dir",
        action="append",
        type=Path,
        default=None,
        help="Sweep root to read. Can be passed multiple times.",
    )
    parser.add_argument("--model", action="append", default=None, help="Model directory name. Defaults to all models.")
    parser.add_argument("--out-dir", type=Path, default=Path("figures/hanoi_nt_collapse"))
    parser.add_argument("--dpi", type=int, default=180)
    parser.add_argument("--check-npz", action="store_true", help="Count trial_*_hidden.npz files per condition.")
    parser.add_argument("--contours", action="store_true", help="Overlay all-trial move-loop/no-move rate contours.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dirs = args.input_dir or [
        Path("results/hanoi/full_sweep"),
        Path("results/hanoi/collapse_phase"),
    ]
    models = args.model or discover_models(input_dirs)
    if not models:
        raise SystemExit("No model directories found.")

    for model in models:
        stats = load_model_stats(input_dirs, model=model, check_npz=args.check_npz)
        if not stats:
            print(f"[SKIP] {model}: no summary.json files found")
            continue
        fig_path = plot_model(model, stats, args.out_dir, dpi=args.dpi, contours=args.contours)
        csv_path = write_table(model, stats, args.out_dir)
        ns, ts = grid_values(stats)
        print(f"[SAVE] {fig_path}  cells={len(stats)}  N={ns[0]}..{ns[-1]}  T={ts[0]:g}..{ts[-1]:g}")
        print(f"[SAVE] {csv_path}")


if __name__ == "__main__":
    main()
