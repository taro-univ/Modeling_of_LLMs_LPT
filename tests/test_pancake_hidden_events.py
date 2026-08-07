import json

import numpy as np

from analysis.join_pancake_hidden_events import join_run


def test_join_run_builds_strided_pancake_token_series(tmp_path):
    run_dir = tmp_path / "run"
    hidden_dir = run_dir / "hidden"
    hidden_dir.mkdir(parents=True)
    out_dir = tmp_path / "events"

    summary = {
        "trial": 1,
        "puzzle": "pancake",
        "N": 3,
        "temperature": 0.6,
        "num_predict": 16,
        "model_id": "test/model",
        "instance_id": "N3_test",
        "initial_state": [3, 2, 1],
        "min_moves": 1,
        "accuracy": 1,
        "moves_all_mentions": ["Flip 3", "Flip 3"],
    }
    (run_dir / "summary.json").write_text(
        json.dumps([summary]), encoding="utf-8"
    )

    token_positions = np.asarray(
        [0, 1, 2, 3, 5, 7, 9, 11, 13, 15, 17], dtype=np.int32
    )
    token_source = np.asarray(
        ["prompt"] * 3 + ["generated"] * 8, dtype=np.str_
    )
    generated_text = "think Flip 3 <final>\nFlip 3\n</final>"
    capture_meta = {
        "trial": 1,
        "puzzle": "pancake",
        "N": 3,
        "temperature": 0.6,
        "num_predict": 16,
        "model_id": "test/model",
        "instance_id": "N3_test",
        "initial_state": [3, 2, 1],
        "min_moves": 1,
        "prompt_token_count": 3,
        "generated_token_count": 16,
        "hidden_shape": [11, 2, 4],
    }
    np.savez_compressed(
        hidden_dir / "trial_001_hidden_token_2_relative_float16.npz",
        hidden=np.zeros((11, 2, 4), dtype=np.float16),
        token_ids=np.arange(11, dtype=np.int32),
        token_positions=token_positions,
        token_source=token_source,
        is_think_token=np.asarray(
            [False] * 3 + [True] * 4 + [False] * 4, dtype=np.bool_
        ),
        layer_ids=np.asarray([2, 6], dtype=np.int32),
        generated_text=np.asarray(generated_text, dtype=np.str_),
        move_steps=np.asarray([1, 9], dtype=np.int32),
        move_texts=np.asarray(["Flip 3", "Flip 3"], dtype=np.str_),
        capture_meta=np.asarray(json.dumps(capture_meta), dtype=np.str_),
    )

    written = join_run(run_dir, out_dir)

    assert written == [out_dir / "trial_001_events.json"]
    result = json.loads(written[0].read_text(encoding="utf-8"))
    assert {
        "schema_version",
        "join_ok",
        "join_warnings",
        "boundary_ok",
        "summary_json",
        "hidden_npz",
        "trajectory_ref",
        "problem",
        "outcome_label",
        "token_series",
        "events",
    } <= result.keys()
    assert result["join_ok"] is True
    assert result["boundary_ok"] is True
    assert result["outcome_label"] == "success_final"
    assert result["trajectory_ref"] == {
        "hidden_key": "hidden",
        "shape": [11, 2, 4],
        "layer_ids": [2, 6],
    }

    series = result["token_series"]
    assert series["t_row"] == list(range(11))
    assert series["token_position"] == token_positions.tolist()
    assert series["dt_token"] == [1, 1, 1, 2, 2, 2, 2, 2, 2, 2, None]
    assert series["flags"]["is_move_event"] == [
        False,
        False,
        False,
        False,
        True,
        False,
        False,
        False,
        True,
        False,
        False,
    ]
    assert series["move_index"][4] == 0
    assert series["move_index"][8] == 1
    assert series["state_index"][3:9] == [0, 1, 1, 1, 1, 2]
    assert series["distance_to_goal"][3:9] == [1, 0, 0, 0, 0, 1]
    assert series["v"][3:9] == [1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
    assert series["flags"]["is_after_first_goal"][4:] == [True] * 7
    assert any(series["flags"]["is_final_region"])
    assert "final" in series["phase_label"]
    assert "post_goal" in series["phase_label"]

    move_events = [
        event for event in result["events"] if event["name"] == "move_mention"
    ]
    assert move_events[0]["t_row"] == 4
    assert move_events[0]["state_before"] == [3, 2, 1]
    assert move_events[0]["state_after"] == [1, 2, 3]
    assert move_events[0]["delta_distance"] == -1
    assert move_events[1]["t_row"] == 8
    assert move_events[1]["state_after"] == [3, 2, 1]
    assert move_events[1]["delta_distance"] == 1
    assert any("mapped to next captured row" in item for item in result["join_warnings"])
    assert any(
        "proportional character-to-token" in item
        for item in result["join_warnings"]
    )


def test_join_run_emits_failed_join_for_missing_hidden_trial(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(
        json.dumps(
            [
                {
                    "trial": 7,
                    "puzzle": "pancake",
                    "N": 3,
                    "initial_state": [3, 2, 1],
                    "accuracy": 0,
                }
            ]
        ),
        encoding="utf-8",
    )

    written = join_run(run_dir, tmp_path / "events")

    result = json.loads(written[0].read_text(encoding="utf-8"))
    assert written[0].name == "trial_007_events.json"
    assert result["join_ok"] is False
    assert result["boundary_ok"] is False
    assert result["hidden_npz"] is None
    assert result["token_series"]["t_row"] == []
