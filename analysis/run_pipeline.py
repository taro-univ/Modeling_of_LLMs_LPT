from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.base_analyzer import AnalysisResult, BaseAnalyzer
from analysis.critical_dynamics import CriticalDynamicsAnalyzer
from analysis.phase_transition import PhaseTransitionAnalyzer
from analysis.spin_glass import SpinGlassAnalyzer

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


ANALYZER_REGISTRY = {
    "phase_transition": PhaseTransitionAnalyzer,
    "spin_glass": SpinGlassAnalyzer,
    "critical_dynamics": CriticalDynamicsAnalyzer,
}


def _load_yaml(path: str | None) -> dict:
    if path is None:
        return {}
    if yaml is None:
        raise RuntimeError("PyYAML is required when --config is used")
    with open(path) as f:
        loaded = yaml.safe_load(f) or {}
    if not isinstance(loaded, dict):
        raise ValueError("--config must contain a YAML mapping")
    return loaded


def build_config(args: argparse.Namespace) -> dict:
    config = _load_yaml(args.config)
    defaults = {
        "ns": BaseAnalyzer.NS_DEFAULT,
        "ts": BaseAnalyzer.TS_DEFAULT,
        "layer": "layer_m8",
        "analyzers": ["phase_transition", "spin_glass", "critical_dynamics"],
    }
    merged = {**defaults, **config}
    for key in ("data_dir", "out_dir", "title", "ns", "ts", "layer", "analyzers", "num_predict_fallback"):
        value = getattr(args, key, None)
        if value is not None:
            merged[key] = value
    if "data_dir" not in merged or "out_dir" not in merged:
        raise ValueError("data_dir and out_dir are required via --config or CLI")
    return merged


def run_pipeline(config: dict) -> list[AnalysisResult]:
    results: list[AnalysisResult] = []
    for name in config["analyzers"]:
        if name not in ANALYZER_REGISTRY:
            raise ValueError(f"Unknown analyzer: {name}")
        cls = ANALYZER_REGISTRY[name]
        kwargs = {
            "data_dir": Path(config["data_dir"]),
            "out_dir": Path(config["out_dir"]),
            "ns": config.get("ns"),
            "ts": config.get("ts"),
            "title": config.get("title", ""),
            "layer": config.get("layer", "layer_m8"),
        }
        if name == "critical_dynamics":
            kwargs["num_predict_fallback"] = config.get("num_predict_fallback", 4096)
        analyzer = cls(**kwargs)
        result = analyzer.run_analysis()
        results.append(result)
        print(result.report_text, end="")
        for path in result.figure_paths:
            print(f"[SAVE] {path}")
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run analysis pipeline")
    parser.add_argument("--config", default=None)
    parser.add_argument("--data-dir", dest="data_dir", default=None)
    parser.add_argument("--out-dir", dest="out_dir", default=None)
    parser.add_argument("--title", default=None)
    parser.add_argument("--ns", type=int, nargs="+", default=None)
    parser.add_argument("--ts", type=float, nargs="+", default=None)
    parser.add_argument("--layer", default=None)
    parser.add_argument("--analyzers", nargs="+", choices=sorted(ANALYZER_REGISTRY), default=None)
    parser.add_argument("--num-predict-fallback", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    run_pipeline(build_config(parse_args()))


if __name__ == "__main__":
    main()
