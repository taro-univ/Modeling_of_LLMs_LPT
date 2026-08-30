"""Drive本番cellから5 trialを取得する明示実行integration test。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_access.config import resolve_data_root
from data_access.loader import LoadRequest, RcloneRemoteBackend, load_hidden_data
from data_access.registry import get_puzzle_spec


def parse_args() -> argparse.Namespace:
    """integration test引数をparseする。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--remote-root",
        default="pancake-drive:LLM_LPT/full_hidden_distribution_v1",
    )
    parser.add_argument(
        "--data-root",
        required=True,
        help="取得した約9 GBを保持する明示的なlocal root",
    )
    parser.add_argument("--rclone-binary", default="rclone")
    return parser.parse_args()


def main() -> None:
    """N=5/mm=5の先頭5 trialを1 batchで取得・検証する。"""
    args = parse_args()
    puzzle = get_puzzle_spec("pancake")
    cell = puzzle.resolve_cell({"N": 5, "mm": 5})
    result = load_hidden_data(
        LoadRequest(
            cell=cell,
            data_root=resolve_data_root(args.data_root),
            remote_root=args.remote_root,
            trials=5,
            selection="sequential",
            batch_size=5,
        ),
        backend=RcloneRemoteBackend(args.rclone_binary),
        is_tty=False,
    )
    if len(result.selected_trial_ids) != 5:
        raise RuntimeError("integration test did not resolve exactly five trials")
    print(f"[PASS] five verified trials are ready: {result.cell_dir}")
    print(f"[SELECTION] {result.selection_path}")
    print("[NOTE] local cache is intentionally retained; remote data is never deleted")


if __name__ == "__main__":
    main()
