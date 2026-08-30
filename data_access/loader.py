"""検証済みhidden datasetをtrial単位でlocal cacheへ取得する。"""

from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Protocol, Sequence

from data_access.registry import CellSpec


class LoaderError(RuntimeError):
    """取得・artifact検証の失敗。"""


def _hash_file(path: Path, algorithm: str, block_size: int = 8 * 1024 * 1024) -> str:
    """大容量fileを固定長bufferでhash化する。"""
    if algorithm == "md5":
        digest = hashlib.md5(usedforsecurity=False)
    else:
        digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        while block := handle.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    """fileのSHA-256を返す。"""
    return _hash_file(path, "sha256")


def md5_file(path: Path) -> str:
    """fileのMD5を返す。"""
    return _hash_file(path, "md5")


def _write_json(path: Path, value: Any) -> None:
    """安定した形式のJSONを保存する。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _validate_remote_root(remote_root: str) -> str:
    """専用directoryを含むrclone remote rootへ正規化する。"""
    if ":" not in remote_root:
        raise LoaderError(
            "remote root must use rclone syntax, e.g. gdrive:research/dataset"
        )
    remote, root = remote_root.split(":", 1)
    if not remote or not root.strip("/"):
        raise LoaderError("remote root must include a dedicated directory after ':'")
    return f"{remote}:{root.strip('/')}"


@dataclass(frozen=True)
class LoadRequest:
    """1回のlocal load条件。"""

    cell: CellSpec
    data_root: Path
    remote_root: str
    trials: int | None = None
    selection: str = "sequential"
    seed: int | None = None
    batch_size: int = 5
    accept_available: bool = False


@dataclass(frozen=True)
class LoadResult:
    """load後にNotebookから参照するpath群。"""

    cell_dir: Path
    manifest_path: Path
    selection_path: Path
    selected_trial_ids: tuple[str, ...]
    downloaded_trial_ids: tuple[str, ...]
    reused_trial_ids: tuple[str, ...]
    cancelled: bool = False


class RemoteBackend(Protocol):
    """remote取得をテストで差し替える最小interface。"""

    def download_metadata(self, remote_cell: str, destination: Path) -> None:
        """CELL_MANIFESTとCELL_COMPLETEを取得する。"""

    def download_batch(
        self,
        remote_trials: str,
        trial_ids: Sequence[str],
        destination: Path,
    ) -> None:
        """指定trial directoriesを1 batchとして取得する。"""


class RcloneRemoteBackend:
    """rclone copy/copytoを使うproduction backend。"""

    def __init__(self, rclone_binary: str = "rclone") -> None:
        self.rclone_binary = rclone_binary

    def _run(self, arguments: Sequence[str]) -> None:
        command = [self.rclone_binary, *arguments]
        try:
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise LoaderError(
                f"rclone executable not found: {self.rclone_binary}"
            ) from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "unknown rclone error").strip()
            raise LoaderError(f"rclone failed ({result.returncode}): {detail}")

    def download_metadata(self, remote_cell: str, destination: Path) -> None:
        """小さいmanifestと完了markerだけを取得する。"""
        destination.mkdir(parents=True, exist_ok=True)
        for name in ("CELL_MANIFEST.json", "CELL_COMPLETE.json"):
            self._run(
                [
                    "copyto",
                    f"{remote_cell}/{name}",
                    str(destination / name),
                    "--retries",
                    "3",
                    "--low-level-retries",
                    "10",
                ]
            )

    def download_batch(
        self,
        remote_trials: str,
        trial_ids: Sequence[str],
        destination: Path,
    ) -> None:
        """include filterでbatch内trialだけを1回のrclone処理で取得する。"""
        destination.mkdir(parents=True, exist_ok=True)
        arguments = ["copy", remote_trials, str(destination)]
        for trial_id in trial_ids:
            arguments.extend(["--include", f"/{trial_id}/**"])
        arguments.extend(
            [
                "--retries",
                "3",
                "--low-level-retries",
                "10",
            ]
        )
        self._run(arguments)


def partition_batches(items: Sequence[str], batch_size: int) -> list[list[str]]:
    """順序を保って固定件数のbatchへ分割する。"""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    return [list(items[index:index + batch_size]) for index in range(0, len(items), batch_size)]


def resolve_trial_count(
    requested: int | None,
    available: int,
    *,
    accept_available: bool,
    input_func: Callable[[str], str] = input,
    is_tty: bool | None = None,
) -> int | None:
    """requested countを検証し、超過時だけ一度確認する。

    ``None`` の返却はuserが超過時のloadを拒否したことを表す。
    """
    if available <= 0:
        raise LoaderError("remote cell contains no trials")
    if requested is None:
        return available
    if requested <= 0:
        raise LoaderError("trials must be positive")
    if requested <= available:
        return requested
    if accept_available:
        return available
    terminal = sys.stdin.isatty() if is_tty is None else is_tty
    if not terminal:
        raise LoaderError(
            f"{requested} trials requested, but only {available} are available; "
            "use --accept-available"
        )
    answer = input_func(
        f"{requested}件が指定されましたが、{available}件しかありません。"
        f"{available}件をロードしますか？ [y/N] "
    )
    return available if answer.strip().lower() in {"y", "yes"} else None


def select_trial_ids(
    trial_ids: Sequence[str],
    count: int,
    *,
    method: str,
    seed: int | None,
) -> tuple[list[str], int | None]:
    """固定plan順または再現可能な非復元抽出を行う。"""
    if count <= 0 or count > len(trial_ids):
        raise LoaderError("selection count is outside available trials")
    if len(set(trial_ids)) != len(trial_ids):
        raise LoaderError("remote manifest contains duplicate trial IDs")
    if method == "sequential":
        if seed is not None:
            raise LoaderError("--seed cannot be used with sequential selection")
        return list(trial_ids[:count]), None
    if method == "random":
        resolved_seed = 42 if seed is None else seed
        return random.Random(resolved_seed).sample(list(trial_ids), count), resolved_seed
    raise LoaderError(f"unsupported selection method: {method}")


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LoaderError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise LoaderError(f"{label} must be a JSON object")
    return value


def _validate_remote_metadata(
    metadata_dir: Path,
    cell: CellSpec,
    remote_cell: str,
) -> dict[str, Any]:
    manifest_path = metadata_dir / "CELL_MANIFEST.json"
    marker_path = metadata_dir / "CELL_COMPLETE.json"
    manifest = _read_json(manifest_path, "CELL_MANIFEST.json")
    marker = _read_json(marker_path, "CELL_COMPLETE.json")
    if manifest.get("schema_version") != 1 or marker.get("schema_version") != 1:
        raise LoaderError("unsupported cell artifact schema")
    if manifest.get("dataset_id") != cell.dataset_id:
        raise LoaderError("CELL_MANIFEST dataset_id mismatch")
    if manifest.get("cell_id") != cell.cell_id or marker.get("cell_id") != cell.cell_id:
        raise LoaderError("cell_id mismatch in remote metadata")
    if marker.get("remote_path") != remote_cell:
        raise LoaderError("CELL_COMPLETE remote_path mismatch")
    if marker.get("local_manifest_sha256") != sha256_file(manifest_path):
        raise LoaderError("CELL_COMPLETE manifest SHA-256 mismatch")
    for key, expected in cell.manifest_difficulty.items():
        if int(manifest.get(key, -1)) != expected:
            raise LoaderError(f"CELL_MANIFEST {key} mismatch")
    trial_ids = manifest.get("trial_ids")
    trial_rows = manifest.get("trials")
    if not isinstance(trial_ids, list) or not all(isinstance(item, str) for item in trial_ids):
        raise LoaderError("CELL_MANIFEST trial_ids is invalid")
    if not isinstance(trial_rows, list) or len(trial_rows) != len(trial_ids):
        raise LoaderError("CELL_MANIFEST trials is invalid")
    if int(manifest.get("trial_count", -1)) != len(trial_ids):
        raise LoaderError("CELL_MANIFEST trial_count mismatch")
    if len(set(trial_ids)) != len(trial_ids):
        raise LoaderError("CELL_MANIFEST contains duplicate trial IDs")
    row_ids = [row.get("trial_id") if isinstance(row, dict) else None for row in trial_rows]
    if row_ids != trial_ids:
        raise LoaderError("CELL_MANIFEST trial order mismatch")
    for row in trial_rows:
        digest = row.get("checksums_sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise LoaderError("CELL_MANIFEST checksums_sha256 is invalid")
    return manifest


def _safe_artifact_path(trial_dir: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise LoaderError(f"unsafe checksum path: {relative!r}")
    return trial_dir.joinpath(*path.parts)


def validate_downloaded_trial(
    trial_dir: Path,
    trial_id: str,
    manifest_row: dict[str, Any],
) -> None:
    """trial checksumとcomplete markerをstream検証する。

    HDF5の内容をRAMへ展開せず、生成時artifact contractのSHA-256/MD5を検証する。
    """
    if not trial_dir.is_dir():
        raise LoaderError(f"downloaded trial directory is missing: {trial_id}")
    checksums_path = trial_dir / "checksums.json"
    if not checksums_path.is_file():
        raise LoaderError(f"checksums.json is missing: {trial_id}")
    if sha256_file(checksums_path) != manifest_row["checksums_sha256"]:
        raise LoaderError(f"checksums.json SHA-256 mismatch: {trial_id}")
    payload = _read_json(checksums_path, "checksums.json")
    if payload.get("schema_version") != 1 or not isinstance(payload.get("files"), list):
        raise LoaderError(f"invalid checksums.json schema: {trial_id}")
    expected_files: set[str] = set()
    sha_lines: list[str] = []
    md5_lines: list[str] = []
    for item in payload["files"]:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise LoaderError(f"invalid checksum row: {trial_id}")
        relative = item["path"]
        if relative in expected_files:
            raise LoaderError(f"duplicate checksum path: {relative}")
        expected_files.add(relative)
        path = _safe_artifact_path(trial_dir, relative)
        if not path.is_file():
            raise LoaderError(f"missing trial artifact: {trial_id}/{relative}")
        if path.stat().st_size != int(item.get("size", -1)):
            raise LoaderError(f"size mismatch: {trial_id}/{relative}")
        if sha256_file(path) != item.get("sha256"):
            raise LoaderError(f"SHA-256 mismatch: {trial_id}/{relative}")
        if md5_file(path) != item.get("md5"):
            raise LoaderError(f"MD5 mismatch: {trial_id}/{relative}")
        sha_lines.append(f"{item['sha256']}  {relative}\n")
        md5_lines.append(f"{item['md5']}  {relative}\n")
    if not expected_files:
        raise LoaderError(f"empty checksums.json: {trial_id}")
    checksum_sha = trial_dir / "checksums.sha256"
    checksum_md5 = trial_dir / "checksums.md5"
    complete_path = trial_dir / "COMPLETE.json"
    for path in (checksum_sha, checksum_md5, complete_path):
        if not path.is_file():
            raise LoaderError(f"missing trial control artifact: {trial_id}/{path.name}")
    if checksum_sha.read_text(encoding="utf-8") != "".join(sha_lines):
        raise LoaderError(f"checksums.sha256 content mismatch: {trial_id}")
    if checksum_md5.read_text(encoding="utf-8") != "".join(md5_lines):
        raise LoaderError(f"checksums.md5 content mismatch: {trial_id}")
    complete = _read_json(complete_path, "COMPLETE.json")
    if complete.get("trial_id") != trial_id or complete.get("status") != "LOCAL_VALIDATED":
        raise LoaderError(f"COMPLETE.json mismatch: {trial_id}")
    metadata_path = trial_dir / "raw/metadata.json"
    if metadata_path.is_file():
        metadata = _read_json(metadata_path, "raw/metadata.json")
        if metadata.get("trial_id") != trial_id:
            raise LoaderError(f"metadata trial_id mismatch: {trial_id}")
        for key in ("generated_token_count", "generated_text_sha256"):
            if key in manifest_row and metadata.get(key) != manifest_row[key]:
                raise LoaderError(f"metadata {key} mismatch: {trial_id}")
            if key in manifest_row and complete.get(key) != manifest_row[key]:
                raise LoaderError(f"COMPLETE.json {key} mismatch: {trial_id}")
    allowed = expected_files | {
        "checksums.json",
        "checksums.sha256",
        "checksums.md5",
        "COMPLETE.json",
    }
    actual = {
        path.relative_to(trial_dir).as_posix()
        for path in trial_dir.rglob("*")
        if path.is_file()
    }
    extras = actual - allowed
    if extras:
        raise LoaderError(f"unexpected trial artifacts: {sorted(extras)[:3]}")


def _install_manifest(cell_dir: Path, downloaded: Path) -> Path:
    destination = cell_dir / "CELL_MANIFEST.json"
    if destination.exists():
        if sha256_file(destination) != sha256_file(downloaded):
            raise LoaderError(
                "local CELL_MANIFEST differs from remote; refusing to overwrite"
            )
        return destination
    temporary = cell_dir / "CELL_MANIFEST.json.partial"
    shutil.copyfile(downloaded, temporary)
    os.replace(temporary, destination)
    return destination


def _selection_path(
    cell_dir: Path,
    *,
    method: str,
    requested: int | None,
    resolved: int,
    seed: int | None,
    trial_ids: Sequence[str],
) -> Path:
    requested_name = "max" if requested is None else str(requested)
    seed_name = "" if seed is None else f"_seed{seed}"
    digest = hashlib.sha256("\n".join(trial_ids).encode("utf-8")).hexdigest()[:12]
    name = f"{method}_req{requested_name}_n{resolved}{seed_name}_{digest}.json"
    return cell_dir / "selections" / name


def load_hidden_data(
    request: LoadRequest,
    *,
    backend: RemoteBackend | None = None,
    input_func: Callable[[str], str] = input,
    is_tty: bool | None = None,
) -> LoadResult:
    """remote cellを検証し、選択trialをlocal cacheへ取得する。"""
    if request.batch_size <= 0:
        raise LoaderError("batch_size must be positive")
    remote_root = _validate_remote_root(request.remote_root)
    remote_cell = f"{remote_root}/{request.cell.cell_id}"
    cell_dir = (
        request.data_root
        / request.cell.dataset_id
        / request.cell.puzzle
        / request.cell.cell_id
    )
    cell_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir = cell_dir / ".metadata.partial"
    remote = RcloneRemoteBackend() if backend is None else backend
    remote.download_metadata(remote_cell, metadata_dir)
    manifest = _validate_remote_metadata(
        metadata_dir, request.cell, remote_cell
    )
    manifest_path = _install_manifest(
        cell_dir, metadata_dir / "CELL_MANIFEST.json"
    )
    available_ids = list(manifest["trial_ids"])
    resolved_count = resolve_trial_count(
        request.trials,
        len(available_ids),
        accept_available=request.accept_available,
        input_func=input_func,
        is_tty=is_tty,
    )
    if resolved_count is None:
        return LoadResult(
            cell_dir=cell_dir,
            manifest_path=manifest_path,
            selection_path=cell_dir / "selections",
            selected_trial_ids=(),
            downloaded_trial_ids=(),
            reused_trial_ids=(),
            cancelled=True,
        )
    selected_ids, resolved_seed = select_trial_ids(
        available_ids,
        resolved_count,
        method=request.selection,
        seed=request.seed,
    )
    rows = {row["trial_id"]: row for row in manifest["trials"]}
    trials_dir = cell_dir / "trials"
    staging_dir = cell_dir / ".downloads.partial"
    trials_dir.mkdir(parents=True, exist_ok=True)
    staging_dir.mkdir(parents=True, exist_ok=True)
    reused: list[str] = []
    missing: list[str] = []
    for trial_id in selected_ids:
        final_dir = trials_dir / trial_id
        if final_dir.exists():
            validate_downloaded_trial(
                final_dir,
                trial_id,
                rows[trial_id],
            )
            reused.append(trial_id)
        else:
            missing.append(trial_id)
    downloaded: list[str] = []
    for batch in partition_batches(missing, request.batch_size):
        remote.download_batch(f"{remote_cell}/trials", batch, staging_dir)
        for trial_id in batch:
            partial_dir = staging_dir / trial_id
            validate_downloaded_trial(
                partial_dir,
                trial_id,
                rows[trial_id],
            )
            final_dir = trials_dir / trial_id
            if final_dir.exists():
                raise LoaderError(f"cache appeared during load: {trial_id}")
            os.replace(partial_dir, final_dir)
            downloaded.append(trial_id)
    selection_path = _selection_path(
        cell_dir,
        method=request.selection,
        requested=request.trials,
        resolved=resolved_count,
        seed=resolved_seed,
        trial_ids=selected_ids,
    )
    selection_manifest = {
        "schema_version": 1,
        "dataset_id": request.cell.dataset_id,
        "puzzle": request.cell.puzzle,
        "cell_id": request.cell.cell_id,
        "difficulty": request.cell.difficulty,
        "selection_method": request.selection,
        "requested_trial_count": request.trials,
        "resolved_trial_count": resolved_count,
        "available_trial_count": len(available_ids),
        "seed": resolved_seed,
        "trial_ids": selected_ids,
        "cell_manifest_sha256": sha256_file(manifest_path),
    }
    if selection_path.exists():
        if _read_json(selection_path, "selection manifest") != selection_manifest:
            raise LoaderError("selection manifest name collision")
    else:
        _write_json(selection_path, selection_manifest)
    return LoadResult(
        cell_dir=cell_dir,
        manifest_path=manifest_path,
        selection_path=selection_path,
        selected_trial_ids=tuple(selected_ids),
        downloaded_trial_ids=tuple(downloaded),
        reused_trial_ids=tuple(reused),
    )
