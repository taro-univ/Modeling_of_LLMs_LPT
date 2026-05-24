"""lights_out_env.py - Lights Out puzzle environment."""

from __future__ import annotations

import itertools
import re
from typing import Optional

import numpy as np

from envs.base_env import BaseEnv


class LightsOutEnv(BaseEnv):
    """Lights Out environment with GF(2) minimum-weight solutions."""

    LAMBDA_DIST = 1.0
    MAX_GENERATION_ATTEMPTS = 1000

    def __init__(
        self,
        N: int,
        initial_state: Optional[np.ndarray] = None,
        seed: Optional[int] = None,
    ) -> None:
        if N not in (3, 4, 5):
            raise ValueError("LightsOutEnv supports N in {3, 4, 5}")
        super().__init__(N)
        self._goal_state = np.zeros((N, N), dtype=np.int8)
        self._adjacency_matrix = self._build_adjacency_matrix()
        self._rref = self._gf2_rref(self._adjacency_matrix)
        self._min_moves_cache: dict[tuple, int] = {}

        if initial_state is None:
            self._initial_state = self._generate_initial_state(seed)
        else:
            self._initial_state = self._validate_state(initial_state)

        solution = self._minimum_weight_solution(self._initial_state, require_unique=True)
        if solution is None:
            raise ValueError("initial_state must have a unique minimum-weight solution")
        self._initial_solution = solution
        self._initial_min_moves = int(solution.sum())
        if self._initial_min_moves <= 0:
            raise ValueError("initial_state must require at least one move")

    @property
    def min_moves(self) -> int:
        return self._initial_min_moves

    @property
    def initial_state(self) -> np.ndarray:
        return self._initial_state.copy()

    @property
    def goal_state(self) -> np.ndarray:
        return self._goal_state.copy()

    def make_sub_env(self, N: int) -> "LightsOutEnv":
        return LightsOutEnv(N, seed=42)

    def state_to_key(self, state: np.ndarray) -> tuple:
        return tuple(self._validate_state(state).flatten().tolist())

    def get_prompt(self) -> str:
        initial_str = self._state_to_str(self._initial_state)
        return (
            "You are an AI solving a Lights Out puzzle.\n\n"
            "[Rules]\n"
            f"1. The board is a {self.N}x{self.N} grid of lights (0=off, 1=on).\n"
            "2. Each move toggles a cell and its adjacent cells (up/down/left/right).\n"
            "3. Goal: turn all lights off (all 0).\n\n"
            f"[Initial State]\n{initial_str}\n\n"
            "[Output Format]\n"
            'Output each step as "Toggle (row,col)" on its own line (0-indexed).\n'
            "Example: Toggle (0,0)\n\n"
            f"Solve in the minimum number of moves ({self.min_moves} moves). "
            "Output ONLY the moves. Begin:\n"
        )

    def evaluate_state(self, current_moves: list) -> float:
        state = self._simulate(current_moves)
        d = self._min_moves_from_state(state)
        return round(self.LAMBDA_DIST * d / (self.N ** 2), 6)

    def goal_reached(self, current_moves: list) -> bool:
        return bool(np.all(self._simulate(current_moves) == self._goal_state))

    def solve(self) -> list[str]:
        return self._solution_to_moves(self._initial_solution)

    def extract_moves_from_text(self, text: str) -> list[str]:
        matches = re.findall(r"Toggle\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", text, re.IGNORECASE)
        return [f"Toggle ({int(i)},{int(j)})" for i, j in matches]

    def _generate_initial_state(self, seed: Optional[int]) -> np.ndarray:
        rng = np.random.default_rng(seed)
        size = self.N * self.N
        for _ in range(self.MAX_GENERATION_ATTEMPTS):
            solution = rng.integers(0, 2, size=size, dtype=np.int8)
            if int(solution.sum()) == 0:
                continue
            state_vec = (self._adjacency_matrix @ solution) % 2
            state = state_vec.reshape(self.N, self.N).astype(np.int8)
            if self._minimum_weight_solution(state, require_unique=True) is not None:
                return state
        raise RuntimeError("failed to generate a unique-minimum Lights Out state")

    def _apply_toggle(self, state: np.ndarray, i: int, j: int) -> np.ndarray:
        if not (0 <= i < self.N and 0 <= j < self.N):
            return state.copy()
        new_state = state.copy()
        for r, c in ((i, j), (i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
            if 0 <= r < self.N and 0 <= c < self.N:
                new_state[r, c] ^= 1
        return new_state

    def _simulate(self, moves: list) -> np.ndarray:
        state = self._initial_state.copy()
        for move in moves:
            parsed = self._parse_move(str(move))
            if parsed is None:
                continue
            state = self._apply_toggle(state, *parsed)
        return state

    def _min_moves_from_state(self, state: np.ndarray) -> int:
        key = self.state_to_key(state)
        cached = self._min_moves_cache.get(key)
        if cached is not None:
            return cached
        solution = self._minimum_weight_solution(state, require_unique=False)
        if solution is None:
            raise ValueError("state is not solvable")
        moves = int(solution.sum())
        self._min_moves_cache[key] = moves
        return moves

    def _build_adjacency_matrix(self) -> np.ndarray:
        size = self.N * self.N
        matrix = np.zeros((size, size), dtype=np.int8)
        for i in range(self.N):
            for j in range(self.N):
                col = self._cell_to_index(i, j)
                for r, c in ((i, j), (i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
                    if 0 <= r < self.N and 0 <= c < self.N:
                        matrix[self._cell_to_index(r, c), col] = 1
        return matrix

    def _gf2_solve(self, b: np.ndarray) -> Optional[np.ndarray]:
        solution = self._minimum_weight_solution(b.reshape(self.N, self.N), require_unique=False)
        return None if solution is None else solution.copy()

    def _minimum_weight_solution(
        self,
        state: np.ndarray,
        require_unique: bool,
    ) -> Optional[np.ndarray]:
        b = self._validate_state(state).flatten()
        particular, null_basis = self._solve_affine_system(b)
        if particular is None:
            return None

        best_solution: Optional[np.ndarray] = None
        best_weight: Optional[int] = None
        best_count = 0
        for coeffs in itertools.product((0, 1), repeat=len(null_basis)):
            candidate = particular.copy()
            for coeff, basis_vec in zip(coeffs, null_basis):
                if coeff:
                    candidate ^= basis_vec
            weight = int(candidate.sum())
            if best_weight is None or weight < best_weight:
                best_solution = candidate
                best_weight = weight
                best_count = 1
            elif weight == best_weight:
                best_count += 1

        if require_unique and best_count != 1:
            return None
        return best_solution

    def _solve_affine_system(self, b: np.ndarray) -> tuple[Optional[np.ndarray], list[np.ndarray]]:
        rref, pivot_cols = self._rref
        augmented = np.concatenate([self._adjacency_matrix.copy(), b.reshape(-1, 1)], axis=1) % 2
        row = 0
        for col in pivot_cols:
            pivot_row = next((r for r in range(row, augmented.shape[0]) if augmented[r, col]), None)
            if pivot_row is None:
                return None, []
            if pivot_row != row:
                augmented[[row, pivot_row]] = augmented[[pivot_row, row]]
            for r in range(augmented.shape[0]):
                if r != row and augmented[r, col]:
                    augmented[r] ^= augmented[row]
            row += 1

        for r in range(row, augmented.shape[0]):
            if not augmented[r, :-1].any() and augmented[r, -1]:
                return None, []

        size = self.N * self.N
        particular = np.zeros(size, dtype=np.int8)
        for r, col in enumerate(pivot_cols):
            particular[col] = augmented[r, -1]

        free_cols = [col for col in range(size) if col not in set(pivot_cols)]
        null_basis = []
        for free_col in free_cols:
            basis = np.zeros(size, dtype=np.int8)
            basis[free_col] = 1
            for r, pivot_col in enumerate(pivot_cols):
                basis[pivot_col] = rref[r, free_col]
            null_basis.append(basis)
        return particular, null_basis

    @staticmethod
    def _gf2_rref(matrix: np.ndarray) -> tuple[np.ndarray, list[int]]:
        rref = matrix.copy() % 2
        pivot_cols: list[int] = []
        row = 0
        for col in range(rref.shape[1]):
            pivot_row = next((r for r in range(row, rref.shape[0]) if rref[r, col]), None)
            if pivot_row is None:
                continue
            if pivot_row != row:
                rref[[row, pivot_row]] = rref[[pivot_row, row]]
            for r in range(rref.shape[0]):
                if r != row and rref[r, col]:
                    rref[r] ^= rref[row]
            pivot_cols.append(col)
            row += 1
            if row == rref.shape[0]:
                break
        return rref, pivot_cols

    def _solution_to_moves(self, solution: np.ndarray) -> list[str]:
        return [
            f"Toggle ({i},{j})"
            for i in range(self.N)
            for j in range(self.N)
            if solution[self._cell_to_index(i, j)] == 1
        ]

    def _state_to_str(self, state: np.ndarray) -> str:
        clean_state = self._validate_state(state)
        return "\n".join(
            f"  Row {i}: {clean_state[i].astype(int).tolist()}"
            for i in range(self.N)
        )

    def _parse_move(self, move_str: str) -> Optional[tuple[int, int]]:
        match = re.search(r"Toggle\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", move_str, re.IGNORECASE)
        if not match:
            return None
        return int(match.group(1)), int(match.group(2))

    def _validate_state(self, state: np.ndarray) -> np.ndarray:
        array = np.asarray(state, dtype=np.int8)
        if array.shape != (self.N, self.N):
            raise ValueError(f"state must have shape ({self.N}, {self.N})")
        if not np.all((array == 0) | (array == 1)):
            raise ValueError("state entries must be 0 or 1")
        return array.copy()

    def _cell_to_index(self, i: int, j: int) -> int:
        return i * self.N + j
