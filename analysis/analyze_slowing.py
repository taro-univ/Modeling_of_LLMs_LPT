"""Backward-compatible wrapper for critical slowing down analysis."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.critical_dynamics import CriticalDynamicsAnalyzer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze critical slowing down from phase_diagram npz files.")
    parser.add_argument("--data-dir", default=None, help="npz が格納されたスラグディレクトリ")
    parser.add_argument("--data-dirs", nargs="+", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--ns", nargs="+", type=int, default=[2, 3, 4, 5])
    parser.add_argument("--ts", nargs="+", type=float, default=[0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0])
    parser.add_argument("--out-dir", default="figures")
    parser.add_argument("--num-predict", type=int, default=4096)
    parser.add_argument("--no-fit", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = args.data_dir
    if data_dir is None and args.data_dirs:
        data_dir = args.data_dirs[0]
    if data_dir is None:
        data_dir = "results/hanoi/full_sweep"
    analyzer = CriticalDynamicsAnalyzer(
        data_dir=data_dir,
        out_dir=Path(args.out_dir),
        ns=args.ns,
        ts=args.ts,
        title=Path(data_dir).name,
        num_predict_fallback=args.num_predict,
        no_fit=args.no_fit,
    )
    result = analyzer.run_analysis()
    print(result.report_text, end="")
    for path in result.figure_paths:
        print(f"[SAVE] {path}")


if __name__ == "__main__":
    main()
