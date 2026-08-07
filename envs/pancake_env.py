"""Pancake Sorting puzzle environment."""

from __future__ import annotations

import re
from collections import deque
from functools import lru_cache
from random import Random
from typing import Iterable, Optional

from envs.base_env import BaseEnv


State = tuple[int, ...]
BfsTables = tuple[dict[State, int], dict[State, str]]


def _flip_state(state: State, k: int) -> State:
    return state[:k][::-1] + state[k:]


@lru_cache(maxsize=None)
def _build_bfs_tables(N: int) -> BfsTables:
    """Build exact distance and next-move tables for one pancake count."""
    goal = tuple(range(1, N + 1))
    distance = {goal: 0}
    next_move_to_goal: dict[State, str] = {}
    queue = deque([goal])

    while queue:
        state = queue.popleft()
        for k in range(2, N + 1):
            neighbor = _flip_state(state, k)
            if neighbor in distance:
                continue
            distance[neighbor] = distance[state] + 1
            next_move_to_goal[neighbor] = f"Flip {k}"
            queue.append(neighbor)

    return distance, next_move_to_goal


class PancakeSortingEnv(BaseEnv):
    """Prefix-reversal sorting with exact shortest-path evaluation."""

    MIN_N = 3
    MAX_N = 8
    MAX_GENERATION_ATTEMPTS = 1000
    LAMBDA_DIST = 1.0
    SYSTEM_HINT = (
        "You are an expert at Pancake Sorting. Track the stack exactly after "
        "each prefix reversal. Use only legal moves of the form \"Flip k\". "
        "Put the final submitted move sequence only inside <final>...</final>."
    )
    MOVE_RE = re.compile(r"Flip\s+(\d+)", re.IGNORECASE)
    FINAL_BLOCK_RE = re.compile(r"<final>(.*?)</final>", re.IGNORECASE | re.DOTALL)
    FINAL_OPEN_RE = re.compile(r"<final>", re.IGNORECASE)

    def __init__(
        self,
        N: int,
        initial_state: Optional[tuple[int, ...]] = None,
        seed: Optional[int] = None,
        scramble_depth: Optional[int] = None,
    ) -> None:
        if not isinstance(N, int) or isinstance(N, bool) or not self.MIN_N <= N <= self.MAX_N:
            raise ValueError(f"PancakeSortingEnv supports N in {self.MIN_N}..{self.MAX_N}")
        if scramble_depth is not None and (
            not isinstance(scramble_depth, int)
            or isinstance(scramble_depth, bool)
            or scramble_depth <= 0
        ):
            raise ValueError("scramble_depth must be a positive integer")

        super().__init__(N)
        self._goal_state: State = tuple(range(1, N + 1))
        self._distance, self._next_move_to_goal = _build_bfs_tables(N)

        if initial_state is None:
            depth = max(2, N) if scramble_depth is None else scramble_depth
            self._initial_state = self._generate_initial_state(seed, depth)
        else:
            self._initial_state = self.state_to_key(initial_state)

        if self._initial_state == self._goal_state:
            raise ValueError("initial_state must not be the goal state")
        self._initial_min_moves = self._distance[self._initial_state]

    @property
    def min_moves(self) -> int:
        return self._initial_min_moves

    @property
    def initial_state(self) -> State:
        return self._initial_state

    @property
    def goal_state(self) -> State:
        return self._goal_state

    def make_sub_env(self, N: int) -> "PancakeSortingEnv":
        return PancakeSortingEnv(N, seed=42)

    def state_to_key(self, state: Iterable[int]) -> State:
        try:
            key = tuple(state)
        except TypeError as exc:
            raise ValueError("state must be an iterable permutation") from exc
        if len(key) != self.N:
            raise ValueError(f"state must contain exactly {self.N} pancakes")
        if any(not isinstance(value, int) or isinstance(value, bool) for value in key):
            raise ValueError("state entries must be integers")
        if set(key) != set(range(1, self.N + 1)):
            raise ValueError(f"state must be a permutation of 1..{self.N}")
        return key

    def get_prompt(self) -> str:
        initial = list(self.initial_state)
        goal = list(self.goal_state)
        return (
            "You are an AI solving a Pancake Sorting puzzle.\n\n"
            "[Rules]\n"
            f"1. The stack contains {self.N} pancakes labeled 1 to {self.N}.\n"
            "2. The stack is shown from top to bottom.\n"
            "3. A move \"Flip k\" reverses the top k pancakes.\n"
            f"4. Only moves with 2 <= k <= {self.N} are legal.\n"
            f"5. Goal: sort the stack into {goal} from top to bottom.\n\n"
            "[Initial State]\n"
            f"  Stack: {initial}\n\n"
            "[Goal State]\n"
            f"  Stack: {goal}\n\n"
            "[Output Format]\n"
            "You may reason freely in the search phase.\n"
            "After searching, put the final submitted move sequence inside "
            "<final>...</final>.\n"
            "Only moves inside <final>...</final> will be graded.\n"
            "Inside <final>, output each step as \"Flip k\" on its own line.\n"
            "Example:\n"
            "<final>\n"
            "Flip 3\n"
            "</final>\n\n"
            f"Solve in the minimum number of moves ({self.min_moves} moves). "
            "Begin:\n"
        )

    def get_system_hint(self) -> str:
        return self.SYSTEM_HINT

    def extract_moves_from_text(self, text: str) -> list[str]:
        return [f"Flip {int(match.group(1))}" for match in self.MOVE_RE.finditer(text)]

    def extract_final_answer_text(self, text: str) -> str:
        """Return the last <final> block, or an open final block through EOF."""
        matches = list(self.FINAL_BLOCK_RE.finditer(text))
        if matches:
            return matches[-1].group(1)
        open_matches = list(self.FINAL_OPEN_RE.finditer(text))
        if open_matches:
            return text[open_matches[-1].end():]
        return ""

    def extract_final_moves_from_text(self, text: str) -> list[str]:
        return self.extract_moves_from_text(self.extract_final_answer_text(text))

    def extract_scored_moves_from_text(self, text: str) -> list[str]:
        return self.extract_final_moves_from_text(text)

    def extract_moves_with_position(self, text: str) -> list[tuple[str, int]]:
        return [
            (f"Flip {int(match.group(1))}", match.start())
            for match in self.MOVE_RE.finditer(text)
        ]

    def evaluate_state(self, current_moves: list) -> float:
        state = self._simulate(current_moves, stop_at_goal=True)
        value = self.LAMBDA_DIST * self._distance[state] / self.min_moves
        return round(value, 6)

    def goal_reached(self, current_moves: list) -> bool:
        state = self.initial_state
        for move in current_moves:
            if state == self.goal_state:
                return True
            state = self._apply_move_if_legal(state, str(move))
        return state == self.goal_state

    def solve(self) -> list[str]:
        state = self.initial_state
        moves: list[str] = []
        while state != self.goal_state:
            move = self._next_move_to_goal[state]
            moves.append(move)
            state = self._apply_move_if_legal(state, move)
        return moves

    def distance_to_goal(self, state: Iterable[int]) -> int:
        """Return the exact BFS distance from state to the sorted goal."""
        return self._distance[self.state_to_key(state)]

    def apply_move(self, state: Iterable[int], move: str) -> State:
        """Apply one legal Flip move; invalid moves are no-ops."""
        return self._apply_move_if_legal(self.state_to_key(state), move)

    def _generate_initial_state(self, seed: Optional[int], scramble_depth: int) -> State:
        rng = Random(seed)
        legal_flips = tuple(range(2, self.N + 1))

        for _ in range(self.MAX_GENERATION_ATTEMPTS):
            state = self.goal_state
            previous_k: Optional[int] = None
            for _ in range(scramble_depth):
                choices = [k for k in legal_flips if k != previous_k]
                k = rng.choice(choices)
                state = _flip_state(state, k)
                previous_k = k
            if self._distance[state] > 0:
                return state

        raise RuntimeError("failed to generate a non-goal Pancake Sorting state")

    def _simulate(self, moves: list, stop_at_goal: bool = False) -> State:
        state = self.initial_state
        for move in moves:
            if stop_at_goal and state == self.goal_state:
                break
            state = self._apply_move_if_legal(state, str(move))
        return state

    def _apply_move_if_legal(self, state: State, move: str) -> State:
        match = self.MOVE_RE.search(move)
        if not match:
            return state
        k = int(match.group(1))
        if not 2 <= k <= self.N:
            return state
        return _flip_state(state, k)
