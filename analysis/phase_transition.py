from __future__ import annotations

import contextlib
import io

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np

from analysis.base_analyzer import AnalysisResult, BaseAnalyzer, ConditionData


BOUNDARY_THRESHOLD = 0.5


class PhaseTransitionAnalyzer(BaseAnalyzer):
    """H-PT analyzer: order-disorder phase transition and Tc(N)."""

    def __init__(self, *args, threshold: float = BOUNDARY_THRESHOLD, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.threshold = threshold

    def _compute_stats(self, cond: ConditionData) -> dict:
        trials = cond.trials
        acc = [r["accuracy"] for r in trials]
        tok = [r.get("total_tokens", np.nan) for r in trials]
        v = [r.get("v_score", np.nan) for r in trials]
        es: dict[str, int] = {}
        for r in trials:
            k = r.get("early_stop") or "none"
            es[k] = es.get(k, 0) + 1
        return {
            "accuracy_mean": float(np.mean(acc)),
            "accuracy_std": float(np.std(acc)),
            "token_mean": float(np.nanmean(tok)) if not np.all(np.isnan(tok)) else float("nan"),
            "token_std": float(np.nanstd(tok)) if not np.all(np.isnan(tok)) else float("nan"),
            "v_mean": float(np.nanmean(v)) if not np.all(np.isnan(v)) else float("nan"),
            "v_std": float(np.nanstd(v)) if not np.all(np.isnan(v)) else float("nan"),
            "n_trials": len(trials),
            "early_stop": es,
        }

    @staticmethod
    def _build_matrix(stats: dict[tuple[int, float], dict], ns: list[int], ts: list[float], key: str) -> np.ndarray:
        mat = np.full((len(ns), len(ts)), np.nan)
        for i, N in enumerate(ns):
            for j, T in enumerate(ts):
                if (N, T) in stats:
                    mat[i, j] = stats[(N, T)][key]
        return mat

    @staticmethod
    def _estimate_boundary(
        acc_mat: np.ndarray,
        ns: list[int],
        ts: list[float],
        threshold: float = BOUNDARY_THRESHOLD,
    ) -> dict[int, float | None]:
        boundary: dict[int, float | None] = {}
        for i, N in enumerate(ns):
            row = acc_mat[i, :]
            valid = ~np.isnan(row)
            if valid.sum() < 2:
                boundary[N] = None
                continue
            ts_v = np.array(ts)[valid]
            row_v = row[valid]
            Tc = None
            for j in range(len(ts_v) - 1):
                if row_v[j] >= threshold > row_v[j + 1]:
                    slope = (row_v[j + 1] - row_v[j]) / (ts_v[j + 1] - ts_v[j])
                    Tc = ts_v[j] + (threshold - row_v[j]) / slope
                    break
            boundary[N] = Tc
        return boundary

    @staticmethod
    def _plot_heatmap_panel(ax, acc_mat: np.ndarray, ns: list[int], ts: list[float], boundary: dict[int, float | None]) -> None:
        cmap = mcolors.LinearSegmentedColormap.from_list("order_disorder", ["#d62728", "#ffffff", "#1f77b4"])
        im = ax.imshow(
            acc_mat,
            aspect="auto",
            origin="lower",
            vmin=0.0,
            vmax=1.0,
            cmap=cmap,
            extent=[ts[0] - 0.1, ts[-1] + 0.1, ns[0] - 0.5, ns[-1] + 0.5],
        )
        plt.colorbar(im, ax=ax, label="Accuracy  m(N, T)")
        bc_ns = [N for N in ns if boundary.get(N) is not None]
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

    @staticmethod
    def _plot_accuracy_curve_panel(ax, acc_mat: np.ndarray, acc_std: np.ndarray, ns: list[int], ts: list[float], colors) -> None:
        for i, N in enumerate(ns):
            row, row_s = acc_mat[i, :], acc_std[i, :]
            valid = ~np.isnan(row)
            ax.errorbar(np.array(ts)[valid], row[valid], yerr=row_s[valid], fmt="o-", capsize=4, color=colors[i], linewidth=1.8, markersize=6, label=f"N={N}")
        ax.axhline(y=BOUNDARY_THRESHOLD, color="gray", linestyle="--", alpha=0.6, label=f"threshold={BOUNDARY_THRESHOLD}")
        ax.set_xlabel("Temperature  T")
        ax.set_ylabel("Accuracy")
        ax.set_title("Accuracy vs Temperature  (per N)")
        ax.set_ylim(-0.05, 1.05)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

    @staticmethod
    def _plot_token_curve_panel(ax, tok_mat: np.ndarray, tok_std: np.ndarray, ns: list[int], ts: list[float], colors) -> None:
        for i, N in enumerate(ns):
            row, row_s = tok_mat[i, :], tok_std[i, :]
            valid = ~np.isnan(row)
            ax.errorbar(np.array(ts)[valid], row[valid], yerr=row_s[valid], fmt="s-", capsize=4, color=colors[i], linewidth=1.8, markersize=6, label=f"N={N}")
        ax.set_xlabel("Temperature  T")
        ax.set_ylabel("Total Tokens")
        ax.set_title("Total Tokens vs Temperature  (per N)")
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

    @staticmethod
    def _plot_boundary_fit_panel(ax, ns: list[int], boundary: dict[int, float | None]) -> None:
        bc_ns = [N for N in ns if boundary.get(N) is not None]
        bc_Tcs = [boundary[N] for N in bc_ns]
        if not bc_ns:
            ax.set_xlabel("Disk count  N")
            ax.set_ylabel(r"$T_c(N)$")
            ax.set_title(r"Phase Boundary $T_c(N)$")
            return
        ax.plot(bc_ns, bc_Tcs, "ko-", linewidth=2, markersize=9, zorder=5, label=r"$T_c(N)$  (interpolated)")
        if len(bc_ns) >= 3:
            ns_arr = np.array(bc_ns, dtype=float)
            Tcs_arr = np.array(bc_Tcs, dtype=float)
            ns_fine = np.linspace(ns_arr[0], ns_arr[-1], 100)
            try:
                coeffs = np.polyfit(np.log(ns_arr), np.log(Tcs_arr), 1)
                ax.plot(ns_fine, np.exp(coeffs[1]) * ns_fine ** (-coeffs[0]), "r--", linewidth=1.5, label=fr"Power law: $T_c \propto N^{{-{-coeffs[0]:.2f}}}$")
            except Exception:
                pass
            try:
                coeffs2 = np.polyfit(ns_arr, np.log(Tcs_arr), 1)
                ax.plot(ns_fine, np.exp(coeffs2[1]) * np.exp(coeffs2[0] * ns_fine), "b-.", linewidth=1.5, label=fr"Exp law: $T_c \propto e^{{-{-coeffs2[0]:.2f}N}}$")
            except Exception:
                pass
        ax.set_xlabel("Disk count  N")
        ax.set_ylabel(r"$T_c(N)$")
        ax.set_title(r"Phase Boundary $T_c(N)$")
        ax.set_xticks(ns)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

    def _plot_phase_diagram(self, stats: dict[tuple[int, float], dict], boundary: dict[int, float | None]):
        acc_mat = self._build_matrix(stats, self.ns, self.ts, "accuracy_mean")
        acc_std = self._build_matrix(stats, self.ns, self.ts, "accuracy_std")
        tok_mat = self._build_matrix(stats, self.ns, self.ts, "token_mean")
        tok_std = self._build_matrix(stats, self.ns, self.ts, "token_std")
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle(f"Inference Collapse Phase Diagram  ({self.title})", fontsize=13)
        colors = plt.cm.tab10(np.linspace(0, 0.6, len(self.ns)))
        self._plot_heatmap_panel(axes[0, 0], acc_mat, self.ns, self.ts, boundary)
        self._plot_accuracy_curve_panel(axes[0, 1], acc_mat, acc_std, self.ns, self.ts, colors)
        self._plot_token_curve_panel(axes[1, 0], tok_mat, tok_std, self.ns, self.ts, colors)
        self._plot_boundary_fit_panel(axes[1, 1], self.ns, boundary)
        plt.tight_layout()
        return fig

    def _print_report(self, stats: dict[tuple[int, float], dict], boundary: dict[int, float | None]) -> None:
        print(f"\n{'='*75}")
        print("  Phase Diagram Report")
        print(f"{'='*75}")
        header = f"{'N':>3} |" + "".join(f"  T={T:<4}" for T in self.ts)
        print(header)
        print("-" * len(header))
        for N in self.ns:
            row_str = f"{N:>3} |"
            for T in self.ts:
                row_str += f"  {stats[(N, T)]['accuracy_mean']:.2f}  " if (N, T) in stats else "   --   "
            print(row_str)
        print(f"\n{'='*75}")
        print(f"  推定相境界 T_c(N)  (accuracy = {BOUNDARY_THRESHOLD} 交差点)")
        print(f"{'='*75}")
        for N in self.ns:
            Tc = boundary.get(N)
            if Tc is None:
                print(f"  N={N}: T_c > {max(self.ts):.1f}  (全温度域で acc >= {BOUNDARY_THRESHOLD})")
            else:
                print(f"  N={N}: T_c ≈ {Tc:.2f}")
        print(f"\n{'='*75}")
        print("  Early Stop 崩壊モード内訳")
        print(f"{'='*75}")
        for N in self.ns:
            print(f"  N={N}:")
            for T in self.ts:
                if (N, T) not in stats:
                    continue
                es = stats[(N, T)]["early_stop"]
                total = sum(es.values())
                breakdown = "  ".join(f"{k}:{v}/{total}" for k, v in sorted(es.items()))
                print(f"    T={T:.1f}: {breakdown}")

    def run_analysis(self) -> AnalysisResult:
        conditions = self.load_all(load_hidden=False)
        stats = {k: self._compute_stats(v) for k, v in conditions.items() if v.trials}
        acc_mat = self._build_matrix(stats, self.ns, self.ts, "accuracy_mean")
        boundary = self._estimate_boundary(acc_mat, self.ns, self.ts, threshold=self.threshold)
        fig = self._plot_phase_diagram(stats, boundary)
        figure_path = self._save_figure(fig, "phase_diagram")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self._print_report(stats, boundary)
        return AnalysisResult(
            analyzer_name="phase_transition",
            figure_paths=[figure_path],
            metrics={"Tc": boundary, "accuracy_grid": {k: v["accuracy_mean"] for k, v in stats.items()}},
            report_text=buf.getvalue(),
        )
