from envs.hanoi_env import TowerOfHanoiEnv


def test_hanoi_min_moves_and_endpoints():
    env = TowerOfHanoiEnv(N=3)

    assert env.min_moves == 7
    assert env.evaluate_state([]) == 1.0
    assert env.evaluate_state(env.solve()) == 0.0
    assert env.goal_reached(env.solve()) is True
    assert env._min_moves_from(env.initial_state) == env.min_moves
    assert env._min_moves_from(env.goal_state) == 0


def test_hanoi_illegal_move_adds_penalty():
    env = TowerOfHanoiEnv(N=3)

    assert env.evaluate_state(["Move 3 from A to B"]) > 1.0


def test_hanoi_extract_moves_from_text():
    env = TowerOfHanoiEnv(N=3)

    assert env.extract_moves_from_text("Move 1 from A to C\nmove 2 from a to b") == [
        "Move 1 from A to C",
        "Move 2 from A to B",
    ]


def test_hanoi_state_to_key_and_simulate_states_use_public_key_method():
    env = TowerOfHanoiEnv(N=2)
    states = env._simulate_states(env.initial_state, ["Move 1 from A to B"])

    assert env.state_to_key(env.initial_state) == ((2, 1), (), ())
    assert states == [((2, 1), (), ()), ((2,), (1,), ())]
