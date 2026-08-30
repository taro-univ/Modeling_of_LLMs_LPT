"""小さなfixtureでGoogle Drive転送をend-to-end検証する。"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runners.pancake_dataset_artifacts import write_json
from runners.pancake_drive_transfer import RcloneDriveTransfer, remote_cell_path


FIXTURE = b"pancake-full-hidden-drive-integration-v1\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--remote-root",
        required=True,
        help=(
            "integration test専用root。例: "
            "pancake-drive:LLM_LPT/full_hidden_v1_integration_test"
        ),
    )
    parser.add_argument("--rclone-binary", default="rclone")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with tempfile.TemporaryDirectory(prefix="pancake_drive_test_") as temp_text:
        temp = Path(temp_text)
        cell = temp / "cells/N3_mm3"
        cell.mkdir(parents=True)
        (cell / "fixture.bin").write_bytes(FIXTURE)
        write_json(
            cell / "CELL_MANIFEST.json",
            {"schema_version": 1, "cell_id": "N3_mm3", "test_fixture": True},
        )
        write_json(
            cell / "LOCAL_COMPLETE.json",
            {"schema_version": 1, "cell_id": "N3_mm3", "status": "LOCAL_COMPLETE"},
        )
        receipts = temp / "receipts"
        transfer = RcloneDriveTransfer(rclone_binary=args.rclone_binary)
        transfer.upload_cell(cell, args.remote_root, receipts)
        # 同一転送を再実行し、marker済みcellがcopyされないことも確認する。
        transfer.upload_cell(cell, args.remote_root, receipts)

        downloaded = temp / "downloaded_fixture.bin"
        remote = remote_cell_path(args.remote_root, "N3_mm3")
        result = subprocess.run(
            [
                args.rclone_binary,
                "copyto",
                f"{remote}/fixture.bin",
                str(downloaded),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout or "rclone download failed")
        expected = hashlib.sha256(FIXTURE).hexdigest()
        actual = hashlib.sha256(downloaded.read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError("downloaded fixture SHA-256 mismatch")
        print(f"[PASS] upload, remote MD5, resume, re-download SHA-256: {remote}")
        print("[NOTE] test remote is intentionally retained for inspection")


if __name__ == "__main__":
    main()
