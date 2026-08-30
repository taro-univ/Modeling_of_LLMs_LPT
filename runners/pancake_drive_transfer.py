"""検証済みPancake dataset cellをrcloneでGoogle Driveへ転送する。"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runners.pancake_dataset_artifacts import hashes_file, md5_file, sha256_file, write_json


CELL_ID_RE = re.compile(r"(?:SMOKE_(?:SCHEMA|STRESS)_)?N[3-5]_mm[3-5]")


class TransferError(RuntimeError):
    """転送またはremote完全性検証の失敗。"""


@dataclass(frozen=True)
class RemoteFile:
    """rclone lsjsonから得るremote file情報。"""

    path: str
    size: int
    md5: str | None


RunCommand = Callable[..., subprocess.CompletedProcess[str]]


def utc_now() -> str:
    """timezone付きUTC時刻を返す。"""
    return datetime.now(timezone.utc).isoformat()


def validate_remote_root(remote_root: str) -> str:
    """専用directoryを含むrclone remote rootか検証する。"""
    if ":" not in remote_root:
        raise ValueError("remote root must use rclone syntax, e.g. gdrive:research/dataset")
    remote, root = remote_root.split(":", 1)
    if not remote or not root.strip("/"):
        raise ValueError("remote root must include a dedicated directory after ':'")
    return f"{remote}:{root.strip('/')}"


def remote_cell_path(remote_root: str, cell_id: str) -> str:
    """remote root配下のcell pathを構築する。"""
    if not CELL_ID_RE.fullmatch(cell_id):
        raise ValueError(f"invalid cell_id: {cell_id}")
    return f"{validate_remote_root(remote_root)}/{cell_id}"


def local_payload(cell_dir: Path) -> dict[str, dict[str, Any]]:
    """転送対象fileのsize/MD5/SHA-256を列挙する。

    ``CELL_COMPLETE.json`` はremote検証後に別送するため除外する。
    partialとreceiptがcell内にあれば安全のため拒否する。
    """
    if not (cell_dir / "LOCAL_COMPLETE.json").is_file():
        raise TransferError("LOCAL_COMPLETE.json is required before upload")
    partials = [path for path in cell_dir.rglob("*") if ".partial" in path.name]
    if partials:
        raise TransferError(f"partial artifacts cannot be uploaded: {partials[0]}")
    payload: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in cell_dir.rglob("*") if item.is_file()):
        relative = path.relative_to(cell_dir).as_posix()
        if relative == "CELL_COMPLETE.json" or relative == "transfer_receipt.json":
            continue
        sha256, md5 = hashes_file(path)
        payload[relative] = {
            "size": path.stat().st_size,
            "md5": md5,
            "sha256": sha256,
        }
    if not payload:
        raise TransferError("cell payload is empty")
    return payload


class RcloneDriveTransfer:
    """copy→remote size/MD5検証→marker作成を実行する。"""

    def __init__(
        self,
        rclone_binary: str = "rclone",
        run_command: RunCommand = subprocess.run,
    ) -> None:
        self.rclone_binary = rclone_binary
        self._run_command = run_command

    def _run(self, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        command = [self.rclone_binary, *args]
        try:
            result = self._run_command(
                command,
                text=True,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise TransferError(f"rclone executable not found: {self.rclone_binary}") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "unknown rclone error").strip()
            raise TransferError(f"rclone failed ({result.returncode}): {detail}")
        return result

    def list_remote(self, remote_path: str) -> dict[str, RemoteFile]:
        """remote filesをrecursiveに列挙する。未作成remoteは空として扱う。"""
        result = self._run(
            ["lsjson", remote_path, "--recursive", "--files-only", "--hash"]
        )
        try:
            rows = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as exc:
            raise TransferError("rclone lsjson returned invalid JSON") from exc
        files = {}
        for row in rows:
            hashes = row.get("Hashes") or {}
            md5 = hashes.get("MD5") or hashes.get("md5")
            relative = str(row["Path"])
            if relative in files:
                raise TransferError(f"duplicate remote path: {relative}")
            files[relative] = RemoteFile(
                path=relative,
                size=int(row["Size"]),
                md5=md5.lower() if md5 else None,
            )
        return files

    def read_remote_marker(self, remote_path: str) -> dict[str, Any]:
        """remote CELL_COMPLETE.jsonを読み、JSON objectとして返す。"""
        result = self._run(["cat", f"{remote_path}/CELL_COMPLETE.json"])
        try:
            marker = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise TransferError("remote CELL_COMPLETE.json is invalid JSON") from exc
        if not isinstance(marker, dict):
            raise TransferError("remote CELL_COMPLETE.json must be a JSON object")
        return marker

    @staticmethod
    def verify_listing(
        expected: dict[str, dict[str, Any]],
        actual: dict[str, RemoteFile],
        *,
        allow_complete_marker: bool,
    ) -> None:
        """remoteの存在・size・MD5と余分なfileがないことを検証する。"""
        allowed = set(expected)
        if allow_complete_marker:
            allowed.add("CELL_COMPLETE.json")
        extras = set(actual) - allowed
        missing = set(expected) - set(actual)
        if extras:
            raise TransferError(f"unexpected remote files: {sorted(extras)[:3]}")
        if missing:
            raise TransferError(f"missing remote files: {sorted(missing)[:3]}")
        for relative, item in expected.items():
            remote = actual[relative]
            if remote.size != int(item["size"]):
                raise TransferError(f"remote size mismatch: {relative}")
            if remote.md5 is None:
                raise TransferError(f"remote MD5 unavailable: {relative}")
            if remote.md5 != str(item["md5"]).lower():
                raise TransferError(f"remote MD5 mismatch: {relative}")

    def upload_cell(
        self,
        cell_dir: Path,
        remote_root: str,
        receipt_dir: Path,
    ) -> dict[str, Any]:
        """cellをcopyし、remote検証後にmarkerとlocal receiptを書く。

        quota超過・通信断・hash不一致はいずれも例外で停止する。local dataは
        このmethodでは削除しない。
        """
        cell_id = cell_dir.name
        remote_path = remote_cell_path(remote_root, cell_id)
        expected = local_payload(cell_dir)
        marker_path = receipt_dir / ".markers" / f"{cell_id}_CELL_COMPLETE.json"
        receipt_path = receipt_dir / f"{cell_id}_transfer_receipt.json"
        receipt_dir.mkdir(parents=True, exist_ok=True)

        # 既にmarkerがある再開時も、payload全体を再検証してから成功扱いにする。
        self._run(["mkdir", remote_path])
        initial = self.list_remote(remote_path)
        if "CELL_COMPLETE.json" not in initial:
            self._run(
                [
                    "copy",
                    str(cell_dir),
                    remote_path,
                    "--immutable",
                    "--exclude",
                    "CELL_COMPLETE.json",
                    "--exclude",
                    "transfer_receipt.json",
                    "--retries",
                    "3",
                    "--low-level-retries",
                    "10",
                ]
            )

        uploaded = self.list_remote(remote_path)
        self.verify_listing(
            expected,
            uploaded,
            allow_complete_marker="CELL_COMPLETE.json" in uploaded,
        )

        marker = {
            "schema_version": 1,
            "cell_id": cell_id,
            "remote_path": remote_path,
            "verified_at": utc_now(),
            "file_count": len(expected),
            "payload_bytes": sum(int(item["size"]) for item in expected.values()),
            "local_manifest_sha256": sha256_file(cell_dir / "CELL_MANIFEST.json"),
        }
        if "CELL_COMPLETE.json" not in uploaded:
            write_json(marker_path, marker)
            self._run(
                [
                    "copyto",
                    str(marker_path),
                    f"{remote_path}/CELL_COMPLETE.json",
                    "--immutable",
                ]
            )
        final_listing = self.list_remote(remote_path)
        self.verify_listing(expected, final_listing, allow_complete_marker=True)
        remote_marker = final_listing.get("CELL_COMPLETE.json")
        if remote_marker is None:
            raise TransferError("remote CELL_COMPLETE.json was not created")
        if remote_marker.md5 is None:
            raise TransferError("remote CELL_COMPLETE.json MD5 is unavailable")
        if marker_path.is_file() and remote_marker.md5 != md5_file(marker_path):
            raise TransferError("remote CELL_COMPLETE.json MD5 mismatch")

        remote_marker_payload = self.read_remote_marker(remote_path)
        current_manifest_sha256 = sha256_file(cell_dir / "CELL_MANIFEST.json")
        if remote_marker_payload.get("cell_id") != cell_id:
            raise TransferError("remote marker cell_id mismatch")
        if remote_marker_payload.get("remote_path") != remote_path:
            raise TransferError("remote marker path mismatch")
        if remote_marker_payload.get("local_manifest_sha256") != current_manifest_sha256:
            raise TransferError("remote marker manifest SHA-256 mismatch")

        receipt = {
            **remote_marker_payload,
            "status": "REMOTE_VERIFIED",
            "remote_marker_size": remote_marker.size,
            "remote_marker_md5": remote_marker.md5,
        }
        write_json(receipt_path, receipt)
        return receipt


def safe_delete_local_cell(
    cell_dir: Path,
    cells_root: Path,
    receipt_path: Path,
) -> None:
    """REMOTE_VERIFIED receiptがあるcellだけを明示的に削除する。"""
    resolved_root = cells_root.resolve()
    resolved_cell = cell_dir.resolve()
    if resolved_cell.parent != resolved_root:
        raise TransferError("delete target must be a direct child of cells root")
    if not CELL_ID_RE.fullmatch(resolved_cell.name):
        raise TransferError("delete target is not a valid cell directory")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("status") != "REMOTE_VERIFIED":
        raise TransferError("REMOTE_VERIFIED receipt is required before local deletion")
    if receipt.get("cell_id") != resolved_cell.name:
        raise TransferError("receipt cell_id does not match delete target")
    if not resolved_cell.is_dir():
        raise TransferError(f"cell directory not found: {resolved_cell}")
    manifest_path = resolved_cell / "CELL_MANIFEST.json"
    if not manifest_path.is_file():
        raise TransferError("CELL_MANIFEST.json is required before local deletion")
    current_manifest_sha256 = sha256_file(manifest_path)
    if receipt.get("local_manifest_sha256") != current_manifest_sha256:
        raise TransferError("receipt manifest SHA-256 does not match local cell")
    remote_path = receipt.get("remote_path")
    if not isinstance(remote_path, str) or not remote_path.strip():
        raise TransferError("receipt remote_path is required before local deletion")
    if not remote_path.rstrip("/").endswith(f"/{resolved_cell.name}"):
        raise TransferError("receipt remote_path does not match local cell")
    try:
        validate_remote_root(remote_path.rsplit("/", 1)[0])
    except ValueError as exc:
        raise TransferError("receipt remote_path is invalid") from exc
    shutil.rmtree(resolved_cell)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cell_dir", type=Path)
    parser.add_argument(
        "--remote-root",
        required=True,
        help="専用Drive root。例: pancake-drive:LLM_LPT/full_hidden_v1",
    )
    parser.add_argument("--receipt-dir", type=Path, required=True)
    parser.add_argument("--rclone-binary", default="rclone")
    parser.add_argument(
        "--delete-local-after-verify",
        action="store_true",
        help="remote size/MD5/marker検証後だけlocal cellを削除する",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    transfer = RcloneDriveTransfer(rclone_binary=args.rclone_binary)
    receipt = transfer.upload_cell(args.cell_dir, args.remote_root, args.receipt_dir)
    receipt_path = args.receipt_dir / f"{args.cell_dir.name}_transfer_receipt.json"
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    if args.delete_local_after_verify:
        safe_delete_local_cell(args.cell_dir, args.cell_dir.parent, receipt_path)
        print(f"[LOCAL_PRUNED] {args.cell_dir}")


if __name__ == "__main__":
    main()
