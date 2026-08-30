"""Pancake full-hidden dataset の不変 artifact と検証処理。"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from envs.pancake_env import PancakeSortingEnv

try:
    import h5py
except ImportError:  # CPU-only の plan/transfer テストでは不要。
    h5py = None  # type: ignore[assignment]


SCHEMA_VERSION = 1
MOVE_RE = re.compile(r"Flip\s+(\d+)", re.IGNORECASE)
THINK_RE = re.compile(r"</?think>", re.IGNORECASE)
FINAL_RE = re.compile(r"</?final>", re.IGNORECASE)


@dataclass(frozen=True)
class TrialPlan:
    """1 sampling trajectory の固定条件。"""

    dataset_id: str
    cell_id: str
    trial_id: str
    N: int
    min_moves: int
    state_index: int
    state_trial_index: int
    initial_state: tuple[int, ...]
    sample_seed: int


def canonical_json_bytes(value: Any) -> bytes:
    """決定的な JSON byte 列を返す。"""
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    """UTF-8 JSON を末尾改行付きで書く。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
        + b"\n"
    )


def sha256_file(path: Path, block_size: int = 8 * 1024 * 1024) -> str:
    """ファイルをstreamして SHA-256を計算する。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def md5_file(path: Path, block_size: int = 8 * 1024 * 1024) -> str:
    """Drive remote照合用のMD5をstream計算する。"""
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        while block := handle.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def hashes_file(path: Path, block_size: int = 8 * 1024 * 1024) -> tuple[str, str]:
    """大容量fileを1回だけ読み、SHA-256とMD5を同時計算する。"""
    sha256_digest = hashlib.sha256()
    md5_digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        while block := handle.read(block_size):
            sha256_digest.update(block)
            md5_digest.update(block)
    return sha256_digest.hexdigest(), md5_digest.hexdigest()


def build_trial_plan(config: dict[str, Any]) -> list[TrialPlan]:
    """cell configから600件の一意なtrial planを構築する。

    sample seed は固定plan順で1から600まで一意に割り当てる。stateごとの
    allocation上の反復番号は ``state_trial_index`` として別に保持する。

    Parameters
    ----------
    config:
        dataset config全体。

    Returns
    -------
    list[TrialPlan]
        config順のtrial plan。
    """
    dataset_id = str(config["dataset_id"])
    plans: list[TrialPlan] = []
    seen_ids: set[str] = set()
    global_sample_seed = 0
    for cell in config["cells"]:
        cell_id = str(cell["cell_id"])
        N = int(cell["N"])
        min_moves = int(cell["min_moves"])
        states = cell["states"]
        allocations = cell["trial_allocation"]
        if len(states) != len(allocations):
            raise ValueError(f"{cell_id}: states and trial_allocation lengths differ")
        if sum(int(count) for count in allocations) != 100:
            raise ValueError(f"{cell_id}: trial allocation must sum to 100")
        normalized_states = [tuple(int(item) for item in state) for state in states]
        if len(set(normalized_states)) != len(normalized_states):
            raise ValueError(f"{cell_id}: selected states must be unique")
        for state_index, (raw_state, count) in enumerate(
            zip(states, allocations, strict=True), start=1
        ):
            state = tuple(int(item) for item in raw_state)
            env = PancakeSortingEnv(N=N, initial_state=state)
            if env.min_moves != min_moves:
                raise ValueError(
                    f"{cell_id}: state {list(state)} has min_moves={env.min_moves}"
                )
            for state_trial_index in range(1, int(count) + 1):
                global_sample_seed += 1
                sample_seed = global_sample_seed
                trial_id = (
                    f"{cell_id}_state{state_index:02d}_"
                    f"trial{state_trial_index:03d}_seed{sample_seed:03d}"
                )
                if trial_id in seen_ids:
                    raise ValueError(f"duplicate trial_id: {trial_id}")
                seen_ids.add(trial_id)
                plans.append(
                    TrialPlan(
                        dataset_id=dataset_id,
                        cell_id=cell_id,
                        trial_id=trial_id,
                        N=N,
                        min_moves=min_moves,
                        state_index=state_index,
                        state_trial_index=state_trial_index,
                        initial_state=state,
                        sample_seed=sample_seed,
                    )
                )
    return plans


def plan_manifest(config: dict[str, Any], plans: Iterable[TrialPlan]) -> dict[str, Any]:
    """再現用のplan manifestを構築する。"""
    rows = []
    for plan in plans:
        row = asdict(plan)
        row["initial_state"] = list(plan.initial_state)
        rows.append(row)
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": config["dataset_id"],
        "selection_seed": config["selection_seed"],
        "config_sha256": hashlib.sha256(canonical_json_bytes(config)).hexdigest(),
        "trial_count": len(rows),
        "trials": rows,
    }


class HiddenH5Writer:
    """generated token hiddenをbounded CPU bufferでHDF5へ追記する。

    Parameters
    ----------
    path:
        書込み中の ``hidden.h5.partial`` path。
    num_layers:
        Transformer layer数。
    hidden_size:
        hidden dimension。
    buffer_tokens:
        HDF5へまとめてflushするtoken数。
    """

    def __init__(
        self,
        path: Path,
        num_layers: int,
        hidden_size: int,
        buffer_tokens: int = 64,
        compression: str = "gzip",
    ) -> None:
        if h5py is None:
            raise RuntimeError("HDF5保存にはh5pyが必要です")
        if buffer_tokens <= 0:
            raise ValueError("buffer_tokens must be positive")
        self.path = path
        self.buffer_tokens = buffer_tokens
        self._hidden_buffer: list[np.ndarray] = []
        self._token_buffer: list[int] = []
        self._position_buffer: list[int] = []
        self._closed = False
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file = h5py.File(path, "x")
        self._hidden = self._file.create_dataset(
            "hidden",
            shape=(0, num_layers, hidden_size),
            maxshape=(None, num_layers, hidden_size),
            chunks=(1, num_layers, hidden_size),
            dtype=np.float16,
            compression=compression,
            shuffle=True,
        )
        self._token_ids = self._file.create_dataset(
            "token_ids",
            shape=(0,),
            maxshape=(None,),
            chunks=(buffer_tokens,),
            dtype=np.int32,
            compression=compression,
        )
        self._positions = self._file.create_dataset(
            "token_positions",
            shape=(0,),
            maxshape=(None,),
            chunks=(buffer_tokens,),
            dtype=np.int32,
            compression=compression,
        )
        self._file.create_dataset(
            "layer_ids", data=np.arange(1, num_layers + 1, dtype=np.int32)
        )

    @property
    def rows_written(self) -> int:
        """flush済みとbuffer内を合わせた行数。"""
        return int(self._hidden.shape[0]) + len(self._hidden_buffer)

    def append(self, hidden: np.ndarray, token_id: int, token_position: int) -> None:
        """1 token分の ``[L,D]`` hiddenとtoken情報を追加する。"""
        expected = self._hidden.shape[1:]
        if hidden.shape != expected:
            raise ValueError(f"hidden shape {hidden.shape} != expected {expected}")
        if not np.isfinite(hidden).all():
            raise ValueError("hidden contains non-finite values")
        self._hidden_buffer.append(np.asarray(hidden, dtype=np.float16))
        self._token_buffer.append(int(token_id))
        self._position_buffer.append(int(token_position))
        if len(self._hidden_buffer) >= self.buffer_tokens:
            self.flush()

    def flush(self) -> None:
        """bufferをHDF5へ追記して解放する。"""
        if not self._hidden_buffer:
            return
        start = int(self._hidden.shape[0])
        end = start + len(self._hidden_buffer)
        self._hidden.resize(end, axis=0)
        self._token_ids.resize(end, axis=0)
        self._positions.resize(end, axis=0)
        self._hidden[start:end] = np.stack(self._hidden_buffer, axis=0)
        self._token_ids[start:end] = np.asarray(self._token_buffer, dtype=np.int32)
        self._positions[start:end] = np.asarray(self._position_buffer, dtype=np.int32)
        self._hidden_buffer.clear()
        self._token_buffer.clear()
        self._position_buffer.clear()
        self._file.flush()

    def finalize(self, metadata: dict[str, Any]) -> Path:
        """flush・close後、``.partial``をatomic renameする。"""
        self.flush()
        self._file.attrs["schema_version"] = SCHEMA_VERSION
        self._file.attrs["metadata_json"] = json.dumps(
            metadata, ensure_ascii=False, sort_keys=True
        )
        self._file.flush()
        self._file.close()
        self._closed = True
        if self.path.suffix != ".partial":
            raise ValueError("writer path must end with .partial")
        final_path = self.path.with_suffix("")
        os.replace(self.path, final_path)
        return final_path

    def close_incomplete(self) -> None:
        """例外時にpartialを残したままhandleだけ閉じる。"""
        if not self._closed:
            self._file.close()
            self._closed = True


def _tag_spans(text: str, pattern: re.Pattern[str], name: str) -> list[dict[str, Any]]:
    return [
        {
            "kind": name,
            "text": match.group(0),
            "char_span": [match.start(), match.end()],
        }
        for match in pattern.finditer(text)
    ]


def map_char_spans_to_tokens(
    text: str,
    generated_ids: list[int],
    tokenizer: Any,
    spans: list[dict[str, Any]],
) -> dict[str, Any]:
    """retokenize照合済みoffset mappingでchar spanをtoken spanへ写す。

    tokenizerがfast offsetを提供しない、またはtoken ID列が一致しない場合は
    token spanを推測せず ``mapping_verified=false`` とする。char spanとtoken ID列は
    保存済みなので、tokenizer更新後にも再処理できる。
    """
    try:
        encoded = tokenizer(
            text,
            add_special_tokens=False,
            return_offsets_mapping=True,
        )
        token_ids = encoded["input_ids"]
        if token_ids and isinstance(token_ids[0], list):
            token_ids = token_ids[0]
        offsets = encoded["offset_mapping"]
        if offsets and isinstance(offsets[0], list) and offsets[0] and isinstance(offsets[0][0], list):
            offsets = offsets[0]
        verified = [int(item) for item in token_ids] == [int(item) for item in generated_ids]
        if not verified:
            return {
                "mapping_verified": False,
                "method": "retokenize_offsets",
                "reason": "retokenized token IDs differ from generated token IDs",
                "spans": spans,
            }
        mapped = []
        for span in spans:
            char_start, char_end = span["char_span"]
            overlaps = [
                index
                for index, (start, end) in enumerate(offsets)
                if end > char_start and start < char_end
            ]
            item = dict(span)
            item["token_span"] = (
                [overlaps[0], overlaps[-1] + 1] if overlaps else None
            )
            mapped.append(item)
        return {
            "mapping_verified": True,
            "method": "retokenize_offsets",
            "spans": mapped,
        }
    except Exception as exc:
        return {
            "mapping_verified": False,
            "method": "retokenize_offsets",
            "reason": f"{type(exc).__name__}: {exc}",
            "spans": spans,
        }


def build_span_artifact(text: str, generated_ids: list[int], tokenizer: Any) -> dict[str, Any]:
    """Move/think/finalのexact char spanと検証可能なtoken spanを作る。"""
    spans = _tag_spans(text, THINK_RE, "think_tag")
    spans.extend(_tag_spans(text, FINAL_RE, "final_tag"))
    spans.extend(
        {
            "kind": "move_mention",
            "text": match.group(0),
            "parsed_k": int(match.group(1)),
            "char_span": [match.start(), match.end()],
        }
        for match in MOVE_RE.finditer(text)
    )
    spans.sort(key=lambda item: (item["char_span"][0], item["char_span"][1]))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "generated_token_count": len(generated_ids),
        **map_char_spans_to_tokens(text, generated_ids, tokenizer, spans),
    }


def _final_region(text: str) -> tuple[int, int] | None:
    closed = list(PancakeSortingEnv.FINAL_BLOCK_RE.finditer(text))
    if closed:
        match = closed[-1]
        return match.start(1), match.end(1)
    opened = list(PancakeSortingEnv.FINAL_OPEN_RE.finditer(text))
    if opened:
        return opened[-1].end(), len(text)
    return None


def _replay_mentions(
    env: PancakeSortingEnv,
    mentions: Iterable[re.Match[str]],
) -> dict[str, Any]:
    state = env.initial_state
    seen = {state}
    rows = []
    first_goal_index = None
    for index, match in enumerate(mentions, start=1):
        k = int(match.group(1))
        legal = 2 <= k <= env.N
        before = state
        before_distance = env.distance_to_goal(before)
        state = env.apply_move(state, match.group(0))
        after_distance = env.distance_to_goal(state)
        repeated = state in seen
        seen.add(state)
        goal = state == env.goal_state
        if goal and first_goal_index is None:
            first_goal_index = index
        rows.append(
            {
                "mention_index": index,
                "raw_text": match.group(0),
                "parsed_k": k,
                "char_span": [match.start(), match.end()],
                "legal": legal,
                "state_before": list(before),
                "state_after": list(state),
                "distance_before": before_distance,
                "distance_after": after_distance,
                "delta_distance": after_distance - before_distance,
                "goal_reached": goal,
                "repeated_state": repeated,
            }
        )
    return {
        "mentions": rows,
        "first_goal_index": first_goal_index,
        "goal_reached": any(row["goal_reached"] for row in rows),
        "final_state": list(state),
        "final_distance": env.distance_to_goal(state),
    }


def build_debug_replay(
    env: PancakeSortingEnv,
    generated_text: str,
    done_reason: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """reasoning mention軌道とfinal提出軌道を分離して再生する。"""
    all_matches = list(MOVE_RE.finditer(generated_text))
    final_region = _final_region(generated_text)
    final_matches = []
    reasoning_matches = all_matches
    if final_region is not None:
        start, end = final_region
        final_matches = [
            match for match in all_matches if start <= match.start() and match.end() <= end
        ]
        reasoning_matches = [
            match for match in all_matches if not (start <= match.start() and match.end() <= end)
        ]
    all_replay = _replay_mentions(env, all_matches)
    reasoning_replay = _replay_mentions(env, reasoning_matches)
    final_replay = _replay_mentions(env, final_matches)
    replay = {
        "schema_version": SCHEMA_VERSION,
        "initial_state": list(env.initial_state),
        "goal_state": list(env.goal_state),
        "min_moves": env.min_moves,
        "done_reason": done_reason,
        "final_region_char_span": list(final_region) if final_region else None,
        "reasoning_mentions_replay": reasoning_replay,
        "all_mentions_replay": all_replay,
        "final_submission_replay": final_replay,
    }

    has_final = final_region is not None
    success_final = final_replay["goal_reached"]
    search_goal = all_replay["goal_reached"]
    if success_final:
        outcome = "success_final"
    elif done_reason == "length":
        outcome = "length_censored"
    elif not has_final:
        outcome = "no_final"
    elif search_goal:
        outcome = "search_success_final_fail"
    else:
        outcome = "search_fail"
    all_rows = all_replay["mentions"]
    labels = {
        "schema_version": 1,
        "label_schema_version": 1,
        "outcome": outcome,
        "observable_flags": {
            "illegal_action": any(not row["legal"] for row in all_rows),
            "repeated_state": any(row["repeated_state"] for row in all_rows),
            "false_goal_claim": False,
            "format_error": not has_final,
            "length_censored": done_reason == "length",
            "search_reached_goal": search_goal,
            "final_reached_goal": success_final,
        },
        "inferred_causes": [],
        "annotation_status": "rule_labels_only",
    }
    return replay, labels


def validate_h5(
    path: Path,
    expected_rows: int,
    num_layers: int,
    hidden_size: int,
    *,
    check_finite: bool = True,
) -> dict[str, Any]:
    """HDF5 schema・shape・finite値をchunk単位で検証する。"""
    if h5py is None:
        raise RuntimeError("HDF5検証にはh5pyが必要です")
    if not path.is_file() or path.suffix == ".partial":
        raise ValueError(f"finalized HDF5 not found: {path}")
    with h5py.File(path, "r") as handle:
        required = {"hidden", "token_ids", "token_positions", "layer_ids"}
        if not required <= set(handle.keys()):
            raise ValueError(f"missing HDF5 datasets: {sorted(required - set(handle.keys()))}")
        expected_shape = (expected_rows, num_layers, hidden_size)
        if tuple(handle["hidden"].shape) != expected_shape:
            raise ValueError(
                f"hidden shape {tuple(handle['hidden'].shape)} != {expected_shape}"
            )
        if tuple(handle["token_ids"].shape) != (expected_rows,):
            raise ValueError("token_ids length differs from hidden rows")
        positions = handle["token_positions"][:]
        if not np.array_equal(positions, np.arange(expected_rows, dtype=np.int32)):
            raise ValueError("generated token_positions must be contiguous from zero")
        layer_ids = handle["layer_ids"][:]
        if not np.array_equal(layer_ids, np.arange(1, num_layers + 1, dtype=np.int32)):
            raise ValueError("layer_ids mismatch")
        if check_finite:
            chunk_rows = 64
            for start in range(0, expected_rows, chunk_rows):
                if not np.isfinite(handle["hidden"][start:start + chunk_rows]).all():
                    raise ValueError(f"hidden contains non-finite values at row {start}")
    return {
        "hidden_shape": [expected_rows, num_layers, hidden_size],
        "finite": True,
        "token_alignment": True,
        "layer_ids": [1, num_layers],
    }


def validate_trial_dir(
    trial_dir: Path,
    expected_trial_id: str | None = None,
    *,
    allow_partial: bool = False,
    check_hidden_values: bool = True,
) -> dict[str, Any]:
    """finalized trialの最低限artifactと相互整合性を検証する。"""
    if trial_dir.name.endswith(".partial") and not allow_partial:
        raise ValueError("partial trial cannot be validated")
    required = [
        "raw/prompt.txt",
        "raw/formatted_prompt.txt",
        "raw/generated.txt",
        "raw/generated_token_ids.npy",
        "raw/spans_v1.json",
        "raw/metadata.json",
        "hidden/hidden.h5",
        "debug/replay_v1.json",
        "labels/labels_v1.json",
        "checksums.json",
        "checksums.sha256",
        "checksums.md5",
        "COMPLETE.json",
    ]
    missing = [item for item in required if not (trial_dir / item).is_file()]
    if missing:
        raise ValueError(f"missing trial artifacts: {missing}")
    metadata = json.loads((trial_dir / "raw/metadata.json").read_text(encoding="utf-8"))
    complete = json.loads((trial_dir / "COMPLETE.json").read_text(encoding="utf-8"))
    if expected_trial_id is not None and metadata.get("trial_id") != expected_trial_id:
        raise ValueError("trial_id mismatch")
    if complete.get("trial_id") != metadata.get("trial_id"):
        raise ValueError("COMPLETE trial_id mismatch")
    generated = (trial_dir / "raw/generated.txt").read_text(encoding="utf-8")
    if hashlib.sha256(generated.encode("utf-8")).hexdigest() != metadata.get(
        "generated_text_sha256"
    ):
        raise ValueError("generated text checksum mismatch")
    token_ids = np.load(trial_dir / "raw/generated_token_ids.npy", allow_pickle=False)
    if len(token_ids) != int(metadata["generated_token_count"]):
        raise ValueError("generated token count mismatch")
    h5_check = validate_h5(
        trial_dir / "hidden/hidden.h5",
        expected_rows=len(token_ids),
        num_layers=int(metadata["num_layers"]),
        hidden_size=int(metadata["hidden_size"]),
        check_finite=check_hidden_values,
    )
    checksums = json.loads((trial_dir / "checksums.json").read_text(encoding="utf-8"))
    for item in checksums["files"]:
        path = trial_dir / item["path"]
        if path.stat().st_size != int(item["size"]):
            raise ValueError(f"size mismatch: {item['path']}")
        if sha256_file(path) != item["sha256"]:
            raise ValueError(f"SHA-256 mismatch: {item['path']}")
    return {"trial_id": metadata["trial_id"], "h5": h5_check}


def write_trial_checksums(trial_dir: Path) -> dict[str, Any]:
    """COMPLETE/checksum自身を除く不変artifactのhash一覧を書く。"""
    excluded = {"checksums.json", "checksums.sha256", "checksums.md5", "COMPLETE.json"}
    files = []
    for path in sorted(item for item in trial_dir.rglob("*") if item.is_file()):
        relative = path.relative_to(trial_dir).as_posix()
        if relative in excluded or relative.endswith(".partial"):
            continue
        sha256, md5 = hashes_file(path)
        files.append(
            {
                "path": relative,
                "size": path.stat().st_size,
                "sha256": sha256,
                "md5": md5,
            }
        )
    payload = {"schema_version": SCHEMA_VERSION, "files": files}
    write_json(trial_dir / "checksums.json", payload)
    (trial_dir / "checksums.sha256").write_text(
        "".join(f"{item['sha256']}  {item['path']}\n" for item in files),
        encoding="utf-8",
    )
    (trial_dir / "checksums.md5").write_text(
        "".join(f"{item['md5']}  {item['path']}\n" for item in files),
        encoding="utf-8",
    )
    return payload
