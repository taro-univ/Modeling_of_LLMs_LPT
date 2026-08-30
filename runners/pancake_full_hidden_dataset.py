"""Pancake full-hidden distribution datasetをcell単位で取得する。"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import itertools
import json
import os
import resource
import shutil
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from envs.pancake_env import PancakeSortingEnv
from runners import run_local
from runners.pancake_dataset_artifacts import (
    HiddenH5Writer,
    TrialPlan,
    build_debug_replay,
    build_span_artifact,
    build_trial_plan,
    canonical_json_bytes,
    plan_manifest,
    sha256_file,
    validate_trial_dir,
    write_json,
    write_trial_checksums,
)
from runners.pancake_drive_transfer import (
    RcloneDriveTransfer,
    TransferError,
    safe_delete_local_cell,
    validate_remote_root,
)


DEFAULT_CONFIG = Path("configs/pancake_full_hidden_dataset_v1.json")
DEFAULT_SPOOL_ROOT = Path("results/pancake/full_hidden_distribution")


def load_config(path: Path) -> dict[str, Any]:
    """dataset configを読み、固定条件を検証する。"""
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema_version") != 1:
        raise ValueError("unsupported dataset config schema")
    if config.get("sample_seed_scheme") != "global_unique_1_to_600_in_frozen_plan_order":
        raise ValueError("unsupported sample_seed_scheme")
    if config["generation"] != {
        "temperature": 0.6,
        "repetition_penalty": 1.1,
        "n_shot": 0,
        "num_predict": 8192,
        "early_stop": False,
    }:
        raise ValueError("generation settings differ from the frozen dataset contract")
    expected_capture = {
        "token_source": "generated",
        "token_stride": 1,
        "layers": "all",
        "expected_num_layers": 48,
        "expected_hidden_size": 5120,
        "dtype": "float16",
        "format": "hdf5",
        "compression": "gzip",
        "buffer_tokens": 64,
    }
    if config["capture"] != expected_capture:
        raise ValueError("capture settings differ from the frozen dataset contract")
    plans = build_trial_plan(config)
    if len(plans) != 600:
        raise ValueError(f"dataset must contain 600 trials, got {len(plans)}")
    expected_cells = {
        (3, 3): 1,
        (4, 3): 11,
        (4, 4): 3,
        (5, 3): 35,
        (5, 4): 48,
        (5, 5): 20,
    }
    configured_cells = {(int(cell["N"]), int(cell["min_moves"])) for cell in config["cells"]}
    if configured_cells != set(expected_cells):
        raise ValueError("dataset must contain exactly the six feasible frozen cells")
    for cell in config["cells"]:
        key = (int(cell["N"]), int(cell["min_moves"]))
        if int(cell["available_state_count"]) != expected_cells[key]:
            raise ValueError(f"{cell['cell_id']}: available_state_count mismatch")
        actual_count = sum(
            1
            for state in itertools.permutations(range(1, key[0] + 1))
            if state != tuple(range(1, key[0] + 1))
            and PancakeSortingEnv(key[0], initial_state=state).min_moves == key[1]
        )
        if actual_count != expected_cells[key]:
            raise ValueError(f"{cell['cell_id']}: BFS distance shell count changed")
    return config


def available_bytes(path: Path) -> int:
    """pathを含むfilesystemの空きbyte数を返す。"""
    path.mkdir(parents=True, exist_ok=True)
    return int(shutil.disk_usage(path).free)


def require_free_space(path: Path, required_gb: float, stage: str) -> None:
    """規定空き容量を満たさなければ生成前に停止する。"""
    free = available_bytes(path)
    required = int(required_gb * 1_000_000_000)
    if free < required:
        raise RuntimeError(
            f"disk preflight failed at {stage}: free={free / 1e9:.1f} GB "
            f"required={required_gb:.1f} GB"
        )


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _atomic_finalize_directory(partial_dir: Path, final_dir: Path) -> None:
    """同一filesystem内でtrial directoryをatomicに確定する。"""
    if final_dir.exists():
        raise FileExistsError(f"final trial already exists: {final_dir}")
    os.replace(partial_dir, final_dir)


def _capture_last_hidden(outputs: Any, num_layers: int) -> np.ndarray:
    """全Transformer layerのlast-position hiddenを一括CPU転送する。"""
    torch = run_local.torch
    if torch is None:
        raise RuntimeError("generation requires torch")
    stacked = torch.stack(
        [outputs.hidden_states[index][0, -1, :] for index in range(1, num_layers + 1)],
        dim=0,
    )
    return stacked.float().cpu().numpy().astype(np.float16, copy=False)


def _resource_metrics(torch: Any, device: Any) -> dict[str, float | None]:
    """smokeの容量判断に使うprocess/GPU peakを取得する。"""
    peak_rss_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    metrics: dict[str, float | None] = {
        "process_peak_rss_mb": round(float(peak_rss_kib) / 1024.0, 3),
        "cuda_peak_allocated_mb": None,
        "cuda_peak_reserved_mb": None,
    }
    if getattr(device, "type", None) == "cuda" and torch.cuda.is_available():
        metrics["cuda_peak_allocated_mb"] = round(
            torch.cuda.max_memory_allocated(device) / (1024 ** 2), 3
        )
        metrics["cuda_peak_reserved_mb"] = round(
            torch.cuda.max_memory_reserved(device) / (1024 ** 2), 3
        )
    return metrics


def generate_trial(
    plan: TrialPlan,
    config: dict[str, Any],
    model: Any,
    tokenizer: Any,
    profile: run_local.ModelProfile,
    trials_dir: Path,
) -> dict[str, Any]:
    """1 trialをstream生成し、不変artifactをatomic確定する。

    Parameters
    ----------
    plan:
        固定された問題stateとsample seed。
    config:
        dataset config。
    model, tokenizer, profile:
        1回だけloadしてcell間で再利用するHF object。
    trials_dir:
        cell内のtrial保存先。

    Returns
    -------
    dict
        完了trialのmetadata。
    """
    torch = run_local.torch
    if torch is None:
        raise RuntimeError("generation requires torch")
    capture = config["capture"]
    generation = config["generation"]
    num_layers = int(model.config.num_hidden_layers)
    hidden_size = int(model.config.hidden_size)
    if num_layers != int(capture["expected_num_layers"]):
        raise RuntimeError(f"model has {num_layers} layers; expected 48")
    if hidden_size != int(capture["expected_hidden_size"]):
        raise RuntimeError(f"model hidden_size={hidden_size}; expected 5120")

    final_dir = trials_dir / plan.trial_id
    partial_dir = trials_dir / f"{plan.trial_id}.partial"
    if final_dir.is_dir():
        validate_trial_dir(final_dir, plan.trial_id)
        return json.loads((final_dir / "raw/metadata.json").read_text(encoding="utf-8"))
    if partial_dir.exists():
        raise RuntimeError(
            f"incomplete trial exists and was preserved: {partial_dir}; "
            "inspect or remove it explicitly before resume"
        )
    partial_dir.mkdir(parents=True)
    env = PancakeSortingEnv(N=plan.N, initial_state=plan.initial_state)
    prompt = env.get_prompt()
    formatted_prompt = run_local.format_prompt_text(
        tokenizer, prompt, env, int(generation["n_shot"]), profile
    )
    (partial_dir / "raw").mkdir()
    (partial_dir / "hidden").mkdir()
    (partial_dir / "debug").mkdir()
    (partial_dir / "labels").mkdir()
    (partial_dir / "raw/prompt.txt").write_text(prompt, encoding="utf-8")
    (partial_dir / "raw/formatted_prompt.txt").write_text(
        formatted_prompt, encoding="utf-8"
    )

    run_local._set_sample_seed(plan.sample_seed)
    device = next(model.parameters()).device
    if getattr(device, "type", None) == "cuda" and torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats(device)
    input_ids = tokenizer(formatted_prompt, return_tensors="pt").input_ids.to(device)
    prompt_token_count = int(input_ids.shape[1])
    current_input_ids = input_ids
    past_key_values = None
    generated_ids: list[int] = []
    done_reason = "length"
    sampled_eos_token_id: int | None = None
    writer = HiddenH5Writer(
        partial_dir / "hidden/hidden.h5.partial",
        num_layers=num_layers,
        hidden_size=hidden_size,
        buffer_tokens=int(capture["buffer_tokens"]),
        compression=str(capture["compression"]),
    )
    started = time.monotonic()
    try:
        for position in range(int(generation["num_predict"])):
            with torch.no_grad():
                outputs = model(
                    input_ids=current_input_ids,
                    past_key_values=past_key_values,
                    use_cache=True,
                    output_hidden_states=True,
                )
            logits = outputs.logits[0, -1, :].float()
            run_local._apply_repetition_penalty(
                logits, generated_ids, float(generation["repetition_penalty"])
            )
            next_token_id = run_local._sample_next_token(
                logits, float(generation["temperature"])
            )
            if next_token_id == tokenizer.eos_token_id:
                done_reason = "eos"
                sampled_eos_token_id = next_token_id
                break
            hidden = _capture_last_hidden(outputs, num_layers)
            writer.append(hidden, next_token_id, position)
            generated_ids.append(next_token_id)
            past_key_values = outputs.past_key_values
            current_input_ids = torch.tensor([[next_token_id]], device=device)
        elapsed = time.monotonic() - started
        generated_text = tokenizer.decode(generated_ids, skip_special_tokens=True)
        text_sha256 = hashlib.sha256(generated_text.encode("utf-8")).hexdigest()
        span_artifact = build_span_artifact(generated_text, generated_ids, tokenizer)
        metadata = {
            "schema_version": 1,
            "dataset_id": plan.dataset_id,
            "cell_id": plan.cell_id,
            "trial_id": plan.trial_id,
            "N": plan.N,
            "min_moves": plan.min_moves,
            "state_index": plan.state_index,
            "state_trial_index": plan.state_trial_index,
            "initial_state": list(plan.initial_state),
            "goal_state": list(env.goal_state),
            "sample_seed": plan.sample_seed,
            "model_id": config["model_id"],
            "model_revision": getattr(model.config, "_commit_hash", None),
            "tokenizer_name": getattr(tokenizer, "name_or_path", None),
            "torch_version": getattr(torch, "__version__", None),
            "transformers_version": _package_version("transformers"),
            "h5py_version": _package_version("h5py"),
            "temperature": generation["temperature"],
            "repetition_penalty": generation["repetition_penalty"],
            "n_shot": generation["n_shot"],
            "num_predict": generation["num_predict"],
            "early_stop_enabled": False,
            "done_reason": done_reason,
            "sampled_eos_token_id": sampled_eos_token_id,
            "prompt_token_count": prompt_token_count,
            "generated_token_count": len(generated_ids),
            "generated_text_sha256": text_sha256,
            "span_token_mapping_verified": span_artifact["mapping_verified"],
            "num_layers": num_layers,
            "hidden_size": hidden_size,
            "hidden_dtype": "float16",
            "hidden_shape": [len(generated_ids), num_layers, hidden_size],
            "token_source": "generated",
            "token_stride": 1,
            "hidden_token_alignment": "row_t_is_context_state_used_to_sample_token_id_t",
            "hidden_states_tuple_indices": [1, num_layers],
            "capture_point_note": (
                "outputs.hidden_states[1..L] last position; final norm placement "
                "must be confirmed against the pinned model implementation"
            ),
            "eos_hidden_saved": False,
            "elapsed_sec": round(elapsed, 3),
            **_resource_metrics(torch, device),
        }
        hidden_path = writer.finalize(metadata)
        metadata["hidden_file_bytes"] = hidden_path.stat().st_size
    except BaseException:
        writer.close_incomplete()
        raise

    (partial_dir / "raw/generated.txt").write_text(generated_text, encoding="utf-8")
    with (partial_dir / "raw/generated_token_ids.npy").open("wb") as handle:
        np.save(handle, np.asarray(generated_ids, dtype=np.int32), allow_pickle=False)
    write_json(partial_dir / "raw/spans_v1.json", span_artifact)
    write_json(partial_dir / "raw/metadata.json", metadata)
    replay, labels = build_debug_replay(env, generated_text, done_reason)
    write_json(partial_dir / "debug/replay_v1.json", replay)
    write_json(partial_dir / "labels/labels_v1.json", labels)
    write_trial_checksums(partial_dir)
    write_json(
        partial_dir / "COMPLETE.json",
        {
            "schema_version": 1,
            "trial_id": plan.trial_id,
            "status": "LOCAL_VALIDATED",
            "generated_token_count": len(generated_ids),
            "generated_text_sha256": metadata["generated_text_sha256"],
        },
    )
    validate_trial_dir(partial_dir, plan.trial_id, allow_partial=True)
    _atomic_finalize_directory(partial_dir, final_dir)
    return metadata


def finalize_cell(cell_dir: Path, plans: list[TrialPlan]) -> dict[str, Any]:
    """100 trialを検証し、cell manifestとLOCAL_COMPLETEを作る。"""
    if len(plans) not in (1, 100):
        raise ValueError("a production cell must have 100 trials; smoke must have one")
    trials_dir = cell_dir / "trials"
    partials = list(trials_dir.glob("*.partial"))
    if partials:
        raise RuntimeError(f"partial trial remains: {partials[0]}")
    expected_ids = [plan.trial_id for plan in plans]
    actual_ids = sorted(path.name for path in trials_dir.iterdir() if path.is_dir())
    if sorted(expected_ids) != actual_ids:
        raise RuntimeError("cell trial IDs differ from its frozen plan")
    trial_rows = []
    for plan in plans:
        validate_trial_dir(
            trials_dir / plan.trial_id,
            plan.trial_id,
            check_hidden_values=False,
        )
        metadata = json.loads(
            (trials_dir / plan.trial_id / "raw/metadata.json").read_text(encoding="utf-8")
        )
        checksums_path = trials_dir / plan.trial_id / "checksums.json"
        trial_rows.append(
            {
                "trial_id": plan.trial_id,
                "state_index": plan.state_index,
                "state_trial_index": plan.state_trial_index,
                "initial_state": list(plan.initial_state),
                "sample_seed": plan.sample_seed,
                "done_reason": metadata["done_reason"],
                "generated_token_count": metadata["generated_token_count"],
                "generated_text_sha256": metadata["generated_text_sha256"],
                "checksums_sha256": sha256_file(checksums_path),
            }
        )
    manifest = {
        "schema_version": 1,
        "dataset_id": plans[0].dataset_id,
        "cell_id": cell_dir.name,
        "N": plans[0].N,
        "min_moves": plans[0].min_moves,
        "trial_count": len(plans),
        "trial_ids": expected_ids,
        "trials": trial_rows,
    }
    write_json(cell_dir / "CELL_MANIFEST.json", manifest)
    checksum_lines_sha256 = []
    checksum_lines_md5 = []
    for plan in plans:
        checksum_payload = json.loads(
            (trials_dir / plan.trial_id / "checksums.json").read_text(encoding="utf-8")
        )
        for item in checksum_payload["files"]:
            relative = f"trials/{plan.trial_id}/{item['path']}"
            checksum_lines_sha256.append(f"{item['sha256']}  {relative}\n")
            checksum_lines_md5.append(f"{item['md5']}  {relative}\n")
    (cell_dir / "checksums.sha256").write_text(
        "".join(checksum_lines_sha256), encoding="utf-8"
    )
    (cell_dir / "checksums.md5").write_text(
        "".join(checksum_lines_md5), encoding="utf-8"
    )
    manifest_sha = sha256_file(cell_dir / "CELL_MANIFEST.json")
    write_json(
        cell_dir / "LOCAL_COMPLETE.json",
        {
            "schema_version": 1,
            "cell_id": cell_dir.name,
            "status": "LOCAL_COMPLETE",
            "trial_count": len(plans),
            "cell_manifest_sha256": manifest_sha,
        },
    )
    return manifest


def _select_execution_plans(
    all_plans: list[TrialPlan],
    selected_cells: list[str] | None,
    smoke: str | None,
) -> list[tuple[str, list[TrialPlan]]]:
    by_cell: dict[str, list[TrialPlan]] = {}
    for plan in all_plans:
        by_cell.setdefault(plan.cell_id, []).append(plan)
    if smoke == "schema":
        return [("SMOKE_SCHEMA_N3_mm3", [by_cell["N3_mm3"][0]])]
    if smoke == "stress":
        return [("SMOKE_STRESS_N5_mm5", [by_cell["N5_mm5"][0]])]
    order = ["N3_mm3", "N4_mm3", "N4_mm4", "N5_mm3", "N5_mm4", "N5_mm5"]
    if selected_cells:
        unknown = set(selected_cells) - set(order)
        if unknown:
            raise ValueError(f"unknown cells: {sorted(unknown)}")
        order = [cell for cell in order if cell in selected_cells]
    return [(cell, by_cell[cell]) for cell in order]


def _receipt_is_verified(receipt_path: Path, cell_id: str) -> bool:
    if not receipt_path.is_file():
        return False
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    return receipt.get("status") == "REMOTE_VERIFIED" and receipt.get("cell_id") == cell_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--spool-root", type=Path, default=DEFAULT_SPOOL_ROOT)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--cells", nargs="+")
    parser.add_argument("--smoke", choices=["schema", "stress"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--remote-root",
        help="rclone専用root。例: pancake-drive:LLM_LPT/full_hidden_v1",
    )
    parser.add_argument("--rclone-binary", default="rclone")
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Drive転送せず、最初の完了cellで停止する",
    )
    parser.add_argument(
        "--delete-local-after-verify",
        action="store_true",
        help="remote完全性検証後だけcell local dataを削除する",
    )
    parser.add_argument("--cell-start-free-gb", type=float, default=550.0)
    parser.add_argument("--runtime-reserve-gb", type=float, default=200.0)
    args = parser.parse_args()
    if not args.dry_run and not args.local_only and not args.remote_root:
        parser.error("--remote-root is required unless --local-only is used")
    if args.delete_local_after_verify and not args.remote_root:
        parser.error("--delete-local-after-verify requires --remote-root")
    if args.remote_root:
        try:
            validate_remote_root(args.remote_root)
        except ValueError as exc:
            parser.error(str(exc))
    if args.cell_start_free_gb <= 0 or args.runtime_reserve_gb <= 0:
        parser.error("disk thresholds must be positive")
    return args


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    all_plans = build_trial_plan(config)
    execution = _select_execution_plans(all_plans, args.cells, args.smoke)
    print(f"dataset={config['dataset_id']} total_plan={len(all_plans)}")
    for cell_id, plans in execution:
        print(
            f"[PLAN] {cell_id}: trials={len(plans)} N={plans[0].N} "
            f"mm={plans[0].min_moves} sample_seeds="
            f"{plans[0].sample_seed}..{plans[-1].sample_seed}"
        )
    if args.dry_run:
        return

    dataset_root = args.spool_root / str(config["dataset_id"])
    cells_root = dataset_root / "cells"
    receipt_dir = dataset_root / "receipts"
    cells_root.mkdir(parents=True, exist_ok=True)
    receipt_dir.mkdir(parents=True, exist_ok=True)
    frozen_plan = plan_manifest(config, all_plans)
    plan_path = dataset_root / "DATASET_PLAN.json"
    if plan_path.is_file():
        existing = json.loads(plan_path.read_text(encoding="utf-8"))
        if canonical_json_bytes(existing) != canonical_json_bytes(frozen_plan):
            raise RuntimeError("existing DATASET_PLAN.json differs from current config")
    else:
        write_json(plan_path, frozen_plan)

    # 全cellがreceipt済みならGPU依存をloadせず終了できる。
    pending = []
    for cell_id, plans in execution:
        receipt_path = receipt_dir / f"{cell_id}_transfer_receipt.json"
        if _receipt_is_verified(receipt_path, cell_id) and not (cells_root / cell_id).exists():
            print(f"[SKIP REMOTE_VERIFIED] {cell_id}")
            continue
        pending.append((cell_id, plans))
    if not pending:
        return

    require_free_space(dataset_root, args.cell_start_free_gb, "before model load")
    model, tokenizer = run_local.load_model_and_tokenizer(config["model_id"], args.device)
    profile = run_local.resolve_model_profile(config["model_id"])
    transfer = RcloneDriveTransfer(rclone_binary=args.rclone_binary)

    for cell_id, plans in pending:
        require_free_space(dataset_root, args.cell_start_free_gb, f"start {cell_id}")
        cell_dir = cells_root / cell_id
        trials_dir = cell_dir / "trials"
        trials_dir.mkdir(parents=True, exist_ok=True)
        cell_plan = {
            "schema_version": 1,
            "cell_id": cell_id,
            "trial_count": len(plans),
            "trials": [
                {**asdict(plan), "initial_state": list(plan.initial_state)} for plan in plans
            ],
        }
        cell_plan_path = cell_dir / "CELL_PLAN.json"
        if cell_plan_path.is_file():
            existing = json.loads(cell_plan_path.read_text(encoding="utf-8"))
            if canonical_json_bytes(existing) != canonical_json_bytes(cell_plan):
                raise RuntimeError(f"existing CELL_PLAN differs: {cell_id}")
        else:
            write_json(cell_plan_path, cell_plan)

        for index, plan in enumerate(plans, start=1):
            require_free_space(
                dataset_root,
                args.runtime_reserve_gb,
                f"{cell_id} trial {index}/{len(plans)}",
            )
            print(f"[{cell_id} {index}/{len(plans)}] {plan.trial_id}")
            metadata = generate_trial(plan, config, model, tokenizer, profile, trials_dir)
            if args.smoke and not metadata["span_token_mapping_verified"]:
                raise RuntimeError(
                    f"smoke failed exact token-span mapping: {plan.trial_id}"
                )
            print(
                f"[LOCAL_VALIDATED] tokens={metadata['generated_token_count']} "
                f"done={metadata['done_reason']} elapsed={metadata['elapsed_sec']:.1f}s"
            )
        finalize_cell(cell_dir, plans)
        print(f"[LOCAL_COMPLETE] {cell_id}")

        if args.local_only:
            print("[STOP] local-only mode stops before the next cell")
            return
        try:
            transfer.upload_cell(cell_dir, args.remote_root, receipt_dir)
        except TransferError:
            print(f"[STOP] remote verification failed; local cell preserved: {cell_dir}")
            raise
        print(f"[REMOTE_VERIFIED] {cell_id}")
        if args.delete_local_after_verify:
            receipt_path = receipt_dir / f"{cell_id}_transfer_receipt.json"
            safe_delete_local_cell(cell_dir, cells_root, receipt_path)
            print(f"[LOCAL_PRUNED] {cell_id}")


if __name__ == "__main__":
    main()
