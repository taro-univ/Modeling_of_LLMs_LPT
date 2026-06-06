from envs.hanoi_env import TowerOfHanoiEnv


def test_hanoi_min_moves_and_endpoints():
    env = TowerOfHanoiEnv(N=3)
    full_b = env.goal_states[0]

    assert env.min_moves == 7
    assert env.evaluate_state([]) == 1.0
    assert env.evaluate_state(env.solve()) == 0.0
    assert env.goal_reached(env.solve()) is True
    assert env._min_moves_from(env.initial_state) == env.min_moves
    assert env._min_moves_from(env.goal_state) == 0
    assert env._min_moves_from_symmetric(env.initial_state) == env.min_moves
    assert env._min_moves_from_symmetric(env.goal_state) == 0
    assert env._min_moves_from_symmetric(full_b) == 0


def test_hanoi_symmetric_goal_accepts_full_b_and_full_c():
    env = TowerOfHanoiEnv(N=2)
    solve_to_b = env._solve_recursive(env.N, 'A', 'B', 'C')

    assert env.goal_reached(solve_to_b) is True
    assert env.evaluate_state(solve_to_b) == 0.0
    assert env.goal_reached(env.solve()) is True
    assert env.evaluate_state(env.solve()) == 0.0


def test_hanoi_symmetric_goal_excludes_return_to_a():
    env = TowerOfHanoiEnv(N=2)
    solve_to_b = env._solve_recursive(env.N, 'A', 'B', 'C')
    return_to_a = env._solve_recursive(env.N, 'B', 'A', 'C')

    assert env.goal_reached(solve_to_b + return_to_a) is True
    assert env.goal_reached(return_to_a) is False


def test_hanoi_prompt_still_targets_c():
    env = TowerOfHanoiEnv(N=2)
    prompt = env.get_prompt()
    full_b_prompt = env.get_prompt_from_state(env.goal_states[0])

    assert "Peg B: [(empty)]" in prompt
    assert "Peg C: [2, 1]" in prompt
    assert "Solve in the minimum number of moves (3 moves)." in full_b_prompt


def test_hanoi_illegal_move_adds_penalty():
    env = TowerOfHanoiEnv(N=3)

    assert env.evaluate_state(["Move 3 from A to B"]) > 1.0


def test_hanoi_extract_moves_from_text():
    env = TowerOfHanoiEnv(N=3)

    assert env.extract_moves_from_text("Move 1 from A to C\nmove 2 from a to b") == [
        "Move 1 from A to C",
        "Move 2 from A to B",
    ]


def test_hanoi_extract_moves_with_position_returns_normalized_text_and_start():
    env = TowerOfHanoiEnv(N=3)
    text = "thinking\nMove 1 from A to C\nnoise\nmove 2 from a to b"

    assert env.extract_moves_with_position(text) == [
        ("Move 1 from A to C", text.index("Move 1 from A to C")),
        ("Move 2 from A to B", text.index("move 2 from a to b")),
    ]


def test_hanoi_system_hint_is_puzzle_specific():
    env = TowerOfHanoiEnv(N=3)
    hint = env.get_system_hint()

    assert "Tower of Hanoi" in hint
    assert "Lights Out" not in hint


def test_hanoi_state_to_key_and_simulate_states_use_public_key_method():
    env = TowerOfHanoiEnv(N=2)
    states = env._simulate_states(env.initial_state, ["Move 1 from A to B"])

    assert env.state_to_key(env.initial_state) == ((2, 1), (), ())
    assert states == [((2, 1), (), ()), ((2,), (1,), ())]
