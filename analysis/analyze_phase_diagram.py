"""Backward-compatible wrapper for phase diagram analysis."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.phase_transition import BOUNDARY_THRESHOLD, PhaseTransitionAnalyzer


NS_DEFAULT: list[int] = [2, 3, 4, 5, 6]
TS_DEFAULT: list[float] = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="案A フルグリッドスイープ結果の可視化・相境界推定")
    parser.add_argument("--dir", type=str, default="results/hanoi/phase_diagram")
    parser.add_argument("--out", type=str, default="figures/phase_diagram.png")
    parser.add_argument("--ns", type=int, nargs="+", default=NS_DEFAULT)
    parser.add_argument("--ts", type=float, nargs="+", default=TS_DEFAULT)
    parser.add_argument("--threshold", type=float, default=BOUNDARY_THRESHOLD, help=f"相境界とみなす accuracy 閾値 (default: {BOUNDARY_THRESHOLD})")
    parser.add_argument("--title", type=str, default=None, help="図のタイトル (省略時はディレクトリ名から自動生成)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_path = Path(args.out)
    analyzer = PhaseTransitionAnalyzer(
        data_dir=args.dir,
        out_dir=out_path.parent,
        ns=args.ns,
        ts=args.ts,
        title=args.title or Path(args.dir).name,
        threshold=args.threshold,
    )
    result = analyzer.run_analysis()
    print(result.report_text, end="")
    if result.figure_paths and result.figure_paths[0] != out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        result.figure_paths[0].replace(out_path)
        result.figure_paths[0] = out_path
    for path in result.figure_paths:
        print(f"[SAVE] {path}")


if __name__ == "__main__":
    main()
