"""
base_env.py - Abstract base class for puzzle environments.

Only puzzle-independent contracts live here.  The progress metric V(x) is
defined by each concrete puzzle because its physical meaning is puzzle-specific.
"""

from abc import ABC, abstractmethod
from typing import Hashable


class BaseEnv(ABC):
    """Common interface implemented by all puzzle environments."""

    def __init__(self, N: int) -> None:
        self.N = N

    @property
    @abstractmethod
    def min_moves(self) -> int:
        """Minimum number of moves from the initial state to the goal."""

    @property
    @abstractmethod
    def initial_state(self):
        """Initial puzzle state."""

    @property
    @abstractmethod
    def goal_state(self):
        """Goal puzzle state."""

    @abstractmethod
    def get_prompt(self) -> str:
        """Return the prompt for this puzzle instance."""

    @abstractmethod
    def evaluate_state(self, current_moves: list) -> float:
        """Return the puzzle-specific progress metric V(x)."""

    @abstractmethod
    def goal_reached(self, current_moves: list) -> bool:
        """Return whether applying the moves reaches the goal."""

    @abstractmethod
    def solve(self) -> list:
        """Return an optimal move sequence."""

    @abstractmethod
    def extract_moves_from_text(self, text: str) -> list:
        """Extract puzzle moves from model output text."""

    @abstractmethod
    def state_to_key(self, state) -> Hashable:
        """Convert a state to a hashable key."""

    @abstractmethod
    def make_sub_env(self, N: int) -> "BaseEnv":
        """Return a smaller environment of the same puzzle type."""
