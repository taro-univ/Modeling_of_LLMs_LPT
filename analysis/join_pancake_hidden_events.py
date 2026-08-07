"""Join Pancake summary rows with token-level hidden capture metadata."""

from __future__ import annotations

import argparse
import ast
import bisect
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis.analyze_pancake_debug import outcome_label
from envs.pancake_env import PancakeSortingEnv


SCHEMA_VERSION = 1
JOIN_FIELDS = (
    "puzzle",
    "N",
    "temperature",
    "num_predict",
    "trial",
    "model_id",
    "instance_id",
    "initial_state",
    "min_moves",
)
NPZ_KEYS = (
    "hidden",
    "token_ids",
    "token_positions",
    "token_source",
    "is_think_token",
    "layer_ids",
    "generated_text",
    "move_steps",
    "move_texts",
    "capture_meta",
)
TRIAL_RE = re.compile(r"trial_(\d+)", re.IGNORECASE)
FINAL_BLOCK_RE = re.compile(r"<final>.*?</final>", re.IGNORECASE | re.DOTALL)


def _json_scalar(array: np.ndarray, key: str) -> Any:
    if array.size != 1:
        raise ValueError(f"{key} must be a scalar, got shape {array.shape}")
    return array.item()


def _parse_state(value: Any) -> tuple[int, ...]:
    if isinstance(value, str):
        try:
            value = ast.literal_eval(value)
        except (SyntaxError, ValueError) as exc:
            raise ValueError(f"invalid initial_state: {value!r}") from exc
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"initial_state must be a list or tuple, got {value!r}")
    return tuple(int(item) for item in value)


def _normalise_join_value(field: str, value: Any) -> Any:
    if field in {"N", "num_predict", "trial", "min_moves"}:
        return int(value)
    if field == "temperature":
        return float(value)
    if field == "initial_state":
        return _parse_state(value)
    if field == "puzzle":
        return str(value).lower()
    return value


def _join_values_equal(field: str, left: Any, right: Any) -> bool:
    left = _normalise_join_value(field, left)
    right = _normalise_join_value(field, right)
    if field == "temperature":
        return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-12)
    return left == right


def _read_summary(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("results", data.get("trials"))
    if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
        raise ValueError(f"{path} must contain a list of trial objects")
    return data


def _trial_from_filename(path: Path) -> int | None:
    match = TRIAL_RE.search(path.name)
    return int(match.group(1)) if match else None


def _load_capture_meta(path: Path) -> dict[str, Any]:
    with np.load(path, allow_pickle=False) as data:
        if "capture_meta" not in data:
            raise ValueError(f"{path}: missing NPZ key capture_meta")
        value = _json_scalar(data["capture_meta"], "capture_meta")
    try:
        meta = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: capture_meta is not valid JSON") from exc
    if not isinstance(meta, dict):
        raise ValueError(f"{path}: capture_meta must decode to an object")
    return meta


def _index_hidden_files(
    run_dir: Path, hidden_glob: str
) -> tuple[dict[int, tuple[Path, dict[str, Any], list[str], bool]], list[str]]:
    indexed: dict[int, tuple[Path, dict[str, Any], list[str], bool]] = {}
    skipped: list[str] = []
    for path in sorted(run_dir.glob(hidden_glob)):
        meta = _load_capture_meta(path)
        meta_trial = meta.get("trial")
        file_trial = _trial_from_filename(path)
        warnings: list[str] = []
        join_ok = True

        if meta_trial is None and file_trial is None:
            skipped.append(f"{path}: trial is absent from capture_meta and filename")
            continue
        trial = int(meta_trial if meta_trial is not None else file_trial)
        if meta_trial is None:
            warnings.append(f"trial {trial} inferred from hidden filename")
        if file_trial is None:
            warnings.append(f"trial {trial} available only in capture_meta")
        elif meta_trial is not None and int(meta_trial) != file_trial:
            join_ok = False
            warnings.append(
                f"trial mismatch: capture_meta={int(meta_trial)}, filename={file_trial}"
            )
        if trial in indexed:
            raise ValueError(
                f"multiple hidden files resolve to trial {trial}: "
                f"{indexed[trial][0]} and {path}"
            )
        indexed[trial] = (path, meta, warnings, join_ok)
    return indexed, skipped


def _validate_join(
    summary: dict[str, Any],
    meta: dict[str, Any],
    initial_warnings: list[str],
    initial_ok: bool,
) -> tuple[bool, list[str]]:
    warnings = list(initial_warnings)
    join_ok = initial_ok
    for field in JOIN_FIELDS:
        summary_value = summary.get(field)
        meta_value = meta.get(field)
        if summary_value is None or meta_value is None:
            missing = []
            if summary_value is None:
                missing.append("summary")
            if meta_value is None:
                missing.append("capture_meta")
            warnings.append(f"join field {field!r} missing from {' and '.join(missing)}")
            continue
        try:
            equal = _join_values_equal(field, summary_value, meta_value)
        except (TypeError, ValueError) as exc:
            equal = False
            warnings.append(f"join field {field!r} could not be compared: {exc}")
        if not equal:
            join_ok = False
            warnings.append(
                f"join field {field!r} mismatch: "
                f"summary={summary_value!r}, capture_meta={meta_value!r}"
            )
    return join_ok, warnings


def _require_vector(name: str, value: np.ndarray, length: int) -> np.ndarray:
    if value.ndim != 1 or len(value) != length:
        raise ValueError(
            f"{name} must have shape ({length},), got {value.shape}"
        )
    return value


def _map_generated_step(
    generated_step: int,
    prompt_token_count: int,
    token_positions: list[int],
    token_source: list[str],
) -> tuple[int | None, int, bool]:
    target = prompt_token_count + generated_step
    row = bisect.bisect_left(token_positions, target)
    while row < len(token_positions) and token_source[row] != "generated":
        row += 1
    if row == len(token_positions):
        return None, target, False
    return row, target, token_positions[row] == target


def _map_boundary_step(
    generated_step: int,
    prompt_token_count: int,
    token_positions: list[int],
    token_source: list[str],
    *,
    at_or_after: bool,
) -> tuple[int | None, int]:
    target = prompt_token_count + generated_step
    if at_or_after:
        row = bisect.bisect_left(token_positions, target)
        while row < len(token_positions) and token_source[row] != "generated":
            row += 1
        return (None if row == len(token_positions) else row), target

    row = bisect.bisect_right(token_positions, target) - 1
    while row >= 0 and token_source[row] != "generated":
        row -= 1
    return (None if row < 0 else row), target


def _estimate_final_boundaries(
    generated_text: str,
    generated_token_count: int | None,
    prompt_token_count: int,
    token_positions: list[int],
    token_source: list[str],
    warnings: list[str],
) -> tuple[bool, int | None, int | None, list[dict[str, Any]]]:
    matches = list(FINAL_BLOCK_RE.finditer(generated_text))
    if not matches:
        warnings.append(
            "final boundary unavailable: no complete <final>...</final> block"
        )
        return False, None, None, []
    if not generated_text or not generated_token_count:
        warnings.append(
            "final boundary unavailable: generated token count is missing"
        )
        return False, None, None, []

    match = matches[-1]
    count = int(generated_token_count)
    start_step = min(count - 1, int(match.start() * count / len(generated_text)))
    end_step = min(
        count - 1,
        max(start_step, math.ceil(match.end() * count / len(generated_text)) - 1),
    )
    start_row, start_position = _map_boundary_step(
        start_step,
        prompt_token_count,
        token_positions,
        token_source,
        at_or_after=True,
    )
    end_row, end_position = _map_boundary_step(
        end_step,
        prompt_token_count,
        token_positions,
        token_source,
        at_or_after=False,
    )
    if start_row is None or end_row is None or end_row < start_row:
        warnings.append(
            "final boundary unavailable: estimated tag range does not contain "
            "a captured generated row"
        )
        return False, None, None, []

    warnings.append(
        "final boundaries use proportional character-to-token estimates and "
        "enclosing captured generated rows"
    )
    events = [
        {
            "name": "final_start",
            "t_row": start_row,
            "token_position": token_positions[start_row],
            "estimated_token_position": start_position,
            "char_position": match.start(),
        },
        {
            "name": "final_end",
            "t_row": end_row,
            "token_position": token_positions[end_row],
            "estimated_token_position": end_position,
            "char_position": match.end(),
        },
    ]
    return True, start_row, end_row, events


def _trajectory_analysis(
    env: PancakeSortingEnv,
    move_texts: list[str],
    move_rows: list[int | None],
    token_positions: list[int],
    row_count: int,
    warnings: list[str],
) -> tuple[
    list[dict[str, Any]],
    list[int],
    list[int],
    list[float],
    list[Any],
    list[bool],
]:
    state = env.initial_state
    distance = env.distance_to_goal(state)
    events: list[dict[str, Any]] = []
    states_after: list[tuple[int, ...]] = []
    first_goal_move: int | None = None

    for move_index, (move, row) in enumerate(zip(move_texts, move_rows)):
        state_before = state
        distance_before = distance
        state = env.apply_move(state, move)
        distance = env.distance_to_goal(state)
        states_after.append(state)
        if state == env.goal_state and first_goal_move is None:
            first_goal_move = move_index
        events.append(
            {
                "name": "move_mention",
                "t_row": row,
                "token_position": None if row is None else token_positions[row],
                "move_index": move_index,
                "move": move,
                "state_before": list(state_before),
                "state_after": list(state),
                "distance_before": distance_before,
                "distance_after": distance,
                "delta_distance": distance - distance_before,
            }
        )

    events_by_row: dict[int, list[int]] = {}
    for move_index, row in enumerate(move_rows):
        if row is not None:
            events_by_row.setdefault(row, []).append(move_index)

    state = env.initial_state
    applied_count = 0
    state_index: list[int] = []
    distances: list[int] = []
    values: list[float] = []
    row_move_index: list[Any] = [None] * row_count
    after_first_goal: list[bool] = []
    goal_seen = False

    for row in range(row_count):
        indices = events_by_row.get(row, [])
        if indices:
            if len(indices) > 1:
                warnings.append(
                    f"multiple move events {indices} map to token row {row}; "
                    "move_index records the last event"
                )
            latest = indices[-1]
            state = states_after[latest]
            applied_count = latest + 1
            row_move_index[row] = latest
            if first_goal_move is not None and latest >= first_goal_move:
                goal_seen = True
        current_distance = env.distance_to_goal(state)
        state_index.append(applied_count)
        distances.append(current_distance)
        values.append(round(current_distance / env.min_moves, 6))
        after_first_goal.append(goal_seen)

    if first_goal_move is not None:
        first_goal_row = move_rows[first_goal_move]
        events.append(
            {
                "name": "first_goal",
                "t_row": first_goal_row,
                "token_position": (
                    None
                    if first_goal_row is None
                    else token_positions[first_goal_row]
                ),
                "move_index": first_goal_move,
            }
        )
    return (
        events,
        state_index,
        distances,
        values,
        row_move_index,
        after_first_goal,
    )


def _classify_outcome(
    summary: dict[str, Any],
    env: PancakeSortingEnv | None,
    generated_text: str,
    move_texts: list[str],
    loop_threshold: float,
) -> str:
    data = dict(summary)
    if env is not None:
        data.setdefault("moves_all_mentions", move_texts)
        data.setdefault("moves_final", env.extract_final_moves_from_text(generated_text))
        data.setdefault(
            "goal_reached_all_mentions", env.goal_reached(move_texts)
        )
        if "repeated_state_count" not in data:
            state = env.initial_state
            seen = {state}
            repeated = 0
            for move in move_texts:
                state = env.apply_move(state, move)
                repeated += int(state in seen)
                seen.add(state)
            data["repeated_state_count"] = repeated
    data.setdefault("done_reason", data.get("early_stop"))
    data.setdefault("final_accuracy", data.get("accuracy", 0))
    return outcome_label(data, loop_threshold)


def _problem(
    summary: dict[str, Any], meta: dict[str, Any], env: PancakeSortingEnv | None
) -> dict[str, Any]:
    def value(key: str) -> Any:
        result = summary.get(key, meta.get(key))
        if key == "initial_state" and result is not None:
            return list(_parse_state(result))
        return result

    return {
        "puzzle": value("puzzle") or "pancake",
        "trial": value("trial"),
        "N": value("N"),
        "temperature": value("temperature"),
        "num_predict": value("num_predict"),
        "model_id": value("model_id"),
        "instance_id": value("instance_id"),
        "instance_seed": value("instance_seed"),
        "sample_seed": value("sample_seed"),
        "initial_state": value("initial_state"),
        "goal_state": list(env.goal_state) if env is not None else value("goal_state"),
        "min_moves": value("min_moves"),
    }


def join_trial(
    summary: dict[str, Any],
    summary_path: Path,
    hidden_path: Path,
    meta: dict[str, Any],
    initial_warnings: list[str],
    initial_join_ok: bool,
    loop_threshold: float,
) -> dict[str, Any]:
    join_ok, warnings = _validate_join(
        summary, meta, initial_warnings, initial_join_ok
    )
    with np.load(hidden_path, allow_pickle=False) as data:
        missing = [key for key in NPZ_KEYS if key not in data]
        if missing:
            raise ValueError(f"{hidden_path}: missing NPZ keys: {', '.join(missing)}")
        hidden_shape_value = meta.get("hidden_shape")
        if (
            isinstance(hidden_shape_value, list)
            and len(hidden_shape_value) == 3
            and all(isinstance(size, int) for size in hidden_shape_value)
        ):
            hidden_shape = list(hidden_shape_value)
        else:
            hidden_shape = list(data["hidden"].shape)
            warnings.append(
                "capture_meta.hidden_shape is unavailable; loaded hidden to "
                "determine its shape"
            )
        if len(hidden_shape) != 3:
            raise ValueError(
                f"{hidden_path}: hidden must have shape [T, L, D], "
                f"got {hidden_shape}"
            )
        row_count = hidden_shape[0]
        token_ids = _require_vector("token_ids", data["token_ids"], row_count)
        token_positions_array = _require_vector(
            "token_positions", data["token_positions"], row_count
        )
        token_source_array = _require_vector(
            "token_source", data["token_source"], row_count
        )
        think_array = _require_vector(
            "is_think_token", data["is_think_token"], row_count
        )
        layer_ids = data["layer_ids"]
        if layer_ids.ndim != 1 or len(layer_ids) != hidden_shape[1]:
            raise ValueError(
                f"layer_ids must have shape ({hidden_shape[1]},), "
                f"got {layer_ids.shape}"
            )
        generated_text = str(_json_scalar(data["generated_text"], "generated_text"))
        move_steps_array = data["move_steps"]
        move_texts_array = data["move_texts"]
        if (
            move_steps_array.ndim != 1
            or move_texts_array.ndim != 1
            or len(move_steps_array) != len(move_texts_array)
        ):
            raise ValueError("move_steps and move_texts must be equal-length vectors")

        token_ids_list = [int(value) for value in token_ids.tolist()]
        token_positions = [int(value) for value in token_positions_array.tolist()]
        token_source = [str(value) for value in token_source_array.tolist()]
        is_think = [bool(value) for value in think_array.tolist()]
        layer_ids_list = [int(value) for value in layer_ids.tolist()]
        move_steps = [int(value) for value in move_steps_array.tolist()]
        move_texts = [str(value) for value in move_texts_array.tolist()]

    if token_positions != sorted(token_positions):
        raise ValueError(f"{hidden_path}: token_positions must be nondecreasing")
    invalid_sources = sorted(set(token_source) - {"prompt", "generated"})
    if invalid_sources:
        raise ValueError(f"{hidden_path}: invalid token_source values {invalid_sources}")

    initial_value = summary.get("initial_state", meta.get("initial_state"))
    n_value = summary.get("N", meta.get("N"))
    if initial_value is None or n_value is None:
        raise ValueError("N and initial_state are required to build the state trace")
    env = PancakeSortingEnv(N=int(n_value), initial_state=_parse_state(initial_value))

    prompt_token_count_value = meta.get("prompt_token_count")
    if prompt_token_count_value is None:
        generated_positions = [
            position
            for position, source in zip(token_positions, token_source)
            if source == "generated"
        ]
        if not generated_positions:
            raise ValueError("prompt_token_count is missing and cannot be inferred")
        prompt_token_count = min(generated_positions)
        warnings.append(
            f"prompt_token_count inferred as {prompt_token_count} from token positions"
        )
    else:
        prompt_token_count = int(prompt_token_count_value)

    move_rows: list[int | None] = []
    for move_index, step in enumerate(move_steps):
        row, target, exact = _map_generated_step(
            step, prompt_token_count, token_positions, token_source
        )
        move_rows.append(row)
        if row is None:
            warnings.append(
                f"move {move_index} at generated step {step} "
                f"(token position {target}) has no captured row at or after it"
            )
        elif not exact:
            warnings.append(
                f"move {move_index} at token position {target} mapped to next "
                f"captured row {row} at token position {token_positions[row]}"
            )

    (
        move_events,
        state_index,
        distances,
        values,
        row_move_index,
        after_first_goal,
    ) = _trajectory_analysis(
        env, move_texts, move_rows, token_positions, row_count, warnings
    )

    generated_token_count = meta.get(
        "generated_token_count", summary.get("total_tokens")
    )
    boundary_ok, final_start, final_end, boundary_events = (
        _estimate_final_boundaries(
            generated_text,
            (
                None
                if generated_token_count is None
                else int(generated_token_count)
            ),
            prompt_token_count,
            token_positions,
            token_source,
            warnings,
        )
    )

    is_prompt = [source == "prompt" for source in token_source]
    is_generated = [source == "generated" for source in token_source]
    is_move_event = [False] * row_count
    for row in move_rows:
        if row is not None:
            is_move_event[row] = True
    is_final_region = [False] * row_count
    is_after_final_start = [False] * row_count
    if boundary_ok and final_start is not None and final_end is not None:
        for row in range(final_start, min(row_count, final_end + 1)):
            is_final_region[row] = True
        for row in range(final_start, row_count):
            is_after_final_start[row] = True

    phase_label = []
    for row in range(row_count):
        if is_prompt[row]:
            phase = "prompt"
        elif is_final_region[row]:
            phase = "final"
        elif after_first_goal[row]:
            phase = "post_goal"
        elif is_think[row]:
            phase = "think"
        else:
            phase = "search"
        phase_label.append(phase)

    dt_token: list[int | None] = [
        token_positions[index + 1] - token_positions[index]
        for index in range(max(0, row_count - 1))
    ]
    if row_count:
        dt_token.append(None)

    return {
        "schema_version": SCHEMA_VERSION,
        "join_ok": join_ok,
        "join_warnings": warnings,
        "boundary_ok": boundary_ok,
        "summary_json": str(summary_path.resolve()),
        "hidden_npz": str(hidden_path.resolve()),
        "trajectory_ref": {
            "hidden_key": "hidden",
            "shape": hidden_shape,
            "layer_ids": layer_ids_list,
        },
        "problem": _problem(summary, meta, env),
        "outcome_label": _classify_outcome(
            summary, env, generated_text, move_texts, loop_threshold
        ),
        "token_series": {
            "t_row": list(range(row_count)),
            "token_position": token_positions,
            "dt_token": dt_token,
            "token_source": token_source,
            "token_id": token_ids_list,
            "flags": {
                "is_prompt": is_prompt,
                "is_generated": is_generated,
                "is_think_token": is_think,
                "is_move_event": is_move_event,
                "is_final_region": is_final_region,
                "is_after_final_start": is_after_final_start,
                "is_after_first_goal": after_first_goal,
            },
            "move_index": row_move_index,
            "state_index": state_index,
            "distance_to_goal": distances,
            "v": values,
            "phase_label": phase_label,
        },
        "events": move_events + boundary_events,
    }


def _missing_hidden_result(
    summary: dict[str, Any],
    summary_path: Path,
    loop_threshold: float,
) -> dict[str, Any]:
    empty_flags = {
        "is_prompt": [],
        "is_generated": [],
        "is_think_token": [],
        "is_move_event": [],
        "is_final_region": [],
        "is_after_final_start": [],
        "is_after_first_goal": [],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "join_ok": False,
        "join_warnings": ["no hidden NPZ matched this summary trial"],
        "boundary_ok": False,
        "summary_json": str(summary_path.resolve()),
        "hidden_npz": None,
        "trajectory_ref": None,
        "problem": _problem(summary, {}, None),
        "outcome_label": _classify_outcome(
            summary, None, "", [], loop_threshold
        ),
        "token_series": {
            "t_row": [],
            "token_position": [],
            "dt_token": [],
            "token_source": [],
            "token_id": [],
            "flags": empty_flags,
            "move_index": [],
            "state_index": [],
            "distance_to_goal": [],
            "v": [],
            "phase_label": [],
        },
        "events": [],
    }


def join_run(
    run_dir: Path,
    out_dir: Path,
    hidden_glob: str = "hidden/*.npz",
    loop_threshold: float = 0.3,
) -> list[Path]:
    run_dir = Path(run_dir)
    summary_path = run_dir / "summary.json"
    if not summary_path.is_file():
        raise FileNotFoundError(f"summary.json not found in {run_dir}")
    summaries = _read_summary(summary_path)
    hidden_by_trial, skipped = _index_hidden_files(run_dir, hidden_glob)
    for warning in skipped:
        print(f"warning: {warning}", file=sys.stderr)

    rows_by_trial: dict[int, dict[str, Any]] = {}
    for row in summaries:
        if row.get("trial") is None:
            raise ValueError("every summary row must contain trial")
        trial = int(row["trial"])
        if trial in rows_by_trial:
            raise ValueError(f"duplicate summary trial {trial}")
        rows_by_trial[trial] = row

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for trial, summary in sorted(rows_by_trial.items()):
        hidden_entry = hidden_by_trial.pop(trial, None)
        if hidden_entry is None:
            result = _missing_hidden_result(
                summary, summary_path, loop_threshold
            )
        else:
            hidden_path, meta, warnings, join_ok = hidden_entry
            result = join_trial(
                summary,
                summary_path,
                hidden_path,
                meta,
                warnings,
                join_ok,
                loop_threshold,
            )
        output_path = out_dir / f"trial_{trial:03d}_events.json"
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        written.append(output_path)

    for trial, (path, _meta, _warnings, _join_ok) in sorted(hidden_by_trial.items()):
        print(
            f"warning: hidden trial {trial} has no summary row: {path}",
            file=sys.stderr,
        )
    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--hidden-glob", default="hidden/*.npz")
    parser.add_argument("--loop-threshold", type=float, default=0.3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    written = join_run(
        args.run_dir,
        args.out_dir,
        hidden_glob=args.hidden_glob,
        loop_threshold=args.loop_threshold,
    )
    for path in written:
        print(path)


if __name__ == "__main__":
    main()
