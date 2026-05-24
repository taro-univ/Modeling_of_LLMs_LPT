from __future__ import annotations

import contextlib
import io
import warnings
from typing import Dict, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit

from analysis.base_analyzer import AnalysisResult, BaseAnalyzer, ConditionData


COLORS = {
    2: "#1f77b4",
    3: "#ff7f0e",
    4: "#2ca02c",
    5: "#d62728",
    6: "#9467bd",
}


def _power_law(x: np.ndarray, tau0: float, Tc: float, znu: float) -> np.ndarray:
    return tau0 * np.abs(x - Tc) ** (-znu)


def fit_critical_slowing(Ts: np.ndarray, taus: np.ndarray, Tc_init: float, side: str = "both") -> Optional[Dict]:
    mask = np.isfinite(taus) & (taus > 0)
    if side == "left":
        mask &= Ts < Tc_init
    elif side == "right":
        mask &= Ts > Tc_init
    if mask.sum() < 3:
        return None
    Tf, tf = Ts[mask], taus[mask]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            p0 = [tf.mean(), Tc_init, 0.5]
            bounds = ([0, max(0, Tc_init - 0.5), 0.01], [tf.max() * 10, Tc_init + 0.5, 5.0])
            popt, _ = curve_fit(_power_law, Tf, tf, p0=p0, bounds=bounds, maxfev=5000)
        tau0, Tc, znu = popt
        ss_res = np.sum((tf - _power_law(Tf, *popt)) ** 2)
        ss_tot = np.sum((tf - tf.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        return {"Tc": Tc, "znu": znu, "tau0": tau0, "r2": r2}
    except Exception:
        return None


def build_summary_table(data: Dict[int, list[Dict]]) -> Dict[int, Dict]:
    tables: Dict[int, Dict] = {}
    for N, conds in data.items():
        Ts, mu_v, sem_v, mu_i, sem_i, fb, nv = [], [], [], [], [], [], []
        for c in conds:
            Ts.append(c["T"])
            fb.append(c["fallback_rate"])
            n_v = len(c["valid_taus"])
            nv.append(n_v)
            if n_v > 0:
                mu_v.append(float(np.mean(c["valid_taus"])))
                sem_v.append(float(np.std(c["valid_taus"])) / np.sqrt(n_v))
            else:
                mu_v.append(float("nan"))
                sem_v.append(float("nan"))
            n_i = len(c["imputed_taus"])
            if n_i > 0:
                mu_i.append(float(np.mean(c["imputed_taus"])))
                sem_i.append(float(np.std(c["imputed_taus"])) / np.sqrt(n_i))
            else:
                mu_i.append(float("nan"))
                sem_i.append(float("nan"))
        tables[N] = {
            "T": np.array(Ts),
            "mean_tau_valid": np.array(mu_v),
            "sem_tau_valid": np.array(sem_v),
            "mean_tau_imputed": np.array(mu_i),
            "sem_tau_imputed": np.array(sem_i),
            "fallback_rate": np.array(fb),
            "n_valid": np.array(nv),
        }
    return tables


class CriticalDynamicsAnalyzer(BaseAnalyzer):
    """H-CD analyzer: critical slowing down."""

    def __init__(self, *args, num_predict_fallback: int = 4096, no_fit: bool = False, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.num_predict_fallback = num_predict_fallback
        self.no_fit = no_fit

    def _condition_to_tau_dict(self, cond: ConditionData) -> dict:
        valid_taus: list[int] = []
        imputed_taus: list[int] = []
        fallback_count = 0
        for ms, fb in zip(cond.move_steps, cond.is_fallback):
            if not fb and len(ms) > 0:
                first = int(ms[0])
                valid_taus.append(first)
                imputed_taus.append(first)
            else:
                fallback_count += 1
                imputed_taus.append(self.num_predict_fallback)
        n = len(cond.move_steps)
        return {
            "N": cond.N,
            "T": cond.T,
            "n_trials": n,
            "valid_taus": valid_taus,
            "fallback_count": fallback_count,
            "imputed_taus": imputed_taus,
            "fallback_rate": fallback_count / n if n > 0 else float("nan"),
        }

    def _collect_all(self) -> Dict[int, list[Dict]]:
        conditions = self.load_all(load_hidden=True)
        by_n: Dict[int, list[Dict]] = {}
        for cond in conditions.values():
            if not cond.move_steps:
                continue
            by_n.setdefault(cond.N, []).append(self._condition_to_tau_dict(cond))
        return {N: sorted(vals, key=lambda c: c["T"]) for N, vals in by_n.items()}

    @staticmethod
    def _estimate_tc_init(tbl: Dict) -> float:
        mu = tbl["mean_tau_valid"]
        T = tbl["T"]
        mask = np.isfinite(mu)
        if not mask.any():
            return 1.0
        return float(T[mask][np.argmax(mu[mask])])

    def _run_fits(self, tables: Dict[int, Dict], ns_available: list[int]) -> Dict[int, Optional[Dict]]:
        fit_results: Dict[int, Optional[Dict]] = {}
        if self.no_fit:
            for N in ns_available:
                fit_results[N] = None
            return fit_results
        for N in ns_available:
            tbl = tables[N]
            Tc0 = self._estimate_tc_init(tbl)
            fit_results[N] = fit_critical_slowing(tbl["T"], tbl["mean_tau_valid"], Tc_init=Tc0, side="both")
        return fit_results

    @staticmethod
    def plot_tau_vs_T(tables: Dict[int, Dict], ns: list[int], fit_results: Dict[int, Optional[Dict]]):
        fig, axes = plt.subplots(1, len(ns), figsize=(4.5 * len(ns), 4.5), sharey=False)
        if len(ns) == 1:
            axes = [axes]
        for ax, N in zip(axes, ns):
            if N not in tables:
                ax.set_title(f"N={N} (no data)")
                continue
            tbl = tables[N]
            T, mu, sem = tbl["T"], tbl["mean_tau_valid"], tbl["sem_tau_valid"]
            color = COLORS.get(N, "gray")
            mask = np.isfinite(mu)
            ax.errorbar(T[mask], mu[mask], yerr=sem[mask], fmt="o-", color=color, capsize=4, linewidth=1.8, markersize=6, label=f"N={N} valid trials")
            fr = fit_results.get(N)
            if fr and mask.any():
                T_fine = np.linspace(T[mask].min(), T[mask].max(), 300)
                left = T_fine[T_fine < fr["Tc"] - 0.05]
                right = T_fine[T_fine > fr["Tc"] + 0.05]
                if len(left):
                    ax.plot(left, _power_law(left, fr["tau0"], fr["Tc"], fr["znu"]), "--", color=color, alpha=0.6, linewidth=1.2)
                if len(right):
                    ax.plot(right, _power_law(right, fr["tau0"], fr["Tc"], fr["znu"]), "--", color=color, alpha=0.6, linewidth=1.2)
                ax.axvline(fr["Tc"], color=color, linestyle=":", alpha=0.5, linewidth=1)
            ax.set_xlabel("Temperature $T$", fontsize=11)
            ax.set_ylabel("First-move step $\\tau$", fontsize=11)
            ax.set_title(f"N={N}", fontsize=12)
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3)
            ax.set_xlim(left=0)
        fig.suptitle("Critical Slowing Down: $\\tau$ vs $T$", fontsize=13, fontweight="bold")
        fig.tight_layout()
        return fig

    @staticmethod
    def plot_fallback_rate(tables: Dict[int, Dict], ns: list[int]):
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for N in ns:
            if N not in tables:
                continue
            tbl = tables[N]
            T, fb = tbl["T"], tbl["fallback_rate"]
            color = COLORS.get(N, "gray")
            ax.plot(T, fb, "o-", color=color, linewidth=1.8, markersize=6, label=f"N={N}")
            for i in range(len(T) - 1):
                if np.isfinite(fb[i]) and np.isfinite(fb[i + 1]) and fb[i] < 0.5 <= fb[i + 1]:
                    Tc_cross = T[i] + (T[i + 1] - T[i]) * (0.5 - fb[i]) / (fb[i + 1] - fb[i])
                    ax.axvline(Tc_cross, color=color, linestyle=":", alpha=0.5)
                    ax.text(Tc_cross + 0.02, 0.52, f"$T_{{SG->PM}}$={Tc_cross:.2f}", fontsize=7, color=color)
        ax.axhline(0.5, color="k", linestyle="--", linewidth=0.8, label="50% threshold")
        ax.set_xlabel("Temperature $T$", fontsize=11)
        ax.set_ylabel("Fallback rate (no-move fraction)", fontsize=11)
        ax.set_title("Paramagnetic Phase Indicator: Fallback Rate vs $T$", fontsize=12)
        ax.legend(fontsize=9)
        ax.set_ylim(-0.05, 1.05)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        return fig

    @staticmethod
    def plot_tau_imputed(tables: Dict[int, Dict], ns: list[int]):
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for N in ns:
            if N not in tables:
                continue
            tbl = tables[N]
            T, mu, sem = tbl["T"], tbl["mean_tau_imputed"], tbl["sem_tau_imputed"]
            color = COLORS.get(N, "gray")
            mask = np.isfinite(mu)
            ax.errorbar(T[mask], mu[mask], yerr=sem[mask], fmt="s--", color=color, capsize=3, linewidth=1.4, markersize=5, alpha=0.8, label=f"N={N}")
        ax.set_xlabel("Temperature $T$", fontsize=11)
        ax.set_ylabel("First-move step $\\tau$ (imputed)", fontsize=11)
        ax.set_title("Critical Slowing Down (fallback imputed as num_predict)", fontsize=12)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        return fig

    @staticmethod
    def plot_combined(tables: Dict[int, Dict], ns: list[int], fit_results: Dict[int, Optional[Dict]]):
        fig, axes = plt.subplots(2, 2, figsize=(12, 9))
        ax_tau, ax_fb, ax_imp, ax_log = axes.flat
        for N in ns:
            if N not in tables:
                continue
            tbl = tables[N]
            T, mu_v, sem_v = tbl["T"], tbl["mean_tau_valid"], tbl["sem_tau_valid"]
            mu_i, sem_i = tbl["mean_tau_imputed"], tbl["sem_tau_imputed"]
            fb = tbl["fallback_rate"]
            color = COLORS.get(N, "gray")
            mask_v = np.isfinite(mu_v)
            ax_tau.errorbar(T[mask_v], mu_v[mask_v], yerr=sem_v[mask_v], fmt="o-", color=color, capsize=3, linewidth=1.6, markersize=5, label=f"N={N}")
            ax_fb.plot(T, fb, "o-", color=color, linewidth=1.6, markersize=5, label=f"N={N}")
            mask_i = np.isfinite(mu_i)
            ax_imp.errorbar(T[mask_i], mu_i[mask_i], yerr=sem_i[mask_i], fmt="s--", color=color, capsize=3, linewidth=1.3, markersize=4, alpha=0.8, label=f"N={N}")
            fr = fit_results.get(N)
            if fr and mask_v.sum() >= 3:
                dT = np.abs(T[mask_v] - fr["Tc"])
                tau_v = mu_v[mask_v]
                valid_log = (dT > 0.01) & (tau_v > 0)
                if valid_log.sum() >= 2:
                    ax_log.scatter(np.log10(dT[valid_log]), np.log10(tau_v[valid_log]), color=color, s=40, label=f"N={N} ($z\\nu$={fr['znu']:.2f})")
                    coeffs = np.polyfit(np.log10(dT[valid_log]), np.log10(tau_v[valid_log]), 1)
                    x_fit = np.linspace(np.log10(dT[valid_log]).min(), np.log10(dT[valid_log]).max(), 50)
                    ax_log.plot(x_fit, np.polyval(coeffs, x_fit), "--", color=color, alpha=0.6, linewidth=1)
        ax_tau.set_xlabel("Temperature $T$")
        ax_tau.set_ylabel("First-move step $\\tau$")
        ax_tau.set_title("(A) Critical Slowing Down ($\\tau$ valid trials)")
        ax_tau.legend(fontsize=8)
        ax_tau.grid(True, alpha=0.3)
        ax_fb.axhline(0.5, color="k", linestyle="--", linewidth=0.8)
        ax_fb.set_xlabel("Temperature $T$")
        ax_fb.set_ylabel("Fallback rate")
        ax_fb.set_title("(B) Paramagnetic Phase Indicator")
        ax_fb.set_ylim(-0.05, 1.05)
        ax_fb.legend(fontsize=8)
        ax_fb.grid(True, alpha=0.3)
        ax_imp.set_xlabel("Temperature $T$")
        ax_imp.set_ylabel("$\\tau$ (imputed)")
        ax_imp.set_title("(C) Upper-bound estimate (fallback = num_predict)")
        ax_imp.legend(fontsize=8)
        ax_imp.grid(True, alpha=0.3)
        ax_log.set_xlabel("$\\log_{10}|T - T_c|$")
        ax_log.set_ylabel("$\\log_{10}\\tau$")
        ax_log.set_title("(D) Power-law check: $\\tau \\sim |T-T_c|^{-z\\nu}$")
        ax_log.legend(fontsize=7)
        ax_log.grid(True, alpha=0.3)
        fig.suptitle("Critical Slowing Down Analysis", fontsize=14, fontweight="bold")
        fig.tight_layout()
        return fig

    @staticmethod
    def _print_report(tables: Dict[int, Dict], fit_results: Dict[int, Optional[Dict]]) -> None:
        print()
        print("=" * 70)
        print("  Critical Slowing Down — Summary Report")
        print("=" * 70)
        for N in sorted(tables.keys()):
            tbl = tables[N]
            fr = fit_results.get(N)
            print(f"\n  N = {N}")
            print(f"  {'T':>6}  {'n_valid':>8}  {'mean_tau':>10}  {'SEM':>8}  {'fallback%':>10}")
            print("  " + "-" * 50)
            for i, T in enumerate(tbl["T"]):
                nv = int(tbl["n_valid"][i])
                mu = tbl["mean_tau_valid"][i]
                sem = tbl["sem_tau_valid"][i]
                fb = tbl["fallback_rate"][i] * 100
                mu_s = f"{mu:10.1f}" if np.isfinite(mu) else f"{'-':>10}"
                sem_s = f"{sem:8.1f}" if np.isfinite(sem) else f"{'-':>8}"
                print(f"  {T:>6.2f}  {nv:>8}  {mu_s}  {sem_s}  {fb:>9.1f}%")
            if fr:
                print("\n  Power-law fit: tau ~ |T - T_c|^{-znu}")
                print(f"    T_c  = {fr['Tc']:.3f}")
                print(f"    z*nu = {fr['znu']:.3f}")
                print(f"    tau0 = {fr['tau0']:.1f}")
                print(f"    R2   = {fr['r2']:.3f}")
            else:
                print("\n  Power-law fit: not available (insufficient data)")
        print()
        print("  T_{SG->PM} (fallback rate = 50% crossing):")
        for N in sorted(tables.keys()):
            tbl = tables[N]
            T, fb = tbl["T"], tbl["fallback_rate"]
            Tc_cross = None
            for i in range(len(T) - 1):
                if np.isfinite(fb[i]) and np.isfinite(fb[i + 1]) and fb[i] < 0.5 <= fb[i + 1]:
                    Tc_cross = T[i] + (T[i + 1] - T[i]) * (0.5 - fb[i]) / (fb[i + 1] - fb[i])
                    break
            if Tc_cross:
                print(f"    N={N}: T_{{SG->PM}} ≈ {Tc_cross:.2f}")
            else:
                print(f"    N={N}: T_{{SG->PM}} not detected in T range")
        print()
        print("=" * 70)

    def run_analysis(self) -> AnalysisResult:
        data = self._collect_all()
        tables = build_summary_table(data)
        ns_available = [N for N in self.ns if N in tables]
        fit_results = self._run_fits(tables, ns_available)
        paths = [
            self._save_figure(self.plot_tau_vs_T(tables, ns_available, fit_results), "slowing_tau_vs_T"),
            self._save_figure(self.plot_fallback_rate(tables, ns_available), "slowing_fallback_rate"),
            self._save_figure(self.plot_tau_imputed(tables, ns_available), "slowing_tau_imputed"),
            self._save_figure(self.plot_combined(tables, ns_available, fit_results), "slowing_combined"),
        ]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self._print_report(tables, fit_results)
        return AnalysisResult("critical_dynamics", paths, {"tables": tables, "fit_results": fit_results}, buf.getvalue())
