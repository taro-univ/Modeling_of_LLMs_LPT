# 03 クラスとOOP：class / 継承 / ABC / dataclass

## クラスの基本

```python
class TowerOfHanoiEnv:
    def __init__(self, N: int) -> None:   # コンストラクタ
        self.N = N
        self.min_moves = (2 ** N) - 1
        self.initial_state = {
            'A': list(range(N, 0, -1)),
            'B': [], 'C': [],
        }

    def get_prompt(self) -> str:
        return f"Solve Tower of Hanoi with {self.N} disks."

env = TowerOfHanoiEnv(N=4)
print(env.N)           # 4
print(env.min_moves)   # 15
print(env.get_prompt())
```

- `__init__` はインスタンス生成時に自動で呼ばれる
- `self` は「このインスタンス自身」を指す（必ず第1引数）
- `self.xxx` でインスタンス変数として保持

## 継承

親クラスのメソッドや属性を子クラスが引き継ぐ。

```python
class BaseEnv:
    LAMBDA_DIST    = 1.0   # クラス変数（全インスタンス共通）
    LAMBDA_PENALTY = 0.5

    def __init__(self, N: int) -> None:
        self.N = N
        self.min_moves = 0

    def _compute_V(self, state, illegal_count: int = 0) -> float:
        d_hat   = self._min_moves_from(state) / self.min_moves
        penalty = self.LAMBDA_PENALTY * illegal_count
        return round(self.LAMBDA_DIST * d_hat + penalty, 6)


class TowerOfHanoiEnv(BaseEnv):   # BaseEnv を継承
    def __init__(self, N: int) -> None:
        super().__init__(N)        # 親の __init__ を呼ぶ
        self.min_moves = (2 ** N) - 1
        # ... 追加の初期化
```

## 抽象基底クラス（ABC）

実装を強制するインターフェース。`@abstractmethod` を持つメソッドは子クラスで必ず実装しなければならない。

```python
from abc import ABC, abstractmethod

class BaseEnv(ABC):
    @abstractmethod
    def get_prompt(self) -> str: ...      # 実装は子クラスに委ねる

    @abstractmethod
    def goal_reached(self, moves: list) -> bool: ...

# BaseEnv() は直接インスタンス化できない（TypeError）
# TowerOfHanoiEnv(4) は get_prompt / goal_reached を実装しているのでOK
```

## dataclass

フィールド（属性）を保持するクラスを簡潔に定義するデコレータ。
`__init__` を自動生成してくれる。

```python
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

@dataclass
class GenerationResult:
    text:             str
    total_tokens:     int
    reasoning_tokens: int
    early_stop:       Optional[str]
    hidden_states:    dict[str, np.ndarray]
    move_steps:       np.ndarray
    move_texts:       list[str]

# 使い方
result = GenerationResult(
    text="Move 1 from A to C\n...",
    total_tokens=312,
    reasoning_tokens=280,
    early_stop="goal_reached",
    hidden_states={},
    move_steps=np.array([10, 25, 40]),
    move_texts=["Move 1 from A to C"],
)

print(result.total_tokens)   # 312
print(result.early_stop)     # "goal_reached"
```

### field() でデフォルト値を設定

```python
@dataclass
class EarlyStopConfig:
    think_budget_ratio:  float = 0.7
    max_move_multiplier: float = 1.5
    loop_window:         int   = 6
    loop_min_count:      int   = 2
    # ミュータブルなデフォルト値（list/dict）には field(default_factory=...) を使う
    labels: list[str] = field(default_factory=list)
```

## staticmethod と classmethod

```python
class TowerOfHanoiEnv(BaseEnv):

    @staticmethod
    def _third_peg(peg1: str, peg2: str) -> str:
        """self を使わない純粋な関数をクラスにまとめるとき。"""
        return ({'A', 'B', 'C'} - {peg1, peg2}).pop()

    @staticmethod
    def _state_to_key(state: dict) -> tuple:
        return (tuple(state['A']), tuple(state['B']), tuple(state['C']))
```

- `@staticmethod`：`self` も `cls` も不要な関数をクラスの名前空間に置く
- `@classmethod`：`cls`（クラス自身）を受け取る（このコードでは未使用）
