"""puzzleごとのdataset・難易度・remote path定義。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]


class RegistryError(ValueError):
    """未対応puzzleまたは不正な難易度指定。"""


@dataclass(frozen=True)
class DifficultyField:
    """puzzle固有の難易度CLI field。"""

    flag: str
    key: str
    config_key: str
    required: bool = True
    value_type: type = int


@dataclass(frozen=True)
class CellSpec:
    """解決済みdataset cell。"""

    puzzle: str
    dataset_id: str
    cell_id: str
    difficulty: dict[str, int]
    manifest_difficulty: dict[str, int]
    default_remote_root: str


@dataclass(frozen=True)
class PuzzleSpec:
    """puzzleをdataset cellへ写す規則。"""

    name: str
    dataset_id: str
    config_path: Path
    difficulty_fields: tuple[DifficultyField, ...]
    default_remote_root: str

    def resolve_cell(self, difficulty: Mapping[str, Any]) -> CellSpec:
        """config上に存在する難易度をcellへ解決する。"""
        expected = {field.key for field in self.difficulty_fields}
        if set(difficulty) != expected:
            raise RegistryError(
                f"{self.name}: difficulty keys must be {sorted(expected)}"
            )
        normalized = {key: int(value) for key, value in difficulty.items()}
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        if config.get("dataset_id") != self.dataset_id:
            raise RegistryError(f"{self.name}: dataset_id differs from registry")
        for cell in config.get("cells", []):
            candidate = {
                field.key: int(cell[field.config_key])
                for field in self.difficulty_fields
            }
            if candidate == normalized:
                return CellSpec(
                    puzzle=self.name,
                    dataset_id=self.dataset_id,
                    cell_id=str(cell["cell_id"]),
                    difficulty=normalized,
                    manifest_difficulty={
                        field.config_key: normalized[field.key]
                        for field in self.difficulty_fields
                    },
                    default_remote_root=self.default_remote_root,
                )
        details = ", ".join(f"{key}={value}" for key, value in normalized.items())
        raise RegistryError(f"{self.name}: unsupported difficulty ({details})")


PUZZLE_REGISTRY: dict[str, PuzzleSpec] = {
    "pancake": PuzzleSpec(
        name="pancake",
        dataset_id="pancake_full_hidden_distribution_v1",
        config_path=REPO_ROOT / "configs/pancake_full_hidden_dataset_v1.json",
        difficulty_fields=(
            DifficultyField("--N", "N", "N"),
            DifficultyField("--mm", "mm", "min_moves"),
        ),
        default_remote_root=(
            "pancake-drive:LLM_LPT/full_hidden_distribution_v1"
        ),
    )
}


def get_puzzle_spec(name: str) -> PuzzleSpec:
    """登録済みpuzzle定義を返す。"""
    try:
        return PUZZLE_REGISTRY[name]
    except KeyError as exc:
        supported = ", ".join(sorted(PUZZLE_REGISTRY))
        raise RegistryError(
            f"unsupported puzzle: {name!r} (supported: {supported})"
        ) from exc
