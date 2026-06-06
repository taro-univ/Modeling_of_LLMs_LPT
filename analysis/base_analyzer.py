from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass
class ConditionData:
    """Loaded data for one (N, T) condition."""

    N: int
    T: float
    trials: list[dict]
    n_trials: int
    accuracy: float
    pm_rate: float
    sg_rate: float
    ordered_rate: float
    early_stop: list[str | None]
    hidden: dict[str, list[np.ndarray]]
    move_steps: list[np.ndarray]
    move_texts: list[list[str]]
    is_fallback: list[bool]


@dataclass
class AnalysisResult:
    """Result returned by an analyzer run."""

    analyzer_name: str
    figure_paths: list[Path]
    metrics: dict
    report_text: str


class BaseAnalyzer(ABC):
    """Common loader and output helper for analysis modules."""

    NS_DEFAULT: list[int] = [2, 3, 4, 5, 6]
    TS_DEFAULT: list[float] = [0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0]
    PM_KEYS: tuple[str, ...] = ("no_move_catchall", "move_ceiling")
    SG_KEYS: tuple[str, ...] = ("move_loop_repeat", "move_loop_reverse")
    ORDER_KEYS: tuple[str, ...] = ("goal_reached",)

    def __init__(
        self,
        data_dir: Path | str,
        out_dir: Path | str,
        ns: list[int] | None = None,
        ts: list[float] | None = None,
        title: str = "",
        layer: str = "layer_mid",
    ) -> None:
        self.data_dir = Path(data_dir)
        self.out_dir = Path(out_dir)
        self.ns = list(ns) if ns is not None else list(self.NS_DEFAULT)
        self.ts = list(ts) if ts is not None else list(self.TS_DEFAULT)
        self.title = title or self.data_dir.name
        self.layer = layer
        self._conditions_cache: dict[bool, dict[tuple[int, float], ConditionData]] = {}

    def load_all(self, *, load_hidden: bool = False) -> dict[tuple[int, float], ConditionData]:
        """Load all existing (N, T) cells, skipping missing directories."""
        if load_hidden in self._conditions_cache:
            return self._conditions_cache[load_hidden]
        result: dict[tuple[int, float], ConditionData] = {}
        for N in self.ns:
            for T in self.ts:
                cond = self._load_condition(N, T, load_hidden=load_hidden)
                if cond is not None:
                    result[(N, T)] = cond
        self._conditions_cache[load_hidden] = result
        return result

    @abstractmethod
    def run_analysis(self) -> AnalysisResult:
        """Run the analyzer and save figures."""

    def _load_condition(
        self,
        N: int,
        T: float,
        *,
        load_hidden: bool = False,
    ) -> Optional[ConditionData]:
        tag = f"{T:.1f}".replace(".", "_")
        cdir = self.data_dir / f"N{N}_T{tag}"
        if not cdir.is_dir():
            return None

        trials, n_trials, accuracy, pm_rate, sg_rate, ordered_rate, early_stop = self._load_summary(cdir)
        hidden: dict[str, list[np.ndarray]] = {}
        move_steps: list[np.ndarray] = []
        move_texts: list[list[str]] = []
        is_fallback: list[bool] = []

        if load_hidden:
            hidden, move_steps, move_texts, is_fallback = self._load_hidden(cdir)

        return ConditionData(
            N=N,
            T=T,
            trials=trials,
            n_trials=n_trials,
            accuracy=accuracy,
            pm_rate=pm_rate,
            sg_rate=sg_rate,
            ordered_rate=ordered_rate,
            early_stop=early_stop,
            hidden=hidden,
            move_steps=move_steps,
            move_texts=move_texts,
            is_fallback=is_fallback,
        )

    def _load_summary(self, cdir: Path) -> tuple[list[dict], int, float, float, float, float, list[str | None]]:
        nan = float("nan")
        path = cdir / "summary.json"
        if not path.exists():
            return [], 0, nan, nan, nan, nan, []
        with path.open() as f:
            trials: list[dict] = json.load(f)
        n = len(trials)
        if n == 0:
            return trials, 0, nan, nan, nan, nan, []
        accuracy = float(sum(r["accuracy"] for r in trials) / n)
        early_stop = [r.get("early_stop") for r in trials]
        pm_rate = sum(1 for es in early_stop if es in self.PM_KEYS) / n
        sg_rate = sum(1 for es in early_stop if es in self.SG_KEYS) / n
        ordered_rate = sum(1 for es in early_stop if es in self.ORDER_KEYS) / n
        return trials, n, accuracy, pm_rate, sg_rate, ordered_rate, early_stop

    def _load_hidden(self, cdir: Path) -> tuple[dict[str, list[np.ndarray]], list[np.ndarray], list[list[str]], list[bool]]:
        hidden: dict[str, list[np.ndarray]] = {}
        move_steps: list[np.ndarray] = []
        move_texts_: list[list[str]] = []
        is_fallback: list[bool] = []

        for npz_path in sorted(cdir.glob("trial_*_hidden.npz")):
            try:
                d = np.load(npz_path, allow_pickle=True)
            except Exception:
                continue
            for key in d.files:
                if key.startswith("layer_"):
                    hidden.setdefault(key, []).append(d[key].astype(np.float32))
            ms = d["move_steps"] if "move_steps" in d.files else np.array([], dtype=np.int32)
            mt = list(d["move_texts"]) if "move_texts" in d.files else []
            move_steps.append(ms)
            move_texts_.append(mt)
            is_fallback.append(len(mt) > 0 and str(mt[0]) == "__fallback__")

        return hidden, move_steps, move_texts_, is_fallback

    def _save_figure(self, fig, name: str) -> Path:
        import matplotlib.pyplot as plt

        self.out_dir.mkdir(parents=True, exist_ok=True)
        path = self.out_dir / f"{name}.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return path

    @staticmethod
    def _t_tag(T: float) -> str:
        return f"T{T:.1f}".replace(".", "_")
