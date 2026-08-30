import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from data_access.config import DEFAULT_DATA_ROOT, resolve_data_root
from data_access.loader import (
    LoadRequest,
    LoaderError,
    RcloneRemoteBackend,
    load_hidden_data,
    partition_batches,
    resolve_trial_count,
    select_trial_ids,
)
from data_access.registry import CellSpec, RegistryError, get_puzzle_spec
from runners.load_hidden_data import parse_args
from runners.pancake_dataset_artifacts import md5_file, sha256_file, write_json


REMOTE_ROOT = "drive:fixture/full_hidden"


class FakeRemote:
    """filesystem fixtureをremoteとして扱うtest backend。"""

    def __init__(self, source: Path):
        self.source = source
        self.batches: list[list[str]] = []
        self.partial_seen: set[str] = set()
        self.metadata_downloads = 0

    def download_metadata(self, remote_cell: str, destination: Path) -> None:
        assert remote_cell == f"{REMOTE_ROOT}/N5_mm5"
        destination.mkdir(parents=True, exist_ok=True)
        self.metadata_downloads += 1
        for name in ("CELL_MANIFEST.json", "CELL_COMPLETE.json"):
            shutil.copyfile(self.source / name, destination / name)

    def download_batch(
        self,
        remote_trials: str,
        trial_ids: list[str],
        destination: Path,
    ) -> None:
        assert remote_trials == f"{REMOTE_ROOT}/N5_mm5/trials"
        self.batches.append(list(trial_ids))
        destination.mkdir(parents=True, exist_ok=True)
        for trial_id in trial_ids:
            target = destination / trial_id
            if target.exists():
                self.partial_seen.add(trial_id)
            shutil.copytree(
                self.source / "trials" / trial_id,
                target,
                dirs_exist_ok=True,
            )


@pytest.fixture
def cell_spec() -> CellSpec:
    return CellSpec(
        puzzle="pancake",
        dataset_id="pancake_full_hidden_distribution_v1",
        cell_id="N5_mm5",
        difficulty={"N": 5, "mm": 5},
        manifest_difficulty={"N": 5, "min_moves": 5},
        default_remote_root=REMOTE_ROOT,
    )


def _make_trial(directory: Path, trial_id: str) -> None:
    (directory / "raw").mkdir(parents=True)
    generated_sha256 = hashlib.sha256(trial_id.encode()).hexdigest()
    write_json(
        directory / "raw/metadata.json",
        {
            "trial_id": trial_id,
            "generated_token_count": 1,
            "generated_text_sha256": generated_sha256,
        },
    )
    (directory / "payload.bin").write_bytes(f"hidden:{trial_id}\n".encode())
    files = []
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        relative = path.relative_to(directory).as_posix()
        files.append(
            {
                "path": relative,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
                "md5": md5_file(path),
            }
        )
    write_json(directory / "checksums.json", {"schema_version": 1, "files": files})
    (directory / "checksums.sha256").write_text(
        "".join(f"{item['sha256']}  {item['path']}\n" for item in files),
        encoding="utf-8",
    )
    (directory / "checksums.md5").write_text(
        "".join(f"{item['md5']}  {item['path']}\n" for item in files),
        encoding="utf-8",
    )
    write_json(
        directory / "COMPLETE.json",
        {
            "schema_version": 1,
            "trial_id": trial_id,
            "status": "LOCAL_VALIDATED",
            "generated_token_count": 1,
            "generated_text_sha256": generated_sha256,
        },
    )


def _make_remote(tmp_path: Path, count: int = 6) -> Path:
    remote = tmp_path / "remote"
    trial_ids = [f"trial-{index:03d}" for index in range(count)]
    rows = []
    for trial_id in trial_ids:
        trial_dir = remote / "trials" / trial_id
        _make_trial(trial_dir, trial_id)
        rows.append(
            {
                "trial_id": trial_id,
                "checksums_sha256": sha256_file(trial_dir / "checksums.json"),
                "generated_token_count": 1,
                "generated_text_sha256": hashlib.sha256(trial_id.encode()).hexdigest(),
            }
        )
    manifest = {
        "schema_version": 1,
        "dataset_id": "pancake_full_hidden_distribution_v1",
        "cell_id": "N5_mm5",
        "N": 5,
        "min_moves": 5,
        "trial_count": count,
        "trial_ids": trial_ids,
        "trials": rows,
    }
    write_json(remote / "CELL_MANIFEST.json", manifest)
    write_json(
        remote / "CELL_COMPLETE.json",
        {
            "schema_version": 1,
            "cell_id": "N5_mm5",
            "remote_path": f"{REMOTE_ROOT}/N5_mm5",
            "local_manifest_sha256": sha256_file(remote / "CELL_MANIFEST.json"),
        },
    )
    return remote


def _request(
    cell_spec: CellSpec,
    data_root: Path,
    **overrides,
) -> LoadRequest:
    values = {
        "cell": cell_spec,
        "data_root": data_root,
        "remote_root": REMOTE_ROOT,
        "selection": "sequential",
        "batch_size": 5,
    }
    values.update(overrides)
    return LoadRequest(**values)


def test_data_root_precedence(tmp_path):
    cli = tmp_path / "cli"
    env = tmp_path / "env"

    assert resolve_data_root(cli, environ={"LPT_DATA_ROOT": str(env)}) == cli.resolve()
    assert resolve_data_root(None, environ={"LPT_DATA_ROOT": str(env)}) == env.resolve()
    assert resolve_data_root(None, environ={}) == DEFAULT_DATA_ROOT.resolve()


def test_partition_batches_uses_default_sized_groups():
    assert [len(batch) for batch in partition_batches(list("abcdefghijkl"), 5)] == [5, 5, 2]
    with pytest.raises(ValueError, match="positive"):
        partition_batches(["a"], 0)


def test_rclone_backend_downloads_one_batch_with_include_filters(
    tmp_path, monkeypatch
):
    commands = []

    def fake_run(command, text, capture_output, check):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("data_access.loader.subprocess.run", fake_run)

    RcloneRemoteBackend("fake-rclone").download_batch(
        "drive:root/N5_mm5/trials",
        ["trial-a", "trial-b"],
        tmp_path / "staging",
    )

    assert len(commands) == 1
    assert commands[0][:3] == [
        "fake-rclone",
        "copy",
        "drive:root/N5_mm5/trials",
    ]
    assert commands[0].count("--include") == 2
    assert "/trial-a/**" in commands[0]
    assert "/trial-b/**" in commands[0]


@pytest.mark.skipif(shutil.which("rclone") is None, reason="rclone is not installed")
def test_installed_rclone_copies_only_selected_trial_directories(tmp_path):
    """実rcloneでproduction引数と複数includeの互換性を確認する。"""
    remote = _make_remote(tmp_path, count=3)
    destination = tmp_path / "actual-rclone-download"

    RcloneRemoteBackend("rclone").download_batch(
        str(remote / "trials"),
        ["trial-000", "trial-002"],
        destination,
    )

    assert sorted(path.name for path in destination.iterdir()) == [
        "trial-000",
        "trial-002",
    ]
    assert (destination / "trial-000/payload.bin").is_file()
    assert (destination / "trial-002/payload.bin").is_file()


def test_sequential_selection_preserves_frozen_plan_order():
    selected, seed = select_trial_ids(
        ["trial-3", "trial-1", "trial-2"], 2, method="sequential", seed=None
    )

    assert selected == ["trial-3", "trial-1"]
    assert seed is None
    with pytest.raises(LoaderError, match="seed"):
        select_trial_ids(["a"], 1, method="sequential", seed=42)


def test_random_selection_defaults_to_seed_42_and_is_reproducible():
    ids = [f"trial-{index}" for index in range(20)]

    first, first_seed = select_trial_ids(ids, 8, method="random", seed=None)
    second, second_seed = select_trial_ids(ids, 8, method="random", seed=42)

    assert first == second
    assert first_seed == second_seed == 42
    assert len(first) == len(set(first)) == 8


@pytest.mark.parametrize("requested", [0, -1])
def test_invalid_trial_count_is_rejected(requested):
    with pytest.raises(LoaderError, match="positive"):
        resolve_trial_count(requested, 6, accept_available=False, is_tty=False)


def test_missing_trial_count_resolves_to_maximum():
    assert resolve_trial_count(None, 6, accept_available=False) == 6
    assert resolve_trial_count(6, 6, accept_available=False) == 6


def test_over_max_prompts_once_and_accepts_yes():
    prompts = []

    result = resolve_trial_count(
        10,
        6,
        accept_available=False,
        is_tty=True,
        input_func=lambda prompt: prompts.append(prompt) or "y",
    )

    assert result == 6
    assert len(prompts) == 1
    assert "6件しかありません" in prompts[0]


def test_over_max_no_cancels_and_accept_flag_skips_prompt():
    assert resolve_trial_count(
        10,
        6,
        accept_available=False,
        is_tty=True,
        input_func=lambda _: "n",
    ) is None
    assert resolve_trial_count(
        10,
        6,
        accept_available=True,
        is_tty=False,
        input_func=lambda _: pytest.fail("must not prompt"),
    ) == 6


def test_over_max_non_tty_fails_without_flag():
    with pytest.raises(LoaderError, match="accept-available"):
        resolve_trial_count(10, 6, accept_available=False, is_tty=False)


def test_tiny_end_to_end_downloads_six_trials_in_five_and_one(
    tmp_path, cell_spec
):
    remote = _make_remote(tmp_path)
    backend = FakeRemote(remote)

    result = load_hidden_data(
        _request(cell_spec, tmp_path / "cache"),
        backend=backend,
        is_tty=False,
    )

    assert [len(batch) for batch in backend.batches] == [5, 1]
    assert len(result.downloaded_trial_ids) == 6
    assert result.selection_path.is_file()
    selection = json.loads(result.selection_path.read_text(encoding="utf-8"))
    assert selection["selection_method"] == "sequential"
    assert selection["requested_trial_count"] is None
    assert selection["resolved_trial_count"] == 6
    assert selection["trial_ids"] == [f"trial-{index:03d}" for index in range(6)]
    assert not list((result.cell_dir / "trials").glob("*.partial"))


def test_valid_cache_is_verified_and_reused(tmp_path, cell_spec):
    remote = _make_remote(tmp_path, count=2)
    first_backend = FakeRemote(remote)
    request = _request(cell_spec, tmp_path / "cache", trials=2)
    first = load_hidden_data(request, backend=first_backend, is_tty=False)
    second_backend = FakeRemote(remote)

    second = load_hidden_data(request, backend=second_backend, is_tty=False)

    assert second.downloaded_trial_ids == ()
    assert second.reused_trial_ids == first.selected_trial_ids
    assert second_backend.batches == []
    assert second.selection_path == first.selection_path


def test_existing_partial_directory_is_resumed(tmp_path, cell_spec):
    remote = _make_remote(tmp_path, count=1)
    cache = tmp_path / "cache"
    partial = (
        cache
        / cell_spec.dataset_id
        / "pancake/N5_mm5/.downloads.partial/trial-000"
    )
    partial.mkdir(parents=True)
    (partial / "payload.bin").write_bytes(b"incomplete")
    backend = FakeRemote(remote)

    result = load_hidden_data(
        _request(cell_spec, cache, trials=1), backend=backend, is_tty=False
    )

    assert backend.partial_seen == {"trial-000"}
    assert result.downloaded_trial_ids == ("trial-000",)
    assert not partial.exists()


def test_corrupt_cached_trial_stops_without_overwrite(tmp_path, cell_spec):
    remote = _make_remote(tmp_path, count=1)
    cache = tmp_path / "cache"
    request = _request(cell_spec, cache, trials=1)
    first = load_hidden_data(request, backend=FakeRemote(remote), is_tty=False)
    payload = first.cell_dir / "trials/trial-000/payload.bin"
    payload.write_bytes(b"corrupt")
    backend = FakeRemote(remote)

    with pytest.raises(LoaderError, match="size mismatch|SHA-256 mismatch"):
        load_hidden_data(request, backend=backend, is_tty=False)

    assert payload.read_bytes() == b"corrupt"
    assert backend.batches == []


def test_download_checksum_mismatch_remains_staged(tmp_path, cell_spec):
    remote = _make_remote(tmp_path, count=1)
    (remote / "trials/trial-000/payload.bin").write_bytes(b"remote-corrupt")
    request = _request(cell_spec, tmp_path / "cache", trials=1)

    with pytest.raises(LoaderError, match="size mismatch|SHA-256 mismatch"):
        load_hidden_data(request, backend=FakeRemote(remote), is_tty=False)

    final = (
        request.data_root
        / cell_spec.dataset_id
        / "pancake/N5_mm5/trials/trial-000"
    )
    staged = final.parents[1] / ".downloads.partial/trial-000"
    assert not final.exists()
    assert staged.is_dir()


def test_prompt_no_does_not_download_trials(tmp_path, cell_spec):
    remote = _make_remote(tmp_path, count=2)
    backend = FakeRemote(remote)

    result = load_hidden_data(
        _request(cell_spec, tmp_path / "cache", trials=3),
        backend=backend,
        is_tty=True,
        input_func=lambda _: "n",
    )

    assert result.cancelled is True
    assert backend.batches == []


def test_accept_available_downloads_max_without_prompt(tmp_path, cell_spec):
    remote = _make_remote(tmp_path, count=2)
    backend = FakeRemote(remote)

    result = load_hidden_data(
        _request(
            cell_spec,
            tmp_path / "cache",
            trials=3,
            accept_available=True,
        ),
        backend=backend,
        is_tty=False,
        input_func=lambda _: pytest.fail("must not prompt"),
    )

    assert len(result.selected_trial_ids) == 2


def test_registry_rejects_unsupported_puzzle_and_difficulty():
    with pytest.raises(RegistryError, match="unsupported puzzle"):
        get_puzzle_spec("hanoi")
    with pytest.raises(RegistryError, match="unsupported difficulty"):
        get_puzzle_spec("pancake").resolve_cell({"N": 3, "mm": 5})


def test_cli_rejects_seed_for_sequential_and_non_positive_values():
    with pytest.raises(SystemExit):
        parse_args(
            [
                "--puzzle",
                "pancake",
                "--N",
                "5",
                "--mm",
                "5",
                "--seed",
                "42",
            ]
        )
    with pytest.raises(SystemExit):
        parse_args(
            [
                "--puzzle",
                "pancake",
                "--N",
                "5",
                "--mm",
                "5",
                "--trials",
                "0",
            ]
        )


def test_random_selection_manifest_records_default_seed(tmp_path, cell_spec):
    remote = _make_remote(tmp_path, count=6)

    result = load_hidden_data(
        _request(
            cell_spec,
            tmp_path / "cache",
            trials=3,
            selection="random",
        ),
        backend=FakeRemote(remote),
        is_tty=False,
    )

    selection = json.loads(result.selection_path.read_text(encoding="utf-8"))
    assert selection["seed"] == 42
    assert "seed42" in result.selection_path.name
    assert selection["trial_ids"] == list(result.selected_trial_ids)
