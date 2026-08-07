import sys

import pytest

from envs.pancake_env import PancakeSortingEnv
import runners.run_local as run_local
from runners.debug_prompt import analyze_pancake_trajectory
from runners.run_local import (
    CaptureTiming,
    GenerationResult,
    _puzzle_name,
    parse_args,
    parse_initial_state,
)


def test_pancake_seed_is_reproducible():
    env_a = PancakeSortingEnv(N=5, seed=123)
    env_b = PancakeSortingEnv(N=5, seed=123)

    assert env_a.initial_state == env_b.initial_state
    assert env_a.solve() == env_b.solve()
    assert env_a.min_moves == env_b.min_moves


def test_pancake_solution_is_exact_and_reaches_goal():
    env = PancakeSortingEnv(N=5, seed=1)
    solution = env.solve()

    assert len(solution) == env.min_moves
    assert env.goal_reached(solution) is True
    assert env.evaluate_state(solution) == 0.0
    assert env.evaluate_state([]) == 1.0


def test_pancake_known_one_move_state_uses_exact_bfs_distance():
    env = PancakeSortingEnv(N=4, initial_state=(3, 2, 1, 4))

    assert env.min_moves == 1
    assert env.solve() == ["Flip 3"]


def test_pancake_extracts_normalized_moves_with_positions():
    env = PancakeSortingEnv(N=5, seed=2)
    text = "Flip 3\nnoise\nflip 05"

    assert env.extract_moves_from_text(text) == ["Flip 3", "Flip 5"]
    assert env.extract_moves_with_position(text) == [
        ("Flip 3", text.index("Flip 3")),
        ("Flip 5", text.index("flip 05")),
    ]
    assert env.count_moves(text) == 2


def test_pancake_state_to_key_normalizes_and_validates():
    env = PancakeSortingEnv(N=3, initial_state=(3, 1, 2))

    assert env.state_to_key([3, 1, 2]) == (3, 1, 2)
    with pytest.raises(ValueError, match="permutation"):
        env.state_to_key([3, 1, 1])


@pytest.mark.parametrize("N", [2, 9])
def test_pancake_rejects_unsupported_sizes(N):
    with pytest.raises(ValueError, match="supports N"):
        PancakeSortingEnv(N=N)


@pytest.mark.parametrize(
    "state",
    [
        (1, 2, 2, 4),
        (1, 2, 3),
        (1, 2, 3, 5),
    ],
)
def test_pancake_rejects_invalid_initial_states(state):
    with pytest.raises(ValueError):
        PancakeSortingEnv(N=4, initial_state=state)


def test_pancake_rejects_solved_initial_state():
    with pytest.raises(ValueError, match="goal state"):
        PancakeSortingEnv(N=4, initial_state=(1, 2, 3, 4))


def test_pancake_scramble_depth_is_reproducible_and_non_goal():
    env_a = PancakeSortingEnv(N=6, seed=99, scramble_depth=12)
    env_b = PancakeSortingEnv(N=6, seed=99, scramble_depth=12)

    assert env_a.initial_state == env_b.initial_state
    assert env_a.initial_state != env_a.goal_state
    assert env_a.min_moves > 0


@pytest.mark.parametrize("scramble_depth", [0, -1, 1.5])
def test_pancake_rejects_invalid_scramble_depth(scramble_depth):
    with pytest.raises(ValueError, match="scramble_depth"):
        PancakeSortingEnv(N=4, scramble_depth=scramble_depth)


def test_pancake_invalid_flips_are_extractable_no_ops():
    env = PancakeSortingEnv(N=4, initial_state=(3, 2, 1, 4))
    invalid_moves = env.extract_moves_from_text("Flip 1\nFlip 0\nFlip 9")

    assert invalid_moves == ["Flip 1", "Flip 0", "Flip 9"]
    assert env.evaluate_state(invalid_moves) == 1.0
    assert env.goal_reached(invalid_moves) is False


def test_pancake_goal_reached_ignores_moves_after_goal():
    env = PancakeSortingEnv(N=4, initial_state=(3, 2, 1, 4))
    moves = env.solve() + ["Flip 4"]

    assert env.goal_reached(moves) is True
    assert env.evaluate_state(moves) == 0.0


def test_pancake_prompt_and_system_hint_describe_contract():
    env = PancakeSortingEnv(N=4, initial_state=(3, 2, 1, 4))
    prompt = env.get_prompt()

    assert "Pancake Sorting" in prompt
    assert "top to bottom" in prompt
    assert "2 <= k <= 4" in prompt
    assert "Stack: [1, 2, 3, 4]" in prompt
    assert "minimum number of moves (1 moves)" in prompt
    assert "<final>" in prompt
    assert "Only moves inside <final>" in prompt
    assert "Pancake Sorting" in env.get_system_hint()


def test_pancake_final_block_is_the_scored_answer_only():
    env = PancakeSortingEnv(N=4, initial_state=(3, 2, 1, 4))
    text = (
        "Search: Flip 2 is a bad candidate.\n"
        "<final>\n"
        "Flip 3\n"
        "</final>\n"
        "Extra: Flip 4\n"
    )

    assert env.extract_moves_from_text(text) == ["Flip 2", "Flip 3", "Flip 4"]
    assert env.extract_final_moves_from_text(text) == ["Flip 3"]
    assert env.extract_scored_moves_from_text(text) == ["Flip 3"]
    assert env.goal_reached(env.extract_scored_moves_from_text(text)) is True


def test_pancake_without_final_block_scores_as_empty_answer():
    env = PancakeSortingEnv(N=4, initial_state=(3, 2, 1, 4))
    text = "Search reaches the goal: Flip 3"

    assert env.extract_moves_from_text(text) == ["Flip 3"]
    assert env.extract_scored_moves_from_text(text) == []
    assert env.goal_reached(env.extract_moves_from_text(text)) is True
    assert env.goal_reached(env.extract_scored_moves_from_text(text)) is False


def test_pancake_open_final_block_scores_until_eof():
    env = PancakeSortingEnv(N=4, initial_state=(3, 2, 1, 4))

    assert env.extract_scored_moves_from_text("<final>\nFlip 3\n") == ["Flip 3"]


def test_pancake_debug_trajectory_separates_search_from_final_answer():
    env = PancakeSortingEnv(N=4, initial_state=(3, 2, 1, 4))
    moves = env.extract_moves_from_text("Search: Flip 3\n<final>\nFlip 2\n</final>")
    trajectory = analyze_pancake_trajectory(env, moves)

    assert trajectory["moves_all_mentions"] == ["Flip 3", "Flip 2"]
    assert trajectory["goal_reached_all_mentions"] is True
    assert trajectory["first_goal_index"] == 0
    assert trajectory["excess_after_goal"] == 1


def test_run_local_recognizes_pancake_name_and_cli_seed(monkeypatch):
    env = PancakeSortingEnv(N=4, seed=7)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_local.py",
            "--puzzle",
            "pancake",
            "--N",
            "4",
            "--seed",
            "7",
        ],
    )

    args = parse_args()

    assert _puzzle_name(env) == "pancake"
    assert args.puzzle == "pancake"
    assert args.seed == 7
    assert args.n_shot == 0


def test_run_local_parses_pancake_initial_state_and_instance_id(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_local.py",
            "--puzzle",
            "pancake",
            "--N",
            "5",
            "--seed",
            "1",
            "--initial-state",
            "1,2,5,4,3",
            "--instance-id",
            "N5_seed1_mm3",
        ],
    )

    args = parse_args()

    assert args.initial_state == (1, 2, 5, 4, 3)
    assert parse_initial_state("[3,2,1,4]") == (3, 2, 1, 4)
    assert args.instance_id == "N5_seed1_mm3"


def test_run_local_rejects_initial_state_for_non_pancake(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_local.py",
            "--puzzle",
            "hanoi",
            "--N",
            "3",
            "--initial-state",
            "3,2,1",
        ],
    )

    with pytest.raises(SystemExit):
        parse_args()


def test_run_experiment_hf_records_pancake_instance_metadata(monkeypatch, tmp_path):
    env = PancakeSortingEnv(N=5, initial_state=(1, 2, 5, 4, 3))

    def fake_generate_with_hidden_states(**kwargs):
        return GenerationResult(
            text="<final>\nFlip 5\nFlip 3\nFlip 5\n</final>",
            total_tokens=4,
            reasoning_tokens=0,
            early_stop=None,
            hidden_states={},
            hidden_tensor=run_local.np.zeros((1, 1, 2), dtype=run_local.np.float16),
            token_ids=run_local.np.asarray([1, 2], dtype=run_local.np.int32),
            token_positions=run_local.np.asarray([], dtype=run_local.np.int32),
            token_source=run_local.np.asarray([], dtype=run_local.np.str_),
            is_think_token=run_local.np.asarray([], dtype=run_local.np.bool_),
            layer_ids=run_local.np.asarray([1], dtype=run_local.np.int32),
            move_steps=run_local.np.asarray([1], dtype=run_local.np.int32),
            move_texts=["Flip 5"],
            capture_meta={
                "schema_version": 1,
                "capture_timing": "move",
                "capture_stride": None,
                "capture_layers": "relative",
                "hidden_dtype": "float16",
                "hidden_shape": [1, 1, 2],
            },
        )

    monkeypatch.setattr(run_local, "generate_with_hidden_states", fake_generate_with_hidden_states)

    results = run_local.run_experiment_hf(
        env=env,
        N=5,
        trials=1,
        model_id="dummy/model",
        model=object(),
        tokenizer=object(),
        num_predict=16,
        output_dir=tmp_path,
        capture_timing=CaptureTiming(mode="move", stride=None),
        seed=1,
        instance_id="N5_seed1_mm3",
        instance_seed=1,
    )

    assert results[0]["initial_state"] == [1, 2, 5, 4, 3]
    assert results[0]["min_moves"] == env.min_moves
    assert results[0]["instance_id"] == "N5_seed1_mm3"
    hidden_path = tmp_path / "hidden" / "trial_001_hidden_move_relative_float16.npz"
    with run_local.np.load(hidden_path, allow_pickle=False) as data:
        metadata = run_local.json.loads(data["capture_meta"].item())
    assert metadata["initial_state"] == [1, 2, 5, 4, 3]
    assert metadata["min_moves"] == env.min_moves
    assert metadata["instance_id"] == "N5_seed1_mm3"
    assert metadata["instance_seed"] == 1
