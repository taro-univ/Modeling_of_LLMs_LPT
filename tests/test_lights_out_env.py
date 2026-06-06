import numpy as np
import pytest

from envs.lights_out_env import LightsOutEnv


def test_lights_out_seed_is_reproducible():
    env_a = LightsOutEnv(N=3, seed=123)
    env_b = LightsOutEnv(N=3, seed=123)

    assert np.array_equal(env_a.initial_state, env_b.initial_state)
    assert env_a.solve() == env_b.solve()
    assert env_a.min_moves == env_b.min_moves


def test_lights_out_solves_to_goal_and_v_uses_n_squared_normalization():
    env = LightsOutEnv(N=3, seed=1)
    solution = env.solve()

    assert env.min_moves > 0
    assert len(solution) == env.min_moves
    assert env.goal_reached(solution) is True
    assert env.evaluate_state(solution) == 0.0
    assert env.evaluate_state([]) == round(env.min_moves / (env.N ** 2), 6)
    assert 0.0 <= env.evaluate_state([]) <= 1.0


def test_lights_out_extract_moves_and_state_to_key():
    env = LightsOutEnv(N=3, seed=2)
    text = "Toggle (0,0)\nnoise\nToggle (2,1)\nToggle (02, 01)"

    assert env.extract_moves_from_text(text) == [
        "Toggle (0,0)",
        "Toggle (2,1)",
        "Toggle (2,1)",
    ]
    assert env.state_to_key(np.eye(3, dtype=np.int8)) == (1, 0, 0, 0, 1, 0, 0, 0, 1)


def test_lights_out_count_moves_and_positions():
    env = LightsOutEnv(N=3, seed=2)
    text = "thinking\nToggle (0,0)\nmore text\nTOGGLE (2, 1)\nToggle (02, 01)"

    assert env.count_moves(text) == 3
    assert env.extract_moves_with_position(text) == [
        ("Toggle (0,0)", text.index("Toggle (0,0)")),
        ("Toggle (2,1)", text.index("TOGGLE (2, 1)")),
        ("Toggle (2,1)", text.index("Toggle (02, 01)")),
    ]


def test_lights_out_system_hint_is_puzzle_specific():
    env = LightsOutEnv(N=3, seed=2)
    hint = env.get_system_hint()

    assert "Lights Out" in hint
    assert "GF(2)" in hint
    assert "Tower of Hanoi" not in hint


def test_lights_out_adjacency_shape_and_center_toggle():
    env = LightsOutEnv(N=3, seed=3)
    matrix = env._build_adjacency_matrix()
    center_col = matrix[:, 4].reshape(3, 3)

    assert matrix.shape == (9, 9)
    assert center_col.tolist() == [
        [0, 1, 0],
        [1, 1, 1],
        [0, 1, 0],
    ]


def test_lights_out_gf2_solve_returns_minimum_solution():
    env = LightsOutEnv(N=3, seed=4)
    solution_vec = env._gf2_solve(env.initial_state.flatten())

    assert solution_vec is not None
    assert int(solution_vec.sum()) == env.min_moves
    assert env._solution_to_moves(solution_vec) == env.solve()


def test_lights_out_rejects_unsolvable_state():
    state = np.zeros((4, 4), dtype=np.int8)
    state[0, 0] = 1

    with pytest.raises(ValueError, match="unique minimum-weight solution"):
        LightsOutEnv(N=4, initial_state=state)


def test_lights_out_rejects_nonunique_minimum_state():
    state = np.array(
        [
            [0, 0, 0, 0],
            [0, 1, 1, 1],
            [1, 0, 0, 0],
            [0, 0, 0, 0],
        ],
        dtype=np.int8,
    )

    with pytest.raises(ValueError, match="unique minimum-weight solution"):
        LightsOutEnv(N=4, initial_state=state)
