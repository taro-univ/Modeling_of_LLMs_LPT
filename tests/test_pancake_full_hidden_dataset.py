import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

from envs.pancake_env import PancakeSortingEnv
from runners import pancake_dataset_artifacts as artifacts
from runners.pancake_dataset_artifacts import (
    HiddenH5Writer,
    build_debug_replay,
    build_span_artifact,
    build_trial_plan,
    validate_h5,
)
from runners.pancake_drive_transfer import (
    RcloneDriveTransfer,
    TransferError,
    safe_delete_local_cell,
)
from runners.pancake_full_hidden_dataset import load_config


CONFIG = Path("configs/pancake_full_hidden_dataset_v1.json")


def test_frozen_plan_has_six_balanced_cells_and_unique_trial_ids():
    config = load_config(CONFIG)
    plans = build_trial_plan(config)

    assert len(plans) == 600
    assert len({plan.trial_id for plan in plans}) == 600
    assert [plan.sample_seed for plan in plans] == list(range(1, 601))
    assert len({plan.sample_seed for plan in plans}) == 600
    counts = {}
    for plan in plans:
        counts[plan.cell_id] = counts.get(plan.cell_id, 0) + 1
        env = PancakeSortingEnv(plan.N, initial_state=plan.initial_state)
        assert env.min_moves == plan.min_moves
    assert counts == {
        "N3_mm3": 100,
        "N4_mm3": 100,
        "N4_mm4": 100,
        "N5_mm3": 100,
        "N5_mm4": 100,
        "N5_mm5": 100,
    }


def test_n4_mm4_uses_34_33_33_allocation():
    plans = [
        plan for plan in build_trial_plan(load_config(CONFIG))
        if plan.cell_id == "N4_mm4"
    ]
    by_state = {}
    for plan in plans:
        by_state[plan.state_index] = by_state.get(plan.state_index, 0) + 1
    assert by_state == {1: 34, 2: 33, 3: 33}


def test_debug_replay_separates_reasoning_and_final_submission():
    env = PancakeSortingEnv(3, initial_state=(1, 3, 2))
    text = (
        "<think>Flip 2\nFlip 3\nFlip 2\n</think>"
        "<final>Flip 2\n</final>"
    )

    replay, labels = build_debug_replay(env, text, "eos")

    assert replay["reasoning_mentions_replay"]["goal_reached"] is True
    assert len(replay["reasoning_mentions_replay"]["mentions"]) == 3
    assert len(replay["final_submission_replay"]["mentions"]) == 1
    assert replay["final_submission_replay"]["goal_reached"] is False
    assert labels["outcome"] == "search_success_final_fail"


class _OffsetTokenizer:
    def __call__(self, text, add_special_tokens=False, return_offsets_mapping=False):
        assert add_special_tokens is False
        assert return_offsets_mapping is True
        return {
            "input_ids": [10, 11, 12],
            "offset_mapping": [(0, 7), (7, 14), (14, len(text))],
        }


def test_span_artifact_requires_generated_id_verification():
    text = "Flip 2<final>x</final>"

    verified = build_span_artifact(text, [10, 11, 12], _OffsetTokenizer())
    rejected = build_span_artifact(text, [10, 99, 12], _OffsetTokenizer())

    assert verified["mapping_verified"] is True
    assert any(item["kind"] == "move_mention" for item in verified["spans"])
    assert any(item["kind"] == "final_tag" for item in verified["spans"])
    assert rejected["mapping_verified"] is False
    assert all("token_span" not in item for item in rejected["spans"])


@pytest.mark.skipif(artifacts.h5py is None, reason="h5py is not installed locally")
def test_hdf5_writer_streams_and_atomically_finalizes(tmp_path):
    partial = tmp_path / "hidden.h5.partial"
    writer = HiddenH5Writer(
        partial,
        num_layers=2,
        hidden_size=3,
        buffer_tokens=2,
    )
    for token in range(3):
        writer.append(
            np.full((2, 3), token, dtype=np.float16),
            token_id=100 + token,
            token_position=token,
        )

    final = writer.finalize({"trial_id": "fixture"})

    assert final == tmp_path / "hidden.h5"
    assert final.is_file()
    assert not partial.exists()
    assert validate_h5(final, expected_rows=3, num_layers=2, hidden_size=3)[
        "finite"
    ] is True


class FakeRclone:
    def __init__(self, *, corrupt_after_copy=False, fail_copy=False):
        self.remote = {}
        self.contents = {}
        self.commands = []
        self.corrupt_after_copy = corrupt_after_copy
        self.fail_copy = fail_copy
        self.copied = False

    @staticmethod
    def _md5(path):
        return hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()

    def __call__(self, command, text, capture_output, check):
        assert text is True
        assert capture_output is True
        assert check is False
        self.commands.append(command)
        operation = command[1]
        if operation == "mkdir":
            return subprocess.CompletedProcess(command, 0, "", "")
        if operation == "copy":
            if self.fail_copy:
                return subprocess.CompletedProcess(command, 9, "", "quota exceeded")
            source = Path(command[2])
            for path in source.rglob("*"):
                if not path.is_file() or path.name in {"CELL_COMPLETE.json", "transfer_receipt.json"}:
                    continue
                relative = path.relative_to(source).as_posix()
                self.remote[relative] = {
                    "Path": relative,
                    "Size": path.stat().st_size,
                    "Hashes": {"MD5": self._md5(path)},
                }
                self.contents[relative] = path.read_bytes()
            self.copied = True
            return subprocess.CompletedProcess(command, 0, "", "")
        if operation == "copyto":
            source = Path(command[2])
            self.remote["CELL_COMPLETE.json"] = {
                "Path": "CELL_COMPLETE.json",
                "Size": source.stat().st_size,
                "Hashes": {"MD5": self._md5(source)},
            }
            self.contents["CELL_COMPLETE.json"] = source.read_bytes()
            return subprocess.CompletedProcess(command, 0, "", "")
        if operation == "cat":
            return subprocess.CompletedProcess(
                command,
                0,
                self.contents["CELL_COMPLETE.json"].decode("utf-8"),
                "",
            )
        if operation == "lsjson":
            rows = list(self.remote.values())
            if self.corrupt_after_copy and self.copied and rows:
                rows = [dict(row) for row in rows]
                rows[0] = {**rows[0], "Hashes": {"MD5": "0" * 32}}
            return subprocess.CompletedProcess(command, 0, json.dumps(rows), "")
        raise AssertionError(command)


def _make_cell(tmp_path, cell_id="N3_mm3"):
    cell = tmp_path / "cells" / cell_id
    cell.mkdir(parents=True)
    (cell / "data.bin").write_bytes(b"full-hidden-fixture")
    (cell / "CELL_MANIFEST.json").write_text("{}\n", encoding="utf-8")
    (cell / "LOCAL_COMPLETE.json").write_text("{}\n", encoding="utf-8")
    return cell


def test_rclone_upload_verifies_payload_then_writes_remote_marker(tmp_path):
    cell = _make_cell(tmp_path)
    receipts = tmp_path / "receipts"
    fake = FakeRclone()
    transfer = RcloneDriveTransfer(rclone_binary="fake-rclone", run_command=fake)

    receipt = transfer.upload_cell(cell, "drive:research/full_hidden_v1", receipts)

    operations = [command[1] for command in fake.commands]
    assert operations.index("copy") < operations.index("copyto")
    assert "CELL_COMPLETE.json" in fake.remote
    assert receipt["status"] == "REMOTE_VERIFIED"
    assert (receipts / "N3_mm3_transfer_receipt.json").is_file()
    assert cell.is_dir()


def test_hash_mismatch_preserves_local_and_never_writes_marker(tmp_path):
    cell = _make_cell(tmp_path)
    receipts = tmp_path / "receipts"
    fake = FakeRclone(corrupt_after_copy=True)
    transfer = RcloneDriveTransfer(run_command=fake)

    with pytest.raises(TransferError, match="MD5 mismatch"):
        transfer.upload_cell(cell, "drive:research/full_hidden_v1", receipts)

    assert cell.is_dir()
    assert "CELL_COMPLETE.json" not in fake.remote
    assert not (receipts / "N3_mm3_transfer_receipt.json").exists()


def test_quota_failure_preserves_local_and_stops_before_marker(tmp_path):
    cell = _make_cell(tmp_path)
    fake = FakeRclone(fail_copy=True)
    transfer = RcloneDriveTransfer(run_command=fake)

    with pytest.raises(TransferError, match="quota exceeded"):
        transfer.upload_cell(cell, "drive:research/full_hidden_v1", tmp_path / "receipts")

    assert cell.is_dir()
    assert all(command[1] != "copyto" for command in fake.commands)


def test_partial_artifact_is_never_uploaded(tmp_path):
    cell = _make_cell(tmp_path)
    (cell / "hidden.h5.partial").write_bytes(b"partial")
    fake = FakeRclone()
    transfer = RcloneDriveTransfer(run_command=fake)

    with pytest.raises(TransferError, match="partial artifacts"):
        transfer.upload_cell(cell, "drive:research/full_hidden_v1", tmp_path / "receipts")

    assert fake.commands == []


def test_local_delete_requires_matching_remote_verified_receipt(tmp_path):
    cell = _make_cell(tmp_path)
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps({"status": "REMOTE_VERIFIED", "cell_id": "N4_mm3"}),
        encoding="utf-8",
    )

    with pytest.raises(TransferError, match="does not match"):
        safe_delete_local_cell(cell, cell.parent, receipt)

    assert cell.is_dir()


def test_local_delete_removes_only_verified_cell(tmp_path):
    cell = _make_cell(tmp_path)
    sibling = cell.parent / "N4_mm3"
    sibling.mkdir()
    receipt = tmp_path / "receipt.json"
    manifest_sha256 = hashlib.sha256(
        (cell / "CELL_MANIFEST.json").read_bytes()
    ).hexdigest()
    receipt.write_text(
        json.dumps(
            {
                "status": "REMOTE_VERIFIED",
                "cell_id": "N3_mm3",
                "local_manifest_sha256": manifest_sha256,
                "remote_path": "drive:research/full_hidden_v1/N3_mm3",
            }
        ),
        encoding="utf-8",
    )

    safe_delete_local_cell(cell, cell.parent, receipt)

    assert not cell.exists()
    assert sibling.is_dir()


def test_local_delete_rejects_stale_receipt_manifest(tmp_path):
    cell = _make_cell(tmp_path)
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "status": "REMOTE_VERIFIED",
                "cell_id": "N3_mm3",
                "local_manifest_sha256": "0" * 64,
                "remote_path": "drive:research/full_hidden_v1/N3_mm3",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(TransferError, match="manifest SHA-256"):
        safe_delete_local_cell(cell, cell.parent, receipt)

    assert cell.is_dir()


def test_resume_rejects_stale_remote_marker_manifest(tmp_path):
    cell = _make_cell(tmp_path)
    fake = FakeRclone()
    transfer = RcloneDriveTransfer(run_command=fake)
    transfer.upload_cell(cell, "drive:research/full_hidden_v1", tmp_path / "receipts_a")
    stale_marker = {
        "schema_version": 1,
        "cell_id": "N3_mm3",
        "remote_path": "drive:research/full_hidden_v1/N3_mm3",
        "local_manifest_sha256": "0" * 64,
    }
    stale_bytes = (json.dumps(stale_marker) + "\n").encode("utf-8")
    fake.contents["CELL_COMPLETE.json"] = stale_bytes
    fake.remote["CELL_COMPLETE.json"] = {
        "Path": "CELL_COMPLETE.json",
        "Size": len(stale_bytes),
        "Hashes": {
            "MD5": hashlib.md5(stale_bytes, usedforsecurity=False).hexdigest()
        },
    }

    with pytest.raises(TransferError, match="remote marker manifest SHA-256"):
        transfer.upload_cell(
            cell,
            "drive:research/full_hidden_v1",
            tmp_path / "receipts_b",
        )

    assert cell.is_dir()
    assert not (tmp_path / "receipts_b/N3_mm3_transfer_receipt.json").exists()
