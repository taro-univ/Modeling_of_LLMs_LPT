"""measure_wn_ceff.py — C_eff と w_N を hanoi_nt_collapse CSV から算出する。

入力は analysis/plot_hanoi_nt_collapse.py の出力 CSV。summary.json は再度読まない。

使用例:
  python3 analysis/measure_wn_ceff.py \
      --csv figures/hanoi_nt_collapse/hanoi_nt_collapse_qwen3-14b.csv \
      --out-dir figures/wn_ceff
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

def load_accuracy_by_n(csv_path: Path) -> dict[int, list[tuple[float, float]]]:
    """
    CSVを読み、N->[(T, accuracy), ...](T昇順)の辞書を返す
    """
    by_n : dict[int, list[tuple[float, float]]] = {}
    with csv_path.open("r", encoding = "utf-8") as f:
        for row in csv.DictReader(f):
            N = int(row["N"])
            T = float(row["T"])
            acc = float(row["accuracy"])
            by_n.setdefault(N, []).append((T, acc))
        
        for N in by_n:
            by_n[N].sort(key=lambda pair: pair[0])
        return by_n
    
#$C_{\rm eff}$の計算

def c_eff(accuracy: float) -> float:
    """
    C_eff = -log(P_success). accuracy = 0はmath.infを返す(丸めない)
    """
    if accuracy <= 0.0:
        return math.inf
    return -math.log(accuracy)

#$w_N$の計算

def _find_crossings(points: list[tuple[float, float]], level: float) -> list[float]:
    """
    points = [(T, acc)]をまたぐTを線形補完で返す
    """
    crossing:list[float] = []
    for (t0, a0), (t1, a1) in zip(points, points[1:]):
        if a0 == a1:
            continue
        if (a0 - level) * (a1 - level) < 0: #符号が反転
            frac = (level - a0) / (a1 - a0)
            crossing.append(t0 + frac * (t1 - t0))
        elif a0 == level:
            crossing.append(t0)
    return crossing

def compute_w_n(points: list[tuple[float, float]], eps: float = 0.1) -> dict:
    """1つのNについて w_N を計算する。非単調なら w_N=None、non_monotonic=Trueを返す。"""
    half_crossings = _find_crossings(points, 0.5)
    if len(half_crossings) != 1:
        return {"t_half": None, "w_n": None, "non_monotonic": True,
                "half_crossings": half_crossings}

    t_half = half_crossings[0]
    lo_crossings = _find_crossings(points, eps)
    hi_crossings = _find_crossings(points, 1.0 - eps)
    if len(lo_crossings) != 1 or len(hi_crossings) != 1:
        return {"t_half": t_half, "w_n": None, "non_monotonic": True,
                "half_crossings": half_crossings}

    w_n = abs(hi_crossings[0] - lo_crossings[0]) / t_half
    return {"t_half": t_half, "w_n": w_n, "non_monotonic": False,
            "half_crossings": half_crossings}

def write_c_eff_csv(csv_path: Path, out_path: Path) -> None:
    with csv_path.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        f.write("N,T,accuracy,c_eff\n")
        for row in rows:
            acc = float(row["accuracy"])
            ce = c_eff(acc)
            ce_str = "inf" if math.isinf(ce) else f"{ce:.6f}"
            f.write(f"{row['N']},{row['T']},{acc:.6f},{ce_str}\n")


def write_w_n_csv(by_n: dict[int, list[tuple[float, float]]], out_path: Path, eps: float) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        f.write("N,t_half,w_n,non_monotonic,half_crossings\n")
        for N in sorted(by_n):
            result = compute_w_n(by_n[N], eps=eps)
            t_half = "" if result["t_half"] is None else f"{result['t_half']:.4f}"
            w_n = "" if result["w_n"] is None else f"{result['w_n']:.4f}"
            crossings = ";".join(f"{c:.4f}" for c in result["half_crossings"])
            f.write(f"{N},{t_half},{w_n},{result['non_monotonic']},{crossings}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute C_eff and w_N from hanoi_nt_collapse CSV.")
    parser.add_argument("--csv", type=Path, required=True, help="plot_hanoi_nt_collapse.py が出したCSV")
    parser.add_argument("--out-dir", type=Path, default=Path("figures/wn_ceff"))
    parser.add_argument("--eps", type=float, default=0.1, help="w_N の裾閾値 (default: 0.1)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model = args.csv.stem.replace("hanoi_nt_collapse_", "")
    by_n = load_accuracy_by_n(args.csv)

    c_eff_path = args.out_dir / f"c_eff_{model}.csv"
    write_c_eff_csv(args.csv, c_eff_path)
    print(f"[SAVE] {c_eff_path}")

    w_n_path = args.out_dir / f"w_n_{model}.csv"
    write_w_n_csv(by_n, w_n_path, eps=args.eps)
    print(f"[SAVE] {w_n_path}")

    for N, result in ((N, compute_w_n(by_n[N], eps=args.eps)) for N in sorted(by_n)):
        flag = " [NON-MONOTONIC]" if result["non_monotonic"] else ""
        print(f"  N={N}: t_half={result['t_half']}, w_N={result['w_n']}{flag}")


if __name__ == "__main__":
    main()