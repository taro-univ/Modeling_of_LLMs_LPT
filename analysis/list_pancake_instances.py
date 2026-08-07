"""List reproducible Pancake Sorting instances without loading a model."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from envs.pancake_env import PancakeSortingEnv


CSV_FIELDS = [
    "N",
    "seed",
    "initial_state",
    "goal_state",
    "min_moves",
    "optimal_moves",
]


def parse_ns(value: str) -> list[int]:
    ns = [int(item) for item in value.split()]
    if not ns:
        raise argparse.ArgumentTypeError("--ns must contain at least one integer")
    return ns


def build_instance_table(ns: list[int], seed_start: int, seed_end: int) -> dict:
    if seed_end < seed_start:
        raise ValueError("seed_end must be greater than or equal to seed_start")

    instances = []
    for N in ns:
        for seed in range(seed_start, seed_end + 1):
            env = PancakeSortingEnv(N=N, seed=seed)
            instances.append(
                {
                    "N": N,
                    "seed": seed,
                    "initial_state": list(env.initial_state),
                    "goal_state": list(env.goal_state),
                    "min_moves": env.min_moves,
                    "optimal_moves": env.solve(),
                }
            )

    return {
        "schema_version": 1,
        "generator": "PancakeSortingEnv",
        "Ns": ns,
        "seed_start": seed_start,
        "seed_end": seed_end,
        "instances": instances,
    }


def write_csv(path: Path, instances: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for instance in instances:
            writer.writerow(
                {
                    **instance,
                    "initial_state": json.dumps(instance["initial_state"]),
                    "goal_state": json.dumps(instance["goal_state"]),
                    "optimal_moves": json.dumps(instance["optimal_moves"]),
                }
            )


def write_json(path: Path, table: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(table, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ns", type=parse_ns, required=True)
    parser.add_argument("--seed-start", type=int, required=True)
    parser.add_argument("--seed-end", type=int, required=True)
    parser.add_argument("--csv-out", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    if args.csv_out is None and args.json_out is None:
        parser.error("at least one of --csv-out or --json-out is required")
    return args


def main() -> None:
    args = parse_args()
    table = build_instance_table(args.ns, args.seed_start, args.seed_end)
    if args.csv_out is not None:
        write_csv(args.csv_out, table["instances"])
    if args.json_out is not None:
        write_json(args.json_out, table)


if __name__ == "__main__":
    main()
