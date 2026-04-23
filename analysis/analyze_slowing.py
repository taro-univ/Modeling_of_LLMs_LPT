"""
analyze_slowing.py — 臨界減速（Critical Slowing Down）の検証

物理的仮説:
    相転移点 T_c 付近では緩和時間 τ が発散する:
        τ_relax ~ |T - T_c|^{-z*nu}

    LLM における対応:
        τ = first_move_step  （最初の Move が出るまでのトークン数）

    測定量:
        - mean_tau(N, T)   : 試行平均 first_move_step（T_c 付近で極大/発散）
        - fallback_rate    : Move ゼロ試行の割合（常磁性相の指標）
        - tau_valid_only   : Move が出た試行のみの first_move_step

    注意:
        fallback 試行（move_texts == '__fallback__'）は常磁性相の trial であり、
        first_move_step が定義できない。2 種類の集計を行う:
        (A) valid only  : fallback 除外 → スピングラス相の緩和時間
        (B) imputed     : fallback に num_predict を代入 → 上限として扱う

Usage:
    python3 analyze_slowing.py [--data-dirs DIR [DIR ...]] [--ns 2 3 4 5]
                                [--out-dir figures] [--no-fit]
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

PHASE_DIAGRAM_DIR = "results/hanoi/phase_diagram"
PQ_SWEEP_DIR      = "results/hanoi/pq_sweep"

COLORS = {
    2: "#1f77b4",
    3: "#ff7f0e",
    4: "#2ca02c",
    5: "#d62728",
    6: "#9467bd",
}

# ---------------------------------------------------------------------------
# データ読み込み
# ---------------------------------------------------------------------------

def _parse_NT(dirname: str) -> Optional[Tuple[int, float]]:
    """ディレクトリ名 'N{n}_T{t_tag}' から (N, T) を取得。"""
    m = re.match(r"N(\d+)_T(\d+)_?(\d*)", os.path.basename(dirname))
    if not m:
        return None
    N = int(m.group(1))
    int_part = m.group(2)
    dec_part  = m.group(3) if m.group(3) else "0"
    T = float(f"{int_part}.{dec_part}")
    return N, T


def load_condition(dirpath: str, num_predict_fallback: int = 4096) -> Dict:
    """
    1 条件分の npz を全て読み込み、first_move_step を集計する。

    Args:
        dirpath: N{n}_T{t} ディレクトリパス
        num_predict_fallback: fallback 試行に代入する上限値

    Returns:
        dict with keys:
            N, T, n_trials, valid_taus, fallback_count,
            imputed_taus, fallback_rate
    """
    npz_files = sorted(glob.glob(os.path.join(dirpath, "trial_*_hidden.npz")))
    if not npz_files:
        return {}

    nt = _parse_NT(dirpath)
    if nt is None:
        return {}
    N, T = nt

    valid_taus:   List[int] = []
    imputed_taus: List[int] = []
    fallback_count = 0

    for f in npz_files:
        try:
            d = np.load(f, allow_pickle=True)
        except Exception:
            continue
        ms = d["move_steps"]
        mt = d["move_texts"]

        # 有効 Move（fallback 以外）の先頭ステップを取得
        valid = [int(ms[i]) for i in range(len(mt))
                 if str(mt[i]) != "__fallback__"]

        if valid:
            first = valid[0]
            valid_taus.append(first)
            imputed_taus.append(first)
        else:
            fallback_count += 1
            imputed_taus.append(num_predict_fallback)

    n = len(npz_files)
    return {
        "N":              N,
        "T":              T,
        "n_trials":       n,
        "valid_taus":     valid_taus,
        "fallback_count": fallback_count,
        "imputed_taus":   imputed_taus,
        "fallback_rate":  fallback_count / n if n > 0 else float("nan"),
    }


def collect_all(data_dirs: List[str], num_predict_fallback: int = 4096) -> Dict[int, List[Dict]]:
    """
    複数ディレクトリ下の全条件を読み込み、N ごとに整理する。

    Returns:
        {N: sorted list of condition dicts by T}
    """
    all_conditions: Dict[int, List[Dict]] = {}

    for base in data_dirs:
        for subdir in sorted(glob.glob(os.path.join(base, "N*_T*"))):
            if not os.path.isdir(subdir):
                continue
            cond = load_condition(subdir, num_predict_fallback)
            if not cond:
                continue
            N = cond["N"]
            all_conditions.setdefault(N, []).append(cond)

    # T でソート、重複 (N, T) は valid_taus を統合
    merged: Dict[int, Dict[float, Dict]] = {}
    for N, conds in all_conditions.items():
        merged[N] = {}
        for c in conds:
            T = c["T"]
            if T not in merged[N]:
                merged[N][T] = c
            else:
                # 同一 (N, T) が複数ディレクトリに存在する場合はマージ
                ex = merged[N][T]
                ex["valid_taus"]    += c["valid_taus"]
                ex["imputed_taus"]  += c["imputed_taus"]
                ex["fallback_count"] += c["fallback_count"]
                ex["n_trials"]       += c["n_trials"]
                ex["fallback_rate"]  = (ex["fallback_count"] / ex["n_trials"]
                                        if ex["n_trials"] > 0 else float("nan"))

    result: Dict[int, List[Dict]] = {}
    for N, T_map in merged.items():
        result[N] = sorted(T_map.values(), key=lambda c: c["T"])

    return result


# ---------------------------------------------------------------------------
# スケーリングフィット
# ---------------------------------------------------------------------------

def _power_law(x: np.ndarray, tau0: float, Tc: float, znu: float) -> np.ndarray:
    """τ = tau0 * |T - Tc|^{-znu}"""
    return tau0 * np.abs(x - Tc) ** (-znu)


def fit_critical_slowing(
    Ts: np.ndarray,
    taus: np.ndarray,
    Tc_init: float,
    side: str = "both",
) -> Optional[Dict]:
    """
    τ ~ |T - T_c|^{-zν} の冪乗則フィット。

    Args:
        Ts:      温度配列
        taus:    mean_tau 配列（NaN を含む可能性あり）
        Tc_init: T_c の初期推定値
        side:    'left'  = T < T_c のみ
                 'right' = T > T_c のみ
                 'both'  = 両側

    Returns:
        {'Tc': float, 'znu': float, 'tau0': float, 'r2': float} or None
    """
    mask = np.isfinite(taus) & (taus > 0)
    if side == "left":
        mask &= (Ts < Tc_init)
    elif side == "right":
        mask &= (Ts > Tc_init)

    if mask.sum() < 3:
        return None

    Tf, tf = Ts[mask], taus[mask]

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            p0 = [tf.mean(), Tc_init, 0.5]
            bounds = ([0, max(0, Tc_init - 0.5), 0.01],
                      [tf.max() * 10, Tc_init + 0.5, 5.0])
            popt, _ = curve_fit(_power_law, Tf, tf, p0=p0,
                                bounds=bounds, maxfev=5000)
        tau0, Tc, znu = popt
        # R²
        ss_res = np.sum((tf - _power_law(Tf, *popt)) ** 2)
        ss_tot = np.sum((tf - tf.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        return {"Tc": Tc, "znu": znu, "tau0": tau0, "r2": r2}
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 集計テーブル作成
# ---------------------------------------------------------------------------

def build_summary_table(data: Dict[int, List[Dict]]) -> Dict[int, Dict]:
    """
    各 (N, T) の統計量をまとめたテーブルを作成する。

    Returns:
        {N: {'T': [...], 'mean_tau_valid': [...], 'sem_tau_valid': [...],
              'mean_tau_imputed': [...], 'fallback_rate': [...], 'n_valid': [...]}}
    """
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
            "T":               np.array(Ts),
            "mean_tau_valid":  np.array(mu_v),
            "sem_tau_valid":   np.array(sem_v),
            "mean_tau_imputed":np.array(mu_i),
            "sem_tau_imputed": np.array(sem_i),
            "fallback_rate":   np.array(fb),
            "n_valid":         np.array(nv),
        }
    return tables


# ---------------------------------------------------------------------------
# プロット
# ---------------------------------------------------------------------------

def plot_tau_vs_T(
    tables: Dict[int, Dict],
    ns: List[int],
    fit_results: Dict[int, Optional[Dict]],
    out_path: str,
) -> None:
    """
    Figure 1: τ(T) — 臨界減速プロット（valid のみ）

    各 N について τ = first_move_step の平均 ± SEM を T に対してプロット。
    T_c 付近の発散（臨界減速）を可視化する。
    """
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
        ax.errorbar(T[mask], mu[mask], yerr=sem[mask],
                    fmt="o-", color=color, capsize=4, linewidth=1.8,
                    markersize=6, label=f"N={N} valid trials")

        # フィット結果を重ねる
        fr = fit_results.get(N)
        if fr:
            T_fine = np.linspace(T[mask].min(), T[mask].max(), 300)
            # T_c の両側で描画（特異点を避ける）
            left  = T_fine[T_fine < fr["Tc"] - 0.05]
            right = T_fine[T_fine > fr["Tc"] + 0.05]
            if len(left):
                ax.plot(left, _power_law(left, fr["tau0"], fr["Tc"], fr["znu"]),
                        "--", color=color, alpha=0.6, linewidth=1.2)
            if len(right):
                ax.plot(right, _power_law(right, fr["tau0"], fr["Tc"], fr["znu"]),
                        "--", color=color, alpha=0.6, linewidth=1.2)
            ax.axvline(fr["Tc"], color=color, linestyle=":", alpha=0.5, linewidth=1)
            ax.text(fr["Tc"] + 0.02, ax.get_ylim()[1] * 0.9 if ax.get_ylim()[1] > 0 else 1000,
                    f"$T_c$={fr['Tc']:.2f}\n$z\\nu$={fr['znu']:.2f}\n$R^2$={fr['r2']:.2f}",
                    fontsize=7, color=color, va="top")

        ax.set_xlabel("Temperature $T$", fontsize=11)
        ax.set_ylabel("First-move step $\\tau$", fontsize=11)
        ax.set_title(f"N={N}", fontsize=12)
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(left=0)

    fig.suptitle("Critical Slowing Down: $\\tau$ vs $T$", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  -> saved: {out_path}")


def plot_fallback_rate(
    tables: Dict[int, Dict],
    ns: List[int],
    out_path: str,
) -> None:
    """
    Figure 2: fallback rate vs T — 常磁性相への転移を可視化。

    fallback_rate が 0.5 を超える温度 ≈ T_{SG->PM}
    """
    fig, ax = plt.subplots(figsize=(7, 4.5))

    for N in ns:
        if N not in tables:
            continue
        tbl = tables[N]
        T, fb = tbl["T"], tbl["fallback_rate"]
        color = COLORS.get(N, "gray")
        ax.plot(T, fb, "o-", color=color, linewidth=1.8, markersize=6, label=f"N={N}")

        # 50% crossing の推定
        for i in range(len(T) - 1):
            if np.isfinite(fb[i]) and np.isfinite(fb[i + 1]):
                if fb[i] < 0.5 <= fb[i + 1]:
                    Tc_cross = T[i] + (T[i + 1] - T[i]) * (0.5 - fb[i]) / (fb[i + 1] - fb[i])
                    ax.axvline(Tc_cross, color=color, linestyle=":", alpha=0.5)
                    ax.text(Tc_cross + 0.02, 0.52,
                            f"$T_{{SG→PM}}$={Tc_cross:.2f}", fontsize=7, color=color)

    ax.axhline(0.5, color="k", linestyle="--", linewidth=0.8, label="50% threshold")
    ax.set_xlabel("Temperature $T$", fontsize=11)
    ax.set_ylabel("Fallback rate (no-move fraction)", fontsize=11)
    ax.set_title("Paramagnetic Phase Indicator: Fallback Rate vs $T$", fontsize=12)
    ax.legend(fontsize=9)
    ax.set_ylim(-0.05, 1.05)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  -> saved: {out_path}")


def plot_tau_imputed(
    tables: Dict[int, Dict],
    ns: List[int],
    out_path: str,
) -> None:
    """
    Figure 3: τ(T) — fallback を num_predict で代入した版（上限推定）

    fallback 試行を除外すると T_c 付近で sample bias が生じるため、
    imputed 版でも発散傾向を確認する。
    """
    fig, ax = plt.subplots(figsize=(7, 4.5))

    for N in ns:
        if N not in tables:
            continue
        tbl = tables[N]
        T, mu, sem = tbl["T"], tbl["mean_tau_imputed"], tbl["sem_tau_imputed"]
        color = COLORS.get(N, "gray")
        mask = np.isfinite(mu)
        ax.errorbar(T[mask], mu[mask], yerr=sem[mask],
                    fmt="s--", color=color, capsize=3, linewidth=1.4,
                    markersize=5, alpha=0.8, label=f"N={N}")

    ax.set_xlabel("Temperature $T$", fontsize=11)
    ax.set_ylabel("First-move step $\\tau$ (imputed)", fontsize=11)
    ax.set_title("Critical Slowing Down (fallback imputed as num_predict)", fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  -> saved: {out_path}")


def plot_combined(
    tables: Dict[int, Dict],
    ns: List[int],
    fit_results: Dict[int, Optional[Dict]],
    out_path: str,
) -> None:
    """
    Figure 4: 4 パネル統合図（論文用）

    (A) τ_valid vs T     — 臨界減速
    (B) fallback rate vs T — 常磁性相指標
    (C) τ_imputed vs T   — 上限推定
    (D) log τ vs log|T - T_c| — 冪乗則の直線性確認
    """
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    ax_tau, ax_fb, ax_imp, ax_log = axes.flat

    for N in ns:
        if N not in tables:
            continue
        tbl = tables[N]
        T, mu_v, sem_v = tbl["T"], tbl["mean_tau_valid"], tbl["sem_tau_valid"]
        mu_i, sem_i    = tbl["mean_tau_imputed"], tbl["sem_tau_imputed"]
        fb             = tbl["fallback_rate"]
        color          = COLORS.get(N, "gray")

        mask_v = np.isfinite(mu_v)
        # (A) τ_valid
        ax_tau.errorbar(T[mask_v], mu_v[mask_v], yerr=sem_v[mask_v],
                        fmt="o-", color=color, capsize=3, linewidth=1.6,
                        markersize=5, label=f"N={N}")

        # (B) fallback rate
        ax_fb.plot(T, fb, "o-", color=color, linewidth=1.6, markersize=5, label=f"N={N}")

        # (C) τ_imputed
        mask_i = np.isfinite(mu_i)
        ax_imp.errorbar(T[mask_i], mu_i[mask_i], yerr=sem_i[mask_i],
                        fmt="s--", color=color, capsize=3, linewidth=1.3,
                        markersize=4, alpha=0.8, label=f"N={N}")

        # (D) log-log: |T - T_c| vs τ （フィットがある場合のみ）
        fr = fit_results.get(N)
        if fr and mask_v.sum() >= 3:
            Tc = fr["Tc"]
            dT = np.abs(T[mask_v] - Tc)
            tau_v = mu_v[mask_v]
            valid_log = (dT > 0.01) & (tau_v > 0)
            if valid_log.sum() >= 2:
                ax_log.scatter(np.log10(dT[valid_log]),
                               np.log10(tau_v[valid_log]),
                               color=color, s=40, label=f"N={N} ($z\\nu$={fr['znu']:.2f})")
                # 回帰直線
                x_log = np.log10(dT[valid_log])
                y_log = np.log10(tau_v[valid_log])
                coeffs = np.polyfit(x_log, y_log, 1)
                x_fit = np.linspace(x_log.min(), x_log.max(), 50)
                ax_log.plot(x_fit, np.polyval(coeffs, x_fit),
                            "--", color=color, alpha=0.6, linewidth=1)

    # 軸設定
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
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  -> saved: {out_path}")


# ---------------------------------------------------------------------------
# コンソールレポート
# ---------------------------------------------------------------------------

def print_report(tables: Dict[int, Dict], fit_results: Dict[int, Optional[Dict]]) -> None:
    """集計結果とフィットパラメータを表形式で出力する。"""
    print()
    print("=" * 70)
    print("  Critical Slowing Down — Summary Report")
    print("=" * 70)

    for N in sorted(tables.keys()):
        tbl = tables[N]
        fr  = fit_results.get(N)
        print(f"\n  N = {N}")
        print(f"  {'T':>6}  {'n_valid':>8}  {'mean_tau':>10}  {'SEM':>8}  {'fallback%':>10}")
        print("  " + "-" * 50)
        for i, T in enumerate(tbl["T"]):
            nv   = int(tbl["n_valid"][i])
            mu   = tbl["mean_tau_valid"][i]
            sem  = tbl["sem_tau_valid"][i]
            fb   = tbl["fallback_rate"][i] * 100
            mu_s = f"{mu:10.1f}" if np.isfinite(mu) else f"{'—':>10}"
            sem_s= f"{sem:8.1f}"  if np.isfinite(sem) else f"{'—':>8}"
            print(f"  {T:>6.2f}  {nv:>8}  {mu_s}  {sem_s}  {fb:>9.1f}%")

        if fr:
            print(f"\n  Power-law fit: τ ~ |T - T_c|^{{-zν}}")
            print(f"    T_c  = {fr['Tc']:.3f}")
            print(f"    z*nu = {fr['znu']:.3f}")
            print(f"    tau0 = {fr['tau0']:.1f}")
            print(f"    R²   = {fr['r2']:.3f}")
        else:
            print(f"\n  Power-law fit: not available (insufficient data)")

    # SG→PM 転移温度の一覧
    print()
    print("  T_{SG->PM} (fallback rate = 50% crossing):")
    for N in sorted(tables.keys()):
        tbl = tables[N]
        T, fb = tbl["T"], tbl["fallback_rate"]
        Tc_cross = None
        for i in range(len(T) - 1):
            if np.isfinite(fb[i]) and np.isfinite(fb[i + 1]):
                if fb[i] < 0.5 <= fb[i + 1]:
                    Tc_cross = T[i] + (T[i + 1] - T[i]) * (0.5 - fb[i]) / (fb[i + 1] - fb[i])
                    break
        if Tc_cross:
            print(f"    N={N}: T_{{SG->PM}} ≈ {Tc_cross:.2f}")
        else:
            print(f"    N={N}: T_{{SG->PM}} not detected in T range")

    print()
    print("=" * 70)


# ---------------------------------------------------------------------------
# エントリポイント
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze critical slowing down from phase_diagram npz files."
    )
    parser.add_argument(
        "--data-dirs", nargs="+",
        default=[PHASE_DIAGRAM_DIR, PQ_SWEEP_DIR],
        help="npz が格納されたディレクトリ群"
    )
    parser.add_argument(
        "--ns", nargs="+", type=int, default=[2, 3, 4, 5],
        help="プロット対象の N 値"
    )
    parser.add_argument(
        "--out-dir", default="figures",
        help="図の出力先ディレクトリ"
    )
    parser.add_argument(
        "--num-predict", type=int, default=4096,
        help="fallback 試行に代入する上限トークン数"
    )
    parser.add_argument(
        "--no-fit", action="store_true",
        help="冪乗則フィットをスキップする"
    )
    parser.add_argument(
        "--tc-init", nargs="+", type=float, default=None,
        help="各 N の T_c 初期値（--ns の順で指定、省略時は自動推定）"
    )
    return parser.parse_args()


def _estimate_tc_init(tbl: Dict) -> float:
    """τ の最大値付近の T を T_c 初期値として返す。"""
    mu = tbl["mean_tau_valid"]
    T  = tbl["T"]
    mask = np.isfinite(mu)
    if not mask.any():
        return 1.0
    return float(T[mask][np.argmax(mu[mask])])


def main() -> None:
    args = parse_args()

    print("=" * 70)
    print("  analyze_slowing.py — Critical Slowing Down Analysis")
    print("=" * 70)
    print(f"  Data dirs : {args.data_dirs}")
    print(f"  N values  : {args.ns}")
    print(f"  Output dir: {args.out_dir}")
    print()

    # データ収集
    print("[1/4] Loading npz files ...")
    data   = collect_all(args.data_dirs, num_predict_fallback=args.num_predict)
    tables = build_summary_table(data)

    ns_available = [N for N in args.ns if N in tables]
    print(f"  Available N: {ns_available}")

    # 冪乗則フィット
    fit_results: Dict[int, Optional[Dict]] = {}
    if not args.no_fit:
        print("[2/4] Fitting power law τ ~ |T - T_c|^{-znu} ...")
        tc_init_map: Dict[int, float] = {}
        if args.tc_init and len(args.tc_init) == len(args.ns):
            tc_init_map = dict(zip(args.ns, args.tc_init))
        for N in ns_available:
            tbl = tables[N]
            Tc0 = tc_init_map.get(N, _estimate_tc_init(tbl))
            fr  = fit_critical_slowing(
                tbl["T"], tbl["mean_tau_valid"], Tc_init=Tc0, side="both"
            )
            fit_results[N] = fr
            if fr:
                print(f"  N={N}: T_c={fr['Tc']:.3f}, z*nu={fr['znu']:.3f}, R²={fr['r2']:.3f}")
            else:
                print(f"  N={N}: fit failed (not enough data near T_c)")
    else:
        print("[2/4] Skipping power-law fit (--no-fit)")
        for N in ns_available:
            fit_results[N] = None

    # 出力ディレクトリ
    os.makedirs(args.out_dir, exist_ok=True)

    # プロット
    print("[3/4] Generating plots ...")
    plot_tau_vs_T(
        tables, ns_available, fit_results,
        out_path=os.path.join(args.out_dir, "slowing_tau_valid.png"),
    )
    plot_fallback_rate(
        tables, ns_available,
        out_path=os.path.join(args.out_dir, "slowing_fallback_rate.png"),
    )
    plot_tau_imputed(
        tables, ns_available,
        out_path=os.path.join(args.out_dir, "slowing_tau_imputed.png"),
    )
    plot_combined(
        tables, ns_available, fit_results,
        out_path=os.path.join(args.out_dir, "slowing_combined.png"),
    )

    # レポート
    print("[4/4] Printing report ...")
    print_report(tables, fit_results)


if __name__ == "__main__":
    main()
