"""P(q) moments based phase classifier.

Usage:
  python3 analysis/pq_phase_classifier.py --model deepseek-r1-distill-qwen-7b
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.analyze_integrated import TS_ALL, TS_PQ, load_condition
from analysis.isotropy import fit_isotropy
from analysis.pq_metrics import compute_pq_moments, pairwise_overlaps, trial_mean_vectors


MODEL_DEFAULT = "deepseek-r1-distill-qwen-7b"
LAYER_DEFAULT = "layer_mid"
NS_DEFAULT = [2, 3, 4, 5, 6]
THRESHOLDS_DEFAULT = Path("configs/thresholds.default.json")
RESULT_COLUMNS = [
    "model_slug",
    "N",
    "T",
    "layer",
    "n_effective",
    "n_censored",
    "accuracy",
    "q_mean",
    "q_mean_ci_95",
    "q_var",
    "q_var_ci_95",
    "q_abs_mean_exploratory",
    "q_tail_mass",
    "q_bimodality_bc",
    "q_bimodality_dip",
    "q_bimodality_dip_pval",
    "ordered_rate",
    "sg_label_rate",
    "pm_rate",
    "stagnation_after_move_rate",
    "phase",
]
PHASES = ["undetermined", "paramagnetic", "transitional", "spin_glass", "ordered"]
PHASE_TO_INT = {phase: i for i, phase in enumerate(PHASES)}
PHASE_COLORS = {
    "undetermined": "#bdbdbd",
    "paramagnetic": "#d62728",
    "transitional": "#9467bd",
    "spin_glass": "#ff7f0e",
    "ordered": "#1f77b4",
}


@dataclass(frozen=True)
class Thresholds:
    acc_ordered_min: float | None = None
    ordered_var_max: float | None = None
    ordered_tail_min: float | None = None
    sg_bimodality_min: float | None = None
    sg_var_min: float | None = None
    sg_tail_min: float | None = None
    pm_mean_max: float | None = None
    pm_var_max: float | None = None
    pm_bimodality_max: float | None = None
    pm_abs_q_max: float | None = None
    pm_rate_min: float | None = None
    min_trials: int = 5

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "Thresholds":
        known = {name for name in cls.__dataclass_fields__}
        values = {k: raw[k] for k in raw if k in known}
        return cls(**values)


def _rate(early_stop: list, keys: set[str]) -> float:
    usable = [es for es in early_stop if es != "think_budget"]
    if not usable:
        return float("nan")
    return sum(1 for es in usable if es in keys) / len(usable)


def _accuracy(accuracy: list, early_stop: list, n_hidden: int) -> float:
    if not accuracy:
        return float("nan")
    usable_acc = [a for a, es in zip(accuracy[:n_hidden], early_stop[:n_hidden]) if es != "think_budget"]
    return float(np.mean(usable_acc)) if usable_acc else float("nan")


def load_thresholds(path: Path | None) -> Thresholds:
    threshold_path = path or THRESHOLDS_DEFAULT
    if not threshold_path.exists():
        return Thresholds()
    with open(threshold_path) as f:
        raw = json.load(f)
    return Thresholds.from_mapping(raw)


def classify_from_moments(
    accuracy: float,
    moments: dict[str, float],
    n_effective: int,
    thresholds: Thresholds,
) -> str:
    if n_effective < thresholds.min_trials:
        return "undetermined"
    if not np.isfinite(accuracy):
        return "undetermined"

    acc_min = thresholds.acc_ordered_min
    if acc_min is None:
        return "undetermined"

    ordered = (
        accuracy >= acc_min
        and thresholds.ordered_var_max is not None
        and thresholds.ordered_tail_min is not None
        and moments["q_var"] <= thresholds.ordered_var_max
        and moments["q_tail_mass"] >= thresholds.ordered_tail_min
    )
    if ordered:
        return "ordered"

    if (
        thresholds.sg_var_min is None
        and thresholds.sg_tail_min is None
        and thresholds.sg_bimodality_min is None
        and thresholds.pm_mean_max is None
        and thresholds.pm_var_max is None
        and thresholds.pm_bimodality_max is None
    ):
        return "undetermined"

    below_ordered = accuracy < acc_min
    sg_checks = []
    if thresholds.sg_bimodality_min is not None:
        sg_checks.append(moments["q_bimodality_bc"] >= thresholds.sg_bimodality_min)
    if thresholds.sg_var_min is not None:
        sg_checks.append(moments["q_var"] >= thresholds.sg_var_min)
    if thresholds.sg_tail_min is not None:
        sg_checks.append(moments["q_tail_mass"] >= thresholds.sg_tail_min)
    spin_glass = below_ordered and any(sg_checks)

    paramagnetic = (
        below_ordered
        and thresholds.pm_mean_max is not None
        and thresholds.pm_var_max is not None
        and abs(moments["q_mean"]) <= thresholds.pm_mean_max
        and moments["q_var"] <= thresholds.pm_var_max
        and (
            thresholds.pm_bimodality_max is None
            or moments["q_bimodality_bc"] < thresholds.pm_bimodality_max
        )
    )

    matched = [ordered, spin_glass, paramagnetic]
    if sum(bool(x) for x in matched) > 1:
        return "transitional"
    if spin_glass:
        return "spin_glass"
    if paramagnetic:
        return "paramagnetic"
    return "transitional"


def _serializable_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for key in ("q_mean_ci_95", "q_var_ci_95"):
        if isinstance(out.get(key), tuple):
            out[key] = list(out[key])
    return out


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return json.dumps(value)
    return value


def collect_conditions(dirs: list[Path], ns: list[int], ts: list[float], layer: str) -> dict[tuple[int, float], dict]:
    conditions: dict[tuple[int, float], dict] = {}
    for N in ns:
        for T in ts:
            cond = load_condition(dirs, N, T, layer)
            if cond is not None:
                conditions[(N, T)] = cond
    return conditions


def build_model_layer_transformer(
    conditions: dict[tuple[int, float], dict],
    method: str,
    topk: int,
    zca_reg: float,
):
    hidden_union = []
    for cond in conditions.values():
        hidden_union.extend(cond["hidden"])
    return fit_isotropy(hidden_union, method=method, topk=topk, zca_reg=zca_reg)


def _effective_hidden(cond: dict, transformer, min_steps: int) -> tuple[list[np.ndarray], int]:
    hidden = []
    n_censored = 0
    early_stop = cond.get("early_stop", [])
    for idx, H in enumerate(cond["hidden"]):
        es = early_stop[idx] if idx < len(early_stop) else None
        if es == "think_budget":
            n_censored += 1
            continue
        if np.asarray(H).ndim != 2 or H.shape[0] < min_steps:
            n_censored += 1
            continue
        hidden.append(transformer.transform(H))
    return hidden, n_censored


def compute_metrics_rows(
    model_slug: str,
    layer: str,
    conditions: dict[tuple[int, float], dict],
    transformer,
    thresholds: Thresholds,
    min_steps: int,
    tail_threshold: float,
    n_bootstrap: int,
    random_seed: int,
) -> tuple[list[dict[str, Any]], dict[tuple[int, float], np.ndarray]]:
    rows: list[dict[str, Any]] = []
    q_cache: dict[tuple[int, float], np.ndarray] = {}

    for (N, T), cond in sorted(conditions.items()):
        hidden, hidden_censored = _effective_hidden(cond, transformer, min_steps)
        means = trial_mean_vectors(hidden, min_steps=1)
        n_censored = hidden_censored + means.n_censored
        q_vals = pairwise_overlaps(means.vectors)
        q_cache[(N, T)] = q_vals
        moments = compute_pq_moments(
            q_vals,
            hbar_norms=means.norms,
            tail_threshold=tail_threshold,
            n_bootstrap=n_bootstrap,
            random_seed=random_seed + 1000 * N + int(round(T * 100)),
        )
        m = moments.to_dict()
        n_effective = int(means.vectors.shape[0])
        phase = classify_from_moments(_accuracy(cond["accuracy"], cond["early_stop"], len(cond["hidden"])), m, n_effective, thresholds)
        row = {
            "model_slug": model_slug,
            "N": N,
            "T": T,
            "layer": layer,
            "n_effective": n_effective,
            "n_censored": n_censored,
            "accuracy": _accuracy(cond["accuracy"], cond["early_stop"], len(cond["hidden"])),
            "q_mean": m["q_mean"],
            "q_mean_ci_95": m["q_mean_ci_95"],
            "q_var": m["q_var"],
            "q_var_ci_95": m["q_var_ci_95"],
            "q_abs_mean_exploratory": m["q_abs_mean_exploratory"],
            "q_tail_mass": m["q_tail_mass"],
            "q_bimodality_bc": m["q_bimodality_bc"],
            "q_bimodality_dip": m["q_bimodality_dip"],
            "q_bimodality_dip_pval": m["q_bimodality_dip_pval"],
            "ordered_rate": _rate(cond["early_stop"], {"goal_reached"}),
            "sg_label_rate": _rate(cond["early_stop"], {"move_loop_repeat", "move_loop_reverse"}),
            "pm_rate": _rate(cond["early_stop"], {"no_move_catchall", "move_ceiling"}),
            "stagnation_after_move_rate": _rate(cond["early_stop"], {"stagnation_after_move"}),
            "phase": phase,
            "q_count": m["q_count"],
            "hbar_norm_mean": m["hbar_norm_mean"],
            "hbar_norm_std": m["hbar_norm_std"],
        }
        rows.append(row)
    return rows, q_cache


def write_metrics(rows: list[dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "metrics.csv"
    json_path = out_dir / "metrics.json"
    columns = RESULT_COLUMNS + ["q_count", "hbar_norm_mean", "hbar_norm_std"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _csv_value(row.get(k)) for k in columns})
    with open(json_path, "w") as f:
        json.dump([_serializable_row(r) for r in rows], f, indent=2, allow_nan=True)
    print(f"[SAVE] {csv_path}")
    print(f"[SAVE] {json_path}")


def plot_phase_diagram(rows: list[dict[str, Any]], ns: list[int], ts: list[float], out_path: Path) -> None:
    mat = np.full((len(ns), len(ts)), np.nan)
    by_cell = {(r["N"], r["T"]): r for r in rows}
    for i, N in enumerate(ns):
        for j, T in enumerate(ts):
            row = by_cell.get((N, T))
            if row:
                mat[i, j] = PHASE_TO_INT[row["phase"]]
    cmap = ListedColormap([PHASE_COLORS[p] for p in PHASES])
    fig, ax = plt.subplots(figsize=(14, 4.5))
    im = ax.imshow(mat, aspect="auto", origin="lower", vmin=-0.5, vmax=len(PHASES) - 0.5, cmap=cmap)
    cbar = plt.colorbar(im, ax=ax, ticks=list(range(len(PHASES))))
    cbar.ax.set_yticklabels([p.replace("_", " ") for p in PHASES], fontsize=8)
    ax.set_title("P(q) Moments Phase Classification")
    ax.set_xlabel("Temperature T")
    ax.set_ylabel("Disk count N")
    ax.set_xticks(range(len(ts)))
    ax.set_xticklabels([f"{t:.1f}" for t in ts], rotation=45, fontsize=7)
    ax.set_yticks(range(len(ns)))
    ax.set_yticklabels(ns)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[SAVE] {out_path}")


def plot_pq_grid(
    rows: list[dict[str, Any]],
    q_cache: dict[tuple[int, float], np.ndarray],
    ns: list[int],
    ts: list[float],
    out_path: Path,
) -> None:
    by_cell = {(r["N"], r["T"]): r for r in rows}
    fig, axes = plt.subplots(len(ns), len(ts), figsize=(2.1 * len(ts), 1.8 * len(ns)), sharex=True)
    axes_arr = np.atleast_2d(axes)
    for i, N in enumerate(ns):
        for j, T in enumerate(ts):
            ax = axes_arr[i, j]
            row = by_cell.get((N, T))
            q_vals = q_cache.get((N, T), np.empty((0,)))
            if row is None or q_vals.size == 0:
                ax.text(0.5, 0.5, "N/A", ha="center", va="center", transform=ax.transAxes, fontsize=7)
                ax.set_xticks([])
                ax.set_yticks([])
                continue
            ax.hist(q_vals, bins=np.linspace(-1.0, 1.0, 41), color=PHASE_COLORS[row["phase"]], alpha=0.75, density=True)
            ax.axvline(row["q_mean"], color="black", lw=0.8, ls="--")
            ax.text(0.04, 0.95, f"q={row['q_mean']:.2f}\nv={row['q_var']:.2f}", transform=ax.transAxes, va="top", fontsize=6)
            if i == 0:
                ax.set_title(f"T={T:.1f}", fontsize=8)
            if j == 0:
                ax.set_ylabel(f"N={N}", fontsize=8)
            ax.tick_params(labelsize=6)
    handles = [Patch(facecolor=PHASE_COLORS[p], label=p.replace("_", " ")) for p in PHASES]
    fig.legend(handles=handles, loc="lower center", ncol=len(PHASES), fontsize=8, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("P(q) Grid", y=1.01)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[SAVE] {out_path}")


def compute_topk_sensitivity_counts(
    model_slug: str,
    layer: str,
    conditions: dict[tuple[int, float], dict],
    thresholds: Thresholds,
    topks: list[int],
    zca_reg: float,
    min_steps: int,
    tail_threshold: float,
    n_bootstrap: int,
    random_seed: int,
) -> dict[int, dict[str, int]]:
    sensitivity: dict[int, dict[str, int]] = {}
    for topk in topks:
        transformer = build_model_layer_transformer(conditions, "remove_topk", topk, zca_reg)
        rows, _ = compute_metrics_rows(
            model_slug,
            layer,
            conditions,
            transformer,
            thresholds,
            min_steps,
            tail_threshold,
            n_bootstrap,
            random_seed,
        )
        counts = {phase: 0 for phase in PHASES}
        for row in rows:
            counts[row["phase"]] = counts.get(row["phase"], 0) + 1
        sensitivity[topk] = counts
    return sensitivity


def plot_threshold_sensitivity(
    rows: list[dict[str, Any]],
    thresholds: Thresholds,
    out_path: Path,
    topk_sensitivity: dict[int, dict[str, int]] | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    counts = {phase: 0 for phase in PHASES}
    for row in rows:
        counts[row["phase"]] = counts.get(row["phase"], 0) + 1

    if topk_sensitivity:
        x = np.arange(len(topk_sensitivity))
        bottom = np.zeros(len(topk_sensitivity), dtype=float)
        labels = [str(k) for k in topk_sensitivity]
        for phase in PHASES:
            vals = np.array([topk_sensitivity[k].get(phase, 0) for k in topk_sensitivity], dtype=float)
            ax.bar(x, vals, bottom=bottom, color=PHASE_COLORS[phase], label=phase.replace("_", " "))
            bottom += vals
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.set_xlabel("remove_topk k")
        ax.legend(fontsize=8, ncol=2)
    else:
        ax.bar(range(len(PHASES)), [counts[p] for p in PHASES], color=[PHASE_COLORS[p] for p in PHASES])
        ax.set_xticks(range(len(PHASES)))
        ax.set_xticklabels([p.replace("_", " ") for p in PHASES], rotation=25, ha="right")
    ax.set_ylabel("cell count")
    ax.set_title("Threshold / top-k Sensitivity")
    unset = [k for k, v in thresholds.__dict__.items() if v is None]
    note = "unset thresholds -> undetermined" if unset else "all rule thresholds set"
    ax.text(0.02, 0.95, note, transform=ax.transAxes, va="top", fontsize=9)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[SAVE] {out_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="P(q) moments based phase classifier")
    parser.add_argument("--model", type=str, default=MODEL_DEFAULT)
    parser.add_argument("--layer", choices=["layer_top", "layer_mid", "layer_low"], default=LAYER_DEFAULT)
    parser.add_argument("--ns", type=int, nargs="+", default=NS_DEFAULT)
    parser.add_argument("--ts", type=float, nargs="+", default=TS_ALL)
    parser.add_argument("--pq-ts", type=float, nargs="+", default=TS_PQ)
    parser.add_argument("--base", type=str, default="results/hanoi")
    parser.add_argument("--results-dir", type=str, default="results/analysis/pq_phase_classifier")
    parser.add_argument("--figures-dir", type=str, default="figures/pq_phase_classifier")
    parser.add_argument("--isotropy-method", choices=["center", "remove_topk", "zca"], default="remove_topk")
    parser.add_argument("--topk", type=int, default=3)
    parser.add_argument("--zca-reg", type=float, default=1e-5)
    parser.add_argument("--min-steps", type=int, default=1)
    parser.add_argument("--tail-threshold", type=float, default=0.5)
    parser.add_argument("--bootstrap", type=int, default=500)
    parser.add_argument("--random-seed", type=int, default=0)
    parser.add_argument("--thresholds", type=Path, default=None)
    parser.add_argument("--sensitivity-topks", type=int, nargs="+", default=[0, 1, 3, 5, 10])
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Override output directory for metrics CSV/JSON (default: results-dir/model/layer)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base = Path(args.base)
    dirs = [base / "full_sweep" / args.model, base / "collapse_phase" / args.model]
    thresholds = load_thresholds(args.thresholds)
    print(f"[INFO] model={args.model} layer={args.layer} isotropy={args.isotropy_method} topk={args.topk}")
    for d in dirs:
        print(f"  {d} ({'ok' if d.exists() else 'NOT FOUND'})")

    conditions = collect_conditions(dirs, args.ns, args.ts, args.layer)
    print(f"[INFO] loaded {len(conditions)} conditions")
    if not conditions:
        raise SystemExit("No conditions loaded")

    transformer = build_model_layer_transformer(conditions, args.isotropy_method, args.topk, args.zca_reg)
    rows, q_cache = compute_metrics_rows(
        args.model,
        args.layer,
        conditions,
        transformer,
        thresholds,
        args.min_steps,
        args.tail_threshold,
        args.bootstrap,
        args.random_seed,
    )

    result_dir = args.output_dir if args.output_dir else Path(args.results_dir) / args.model / args.layer
    figure_dir = Path(args.figures_dir) / args.model / args.layer
    write_metrics(rows, result_dir)
    topk_sensitivity = None
    if args.isotropy_method == "remove_topk" and args.sensitivity_topks:
        topk_sensitivity = compute_topk_sensitivity_counts(
            args.model,
            args.layer,
            conditions,
            thresholds,
            args.sensitivity_topks,
            args.zca_reg,
            args.min_steps,
            args.tail_threshold,
            min(args.bootstrap, 100),
            args.random_seed,
        )
    plot_phase_diagram(rows, args.ns, args.ts, figure_dir / "phase_diagram.png")
    plot_pq_grid(rows, q_cache, args.ns, args.pq_ts, figure_dir / "pq_grid.png")
    plot_threshold_sensitivity(rows, thresholds, figure_dir / "threshold_sensitivity.png", topk_sensitivity)


if __name__ == "__main__":
    main()
