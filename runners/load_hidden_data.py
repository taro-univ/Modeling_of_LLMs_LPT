"""Drive上のfull-hidden trialを解析用local cacheへ取得する。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_access.config import resolve_data_root
from data_access.loader import LoadRequest, LoaderError, RcloneRemoteBackend, load_hidden_data
from data_access.registry import PUZZLE_REGISTRY, RegistryError, get_puzzle_spec


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """CLI argumentsをparseする。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--puzzle", required=True)
    fields = {
        field.flag: field
        for spec in PUZZLE_REGISTRY.values()
        for field in spec.difficulty_fields
    }
    for field in fields.values():
        parser.add_argument(field.flag, dest=field.key, type=field.value_type)
    parser.add_argument("--trials", type=int)
    parser.add_argument(
        "--selection",
        choices=("sequential", "random"),
        default="sequential",
    )
    parser.add_argument("--seed", type=int)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--data-root")
    parser.add_argument(
        "--remote-root",
        help="未指定時はpuzzle registryのproduction remoteを使う",
    )
    parser.add_argument("--rclone-binary", default="rclone")
    parser.add_argument("--accept-available", action="store_true")
    args = parser.parse_args(argv)
    try:
        puzzle = get_puzzle_spec(args.puzzle)
    except RegistryError as exc:
        parser.error(str(exc))
    missing = [
        field.flag
        for field in puzzle.difficulty_fields
        if field.required and getattr(args, field.key) is None
    ]
    if missing:
        parser.error(f"{args.puzzle} requires {' and '.join(missing)}")
    if args.trials is not None and args.trials <= 0:
        parser.error("--trials must be positive")
    if args.batch_size <= 0:
        parser.error("--batch-size must be positive")
    if args.selection == "sequential" and args.seed is not None:
        parser.error("--seed cannot be used with sequential selection")
    return args


def main(argv: list[str] | None = None) -> int:
    """CLI entry point。"""
    args = parse_args(argv)
    try:
        puzzle = get_puzzle_spec(args.puzzle)
        difficulty = {
            field.key: getattr(args, field.key)
            for field in puzzle.difficulty_fields
        }
        cell = puzzle.resolve_cell(difficulty)
        result = load_hidden_data(
            LoadRequest(
                cell=cell,
                data_root=resolve_data_root(args.data_root),
                remote_root=args.remote_root or cell.default_remote_root,
                trials=args.trials,
                selection=args.selection,
                seed=args.seed,
                batch_size=args.batch_size,
                accept_available=args.accept_available,
            ),
            backend=RcloneRemoteBackend(args.rclone_binary),
        )
    except (LoaderError, RegistryError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    if result.cancelled:
        print("[CANCELLED] データは取得していません")
        return 0
    print(f"[READY] {len(result.selected_trial_ids)} trials: {result.cell_dir}")
    print(f"[SELECTION] {result.selection_path}")
    print(
        f"[CACHE] downloaded={len(result.downloaded_trial_ids)} "
        f"reused={len(result.reused_trial_ids)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
