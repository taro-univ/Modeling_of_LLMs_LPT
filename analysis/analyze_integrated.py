"""Compatibility wrapper for the integrated analysis entry point."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.io_utils import TS_ALL, TS_PQ, _cosine, load_condition
from analysis.run_pipeline import run_pipeline


MODEL_DEFAULT = "deepseek-r1-distill-qwen-7b"
LAYER_DEFAULT = "layer_mid"
NS_DEFAULT = [2, 3, 4, 5, 6]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="full_sweep + collapse_phase 統合解析")
    parser.add_argument("--model", type=str, default=MODEL_DEFAULT)
    parser.add_argument("--layer", type=str, default=LAYER_DEFAULT)
    parser.add_argument("--ns", type=int, nargs="+", default=NS_DEFAULT)
    parser.add_argument("--base", type=str, default="results/hanoi")
    parser.add_argument("--out-dir", type=str, default="figures")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = Path(args.base) / "full_sweep" / args.model
    config = {
        "data_dir": data_dir,
        "out_dir": Path(args.out_dir) / f"{args.model}_integrated",
        "title": args.model,
        "ns": args.ns,
        "ts": TS_ALL,
        "layer": args.layer,
        "analyzers": ["phase_transition", "spin_glass"],
    }
    run_pipeline(config)


if __name__ == "__main__":
    main()
