"""Backward-compatible wrapper for P(q) spin-glass analysis."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.spin_glass import LAYER_DEFAULT, SpinGlassAnalyzer


NS_DEFAULT = [3, 4, 5]
TS_DEFAULT = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="P(q) overlap 分布によるスピングラス・常磁性相の判別")
    parser.add_argument("--dir", type=str, default="results/hanoi/pq_sweep", help="pq_sweep 結果ディレクトリ")
    parser.add_argument("--layer", type=str, default=LAYER_DEFAULT, help="解析対象レイヤー (default: layer_m8)")
    parser.add_argument("--ns", type=int, nargs="+", default=NS_DEFAULT)
    parser.add_argument("--ts", type=float, nargs="+", default=TS_DEFAULT)
    parser.add_argument("--out-dist", type=str, default="figures/pq_dist.png", help="P(q) 分布グリッド図の出力先")
    parser.add_argument("--out-summary", type=str, default="figures/pq_summary.png", help="サマリー4パネル図の出力先")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dist = Path(args.out_dist)
    out_summary = Path(args.out_summary)
    analyzer = SpinGlassAnalyzer(
        data_dir=args.dir,
        out_dir=out_dist.parent,
        ns=args.ns,
        ts=args.ts,
        title=Path(args.dir).name,
        layer=args.layer,
    )
    result = analyzer.run_analysis()
    print(result.report_text, end="")
    targets = [out_dist, out_summary]
    for src, dst in zip(result.figure_paths, targets):
        if src != dst:
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.replace(dst)
        print(f"[SAVE] {dst}")


if __name__ == "__main__":
    main()
