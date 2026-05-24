from __future__ import annotations

import contextlib
import io
from itertools import combinations

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np

from analysis.base_analyzer import AnalysisResult, BaseAnalyzer, ConditionData
from analysis.io_utils import _cosine


LAYER_DEFAULT = "layer_m8"
Q_BINS = np.linspace(-0.1, 1.05, 47)
PHASE_COLORS = {
    "ordered": "#1f77b4",
    "spin_glass": "#ff7f0e",
    "paramagnetic": "#d62728",
    "mixed": "#9467bd",
}


def condition_to_dict(cond: ConditionData, layer: str) -> dict:
    hidden = cond.hidden.get(layer, [])
    return {
        "hidden": hidden,
        "is_fallback": cond.is_fallback[: len(hidden)],
        "accuracy": [r["accuracy"] for r in cond.trials],
        "early_stop": cond.early_stop,
        "pm_rate": cond.pm_rate,
        "n_trials": len(hidden),
        "N": cond.N,
        "T": cond.T,
    }


def trial_mean_hidden(H: np.ndarray) -> np.ndarray:
    return H.mean(axis=0)


def compute_pq(cond: dict) -> np.ndarray:
    means = [trial_mean_hidden(H) for H in cond["hidden"]]
    q_vals = [_cosine(means[i], means[j]) for i, j in combinations(range(len(means)), 2)]
    return np.array(q_vals, dtype=np.float32)


def compute_qea(cond: dict) -> float:
    vals = []
    for H, is_fb in zip(cond["hidden"], cond["is_fallback"]):
        if is_fb or H.shape[0] < 2:
            continue
        for i, j in combinations(range(H.shape[0]), 2):
            vals.append(_cosine(H[i], H[j]))
    return float(np.mean(vals)) if vals else float("nan")


def compute_autocorr(cond: dict, max_lag: int = 10) -> np.ndarray:
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
    n = len(cond["early_stop"])
    if n == 0:
        fb = sum(cond["is_fallback"])
        return {"fallback": fb / cond["n_trials"]} if cond["n_trials"] else {}
    counts: dict[str, int] = {}
    for es in cond["early_stop"]:
        k = es if es else "none"
        counts[k] = counts.get(k, 0) + 1
    return {k: v / n for k, v in counts.items()}


def classify_phase(q_ea: float, pm_rate: float, fallback_rate: float, accuracy: float) -> str:
    if accuracy > 0.4:
        return "ordered"
    effective_pm = pm_rate if not np.isnan(pm_rate) else fallback_rate
    if effective_pm > 0.6:
        return "paramagnetic"
    if not np.isnan(q_ea) and q_ea > 0.70:
        return "spin_glass"
    return "mixed"


class SpinGlassAnalyzer(BaseAnalyzer):
    """H-SG analyzer: P(q), q_EA, and time autocorrelation."""

    def _conditions_as_dicts(self) -> dict[tuple[int, float], dict]:
        data = self.load_all(load_hidden=True)
        out: dict[tuple[int, float], dict] = {}
        for key, cond in data.items():
            d = condition_to_dict(cond, self.layer)
            if d["hidden"]:
                out[key] = d
        return out

    @staticmethod
    def _render_pq_cell(ax: plt.Axes, cond: dict, i: int, j: int, N: int, T: float) -> None:
        q_vals = compute_pq(cond)
        acc = float(np.mean(cond["accuracy"])) if cond["accuracy"] else 0.0
        q_ea = compute_qea(cond)
        fb_rate = sum(cond["is_fallback"]) / cond["n_trials"]
        phase = classify_phase(q_ea, cond["pm_rate"], fb_rate, acc)
        color = PHASE_COLORS[phase]
        ax.hist(q_vals, bins=Q_BINS, color=color, alpha=0.75, density=True)
        ax.axvline(np.nanmean(q_vals), color="k", lw=1.2, ls="--", alpha=0.7)
        pm_str = f"{cond['pm_rate']:.0%}" if not np.isnan(cond["pm_rate"]) else "N/A"
        ax.text(0.04, 0.93, f"qbar={np.nanmean(q_vals):.2f}\npm={pm_str}", transform=ax.transAxes, fontsize=6, va="top", color="black")
        if i == 0:
            ax.set_title(f"T={T}", fontsize=8)
        if j == 0:
            ax.set_ylabel(f"N={N}", fontsize=8)
        ax.set_xlim(-0.1, 1.05)
        ax.tick_params(labelsize=6)

    @staticmethod
    def _render_pq_cell_na(ax: plt.Axes) -> None:
        ax.text(0.5, 0.5, "N/A", ha="center", va="center", transform=ax.transAxes, fontsize=8, color="gray")
        ax.set_xticks([])
        ax.set_yticks([])

    def _plot_pq_distributions(self, all_conds: dict[tuple[int, float], dict]):
        fig, axes = plt.subplots(len(self.ns), len(self.ts), figsize=(2.2 * len(self.ts), 2.0 * len(self.ns)), sharex=True, sharey=False)
        axes_arr = np.atleast_2d(axes)
        fig.suptitle(f"P(q) Overlap Distribution  ({self.layer})", fontsize=12, y=1.01)
        for i, N in enumerate(self.ns):
            for j, T in enumerate(self.ts):
                ax = axes_arr[i, j]
                cond = all_conds.get((N, T))
                if cond is None:
                    self._render_pq_cell_na(ax)
                else:
                    self._render_pq_cell(ax, cond, i, j, N, T)
        from matplotlib.patches import Patch

        legend_elements = [Patch(facecolor=PHASE_COLORS[p], label=p.replace("_", " ")) for p in ["ordered", "spin_glass", "mixed", "paramagnetic"]]
        fig.legend(handles=legend_elements, loc="lower center", ncol=4, fontsize=8, bbox_to_anchor=(0.5, -0.02))
        plt.tight_layout()
        return fig

    @staticmethod
    def _plot_qea_vs_t(ax: plt.Axes, all_conds: dict[tuple[int, float], dict], ns: list[int], ts: list[float], colors: np.ndarray) -> None:
        ax.set_title("q_EA  vs  Temperature")
        for idx, N in enumerate(ns):
            qea_row, ts_valid = [], []
            for T in ts:
                cond = all_conds.get((N, T))
                if cond is None:
                    continue
                qea_row.append(compute_qea(cond))
                ts_valid.append(T)
            ax.plot(ts_valid, qea_row, "o-", color=colors[idx], linewidth=1.8, markersize=6, label=f"N={N}")
        ax.set_xlabel("Temperature  T")
        ax.set_ylabel(r"$q_{EA}$")
        ax.set_ylim(0.4, 1.02)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

    @staticmethod
    def _plot_pm_rate_vs_t(ax: plt.Axes, all_conds: dict[tuple[int, float], dict], ns: list[int], ts: list[float], colors: np.ndarray) -> None:
        ax.set_title("PM rate  vs  Temperature\n(no_move_catchall fraction)")
        for idx, N in enumerate(ns):
            pm_row, ts_valid = [], []
            for T in ts:
                cond = all_conds.get((N, T))
                if cond is None:
                    continue
                pm_row.append(cond["pm_rate"])
                ts_valid.append(T)
            ax.plot(ts_valid, pm_row, "s-", color=colors[idx], linewidth=1.8, markersize=6, label=f"N={N}")
        ax.axhline(0.5, color="gray", ls="--", alpha=0.6, label="50%")
        ax.set_xlabel("Temperature  T")
        ax.set_ylabel("PM rate  (no_move_catchall)")
        ax.set_ylim(-0.05, 1.05)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

    @staticmethod
    def _plot_autocorr(ax: plt.Axes, all_conds: dict[tuple[int, float], dict], ns: list[int], ts: list[float]) -> None:
        ax.set_title(r"Time autocorrelation  $C(\Delta t)$")
        reps = [(ns[0], ts[len(ts) // 4]), (ns[0], ts[-1]), (ns[-1], ts[len(ts) // 4]), (ns[-1], ts[len(ts) // 2])]
        palette = ["#1f77b4", "#d62728", "#ff7f0e", "#9467bd"]
        for (N, T), color in zip(reps, palette):
            cond = all_conds.get((N, T))
            if cond is None:
                continue
            C = compute_autocorr(cond, max_lag=8)
            lags = np.arange(1, 9)
            valid = ~np.isnan(C)
            if valid.any():
                ax.plot(lags[valid], C[valid], "o-", color=color, linewidth=1.8, markersize=6, label=f"N={N}  T={T}")
        ax.set_xlabel(r"$\Delta t$  (move steps)")
        ax.set_ylabel(r"$C(\Delta t)$")
        ax.set_ylim(0.4, 1.02)
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

    @staticmethod
    def _plot_phase_heatmap(ax: plt.Axes, all_conds: dict[tuple[int, float], dict], ns: list[int], ts: list[float]) -> None:
        ax.set_title("Phase classification")
        phase_to_int = {"ordered": 3, "spin_glass": 2, "mixed": 1, "paramagnetic": 0}
        int_to_label = {3: "ordered", 2: "spin glass", 1: "mixed", 0: "paramagnetic"}
        cmap_phases = plt.cm.colors.ListedColormap([PHASE_COLORS["paramagnetic"], PHASE_COLORS["mixed"], PHASE_COLORS["spin_glass"], PHASE_COLORS["ordered"]])
        mat = np.full((len(ns), len(ts)), np.nan)
        for i, N in enumerate(ns):
            for j, T in enumerate(ts):
                cond = all_conds.get((N, T))
                if cond is None:
                    continue
                acc = float(np.mean(cond["accuracy"])) if cond["accuracy"] else 0.0
                qea = compute_qea(cond)
                fb = sum(cond["is_fallback"]) / cond["n_trials"]
                mat[i, j] = phase_to_int[classify_phase(qea, cond["pm_rate"], fb, acc)]
        im = ax.imshow(mat, aspect="auto", origin="lower", vmin=-0.5, vmax=3.5, cmap=cmap_phases, extent=[ts[0] - 0.1, ts[-1] + 0.1, ns[0] - 0.5, ns[-1] + 0.5])
        cbar = plt.colorbar(im, ax=ax, ticks=[0, 1, 2, 3])
        cbar.ax.set_yticklabels([int_to_label[i] for i in [0, 1, 2, 3]], fontsize=8)
        ax.set_xlabel("Temperature  T")
        ax.set_ylabel("Disk count  N")
        ax.set_yticks(ns)
        ax.set_xticks(ts)
        ax.tick_params(axis="x", rotation=45)

    def _plot_summary(self, all_conds: dict[tuple[int, float], dict]):
        fig = plt.figure(figsize=(14, 10))
        gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.38, wspace=0.32)
        axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])]
        fig.suptitle(f"P(q) Analysis Summary  ({self.layer})", fontsize=13)
        colors = plt.cm.tab10(np.linspace(0, 0.6, len(self.ns)))
        self._plot_qea_vs_t(axes[0], all_conds, self.ns, self.ts, colors)
        self._plot_pm_rate_vs_t(axes[1], all_conds, self.ns, self.ts, colors)
        self._plot_autocorr(axes[2], all_conds, self.ns, self.ts)
        self._plot_phase_heatmap(axes[3], all_conds, self.ns, self.ts)
        return fig

    @staticmethod
    def _find_crossing(vals: list[float], xs: list[float], threshold: float) -> float | None:
        for j in range(len(xs) - 1):
            if vals[j] < threshold <= vals[j + 1]:
                slope = (vals[j + 1] - vals[j]) / (xs[j + 1] - xs[j])
                return xs[j] + (threshold - vals[j]) / slope
        return None

    def _print_report(self, all_conds: dict[tuple[int, float], dict]) -> None:
        print(f"\n{'='*80}")
        print("  P(q) Analysis Report")
        print(f"{'='*80}")
        header = f"{'N':>3} {'T':>5} | {'q_EA':>6} | {'qbar_inter':>10} | {'q_std':>6} | {'pm%':>5} | {'acc':>5} | phase"
        print(header)
        print("-" * len(header))
        for N in self.ns:
            for T in self.ts:
                cond = all_conds.get((N, T))
                if cond is None:
                    continue
                q_vals = compute_pq(cond)
                qea = compute_qea(cond)
                acc = float(np.mean(cond["accuracy"])) if cond["accuracy"] else 0.0
                pm = cond["pm_rate"]
                fb = sum(cond["is_fallback"]) / cond["n_trials"]
                phase = classify_phase(qea, pm, fb, acc)
                qea_s = f"{qea:.3f}" if not np.isnan(qea) else "  nan"
                pm_s = f"{pm:.0%}" if not np.isnan(pm) else " N/A"
                print(f"{N:>3} {T:>5.1f} | {qea_s:>6} | {np.nanmean(q_vals):>10.4f} | {np.nanstd(q_vals):>6.4f} | {pm_s:>5} | {acc:>5.2f} | {phase}")
            print()
        print(f"\n{'='*80}")
        print("  崩壊モード遷移温度 T_SG->PM（PM率 = 50% 交差点、no_move_catchall 基準）")
        print(f"{'='*80}")
        for N in self.ns:
            pm_vals, ts_valid = [], []
            for T in self.ts:
                cond = all_conds.get((N, T))
                if cond is None or np.isnan(cond["pm_rate"]):
                    continue
                pm_vals.append(cond["pm_rate"])
                ts_valid.append(T)
            T_trans = self._find_crossing(pm_vals, ts_valid, threshold=0.5)
            if T_trans is not None:
                print(f"  N={N}: T_{{SG->PM}} ≈ {T_trans:.2f}")
            else:
                pm_max = max(pm_vals) if pm_vals else float("nan")
                print(f"  N={N}: 遷移が範囲内に見つからない（PM率最大={pm_max:.0%}）")

    def run_analysis(self) -> AnalysisResult:
        all_conds = self._conditions_as_dicts()
        fig_dist = self._plot_pq_distributions(all_conds)
        fig_summary = self._plot_summary(all_conds)
        paths = [self._save_figure(fig_dist, "pq_distributions"), self._save_figure(fig_summary, "pq_summary")]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self._print_report(all_conds)
        metrics = {
            "q_EA": {k: compute_qea(v) for k, v in all_conds.items()},
            "pm_rate": {k: v["pm_rate"] for k, v in all_conds.items()},
        }
        return AnalysisResult("spin_glass", paths, metrics, buf.getvalue())
