import pytest

from envs.base_env import BaseEnv
from envs.hanoi_env import TowerOfHanoiEnv
from envs.lights_out_env import LightsOutEnv


def test_base_env_is_abstract():
    with pytest.raises(TypeError):
        BaseEnv(3)


def test_concrete_envs_are_base_env_subclasses():
    assert issubclass(TowerOfHanoiEnv, BaseEnv)
    assert issubclass(LightsOutEnv, BaseEnv)


def test_make_sub_env_returns_same_puzzle_type_and_base_env():
    hanoi = TowerOfHanoiEnv(3).make_sub_env(2)
    lights = LightsOutEnv(3, seed=42).make_sub_env(3)

    assert isinstance(hanoi, TowerOfHanoiEnv)
    assert isinstance(hanoi, BaseEnv)
    assert hanoi.min_moves > 0

    assert isinstance(lights, LightsOutEnv)
    assert isinstance(lights, BaseEnv)
    assert lights.min_moves > 0
