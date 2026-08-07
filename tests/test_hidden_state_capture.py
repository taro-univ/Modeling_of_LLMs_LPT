import json

import numpy as np
import pytest

from runners.run_local import (
    CaptureTiming,
    GenerationResult,
    make_capture_layers,
    parse_capture_timing,
    save_hidden_npz,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("move", CaptureTiming(mode="move", stride=None)),
        ("token", CaptureTiming(mode="token", stride=1)),
        ("token:1", CaptureTiming(mode="token", stride=1)),
        ("token:8", CaptureTiming(mode="token", stride=8)),
    ],
)
def test_parse_capture_timing(value, expected):
    assert parse_capture_timing(value) == expected


@pytest.mark.parametrize(
    "value",
    ["", "think", "token:0", "token:-1", "token:abc", "move:2"],
)
def test_parse_capture_timing_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        parse_capture_timing(value)


def test_make_capture_layers_relative_and_all():
    assert make_capture_layers(12, mode="relative") == {
        "layer_top": -1,
        "layer_mid": -6,
        "layer_low": -9,
    }
    assert make_capture_layers(4, mode="all") == {
        "layer_001": 1,
        "layer_002": 2,
        "layer_003": 3,
        "layer_004": 4,
    }


def _dummy_result(mode: str) -> GenerationResult:
    hidden = np.arange(24, dtype=np.float16).reshape(3, 2, 4)
    token_mode = mode == "token"
    return GenerationResult(
        text="Move 1 from A to C",
        total_tokens=2,
        reasoning_tokens=0,
        early_stop=None,
        hidden_states={},
        hidden_tensor=hidden,
        token_ids=np.asarray(
            [10, 11, 20] if token_mode else [20, 21],
            dtype=np.int32,
        ),
        token_positions=np.asarray(
            [0, 1, 2] if token_mode else [],
            dtype=np.int32,
        ),
        token_source=np.asarray(
            ["prompt", "prompt", "generated"] if token_mode else [],
            dtype=np.str_,
        ),
        is_think_token=np.asarray(
            [False, False, True] if token_mode else [],
            dtype=np.bool_,
        ),
        layer_ids=np.asarray([1, 4], dtype=np.int32),
        move_steps=np.asarray([1], dtype=np.int32),
        move_texts=["Move 1 from A to C"],
        capture_meta={
            "schema_version": 1,
            "capture_timing": mode,
            "capture_stride": 1 if token_mode else None,
            "capture_layers": "relative",
            "hidden_dtype": "float16",
            "hidden_shape": [3, 2, 4],
        },
    )


def test_save_hidden_npz_token_schema(tmp_path):
    path = tmp_path / "hidden" / "token.npz"
    save_hidden_npz(
        path,
        _dummy_result("token"),
        CaptureTiming(mode="token", stride=1),
    )

    with np.load(path, allow_pickle=False) as data:
        assert set(data.files) == {
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
        }
        assert data["hidden"].shape == (3, 2, 4)
        assert data["hidden"].dtype == np.float16
        assert set(data["token_source"].tolist()) == {"prompt", "generated"}
        assert data["is_think_token"].shape == (3,)
        metadata = json.loads(data["capture_meta"].item())
        assert metadata["hidden_shape"] == [3, 2, 4]
        assert metadata["compression"] == "npz_compressed"
        assert metadata["time_axis"] == "captured_token_rows"
        assert metadata["row_index_unit"] == "hidden_row"
        assert metadata["token_position_unit"] == "prompt_plus_generated_token_index"
        assert metadata["prompt_stride"] == 1
        assert metadata["generated_stride"] == 1
        assert metadata["dt_token_source"] == "successive_token_positions_difference"
        assert metadata["hidden_token_alignment"] == "hidden_row_i_matches_token_positions_i"


def test_save_hidden_npz_move_schema_has_no_legacy_layer_keys(tmp_path):
    path = tmp_path / "hidden" / "move.npz"
    save_hidden_npz(
        path,
        _dummy_result("move"),
        CaptureTiming(mode="move", stride=None),
        compression="none",
    )

    with np.load(path, allow_pickle=False) as data:
        assert set(data.files) == {
            "hidden",
            "layer_ids",
            "move_steps",
            "move_texts",
            "capture_meta",
            "generated_text",
            "token_ids",
        }
        assert not {"layer_low", "layer_mid", "layer_top"} & set(data.files)
        metadata = json.loads(data["capture_meta"].item())
        assert metadata["compression"] == "none"
        assert metadata["time_axis"] == "captured_move_rows"
        assert metadata["generated_stride"] is None
