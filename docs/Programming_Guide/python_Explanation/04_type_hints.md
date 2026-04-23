# 04 型ヒント（Type Hints）

Python は動的型付け言語だが、型ヒントを書くことでエディタの補完・静的解析・コードの可読性が向上する。実行時に型を強制するわけではない。

## 基本の型ヒント

```python
N: int = 4
temperature: float = 0.6
model_id: str = "deepseek-ai/..."
no_save: bool = False

def calc_num_predict(N: int) -> int:
    return (2 ** N - 1) * 20

def get_prompt(self) -> str:
    return "..."

def run(N: int, trials: int = 10) -> None:   # 返り値なし
    pass
```

## コレクション型

```python
from typing import Optional   # Python 3.9 以前は typing が必要

results: list[dict] = []
pegs: list[str] = ['A', 'B', 'C']
state: dict[str, list[int]] = {'A': [4,3,2,1], 'B': [], 'C': []}
es_counts: dict[str, int] = {}
data: dict[tuple[int, float], list[dict]] = {}   # (N, T) をキーに
```

Python 3.9 以降は `list[...]`・`dict[...]`・`tuple[...]` を直接使える（`from typing import List` 不要）。

## Optional

`Optional[X]` は「`X` または `None`」を意味する。

```python
from typing import Optional

early_stop: Optional[str] = None       # str か None
output_dir: Optional[Path] = None      # Path か None

def check(reason: Optional[str]) -> None:
    if reason is not None:
        print(reason)
```

Python 3.10 以降は `str | None` と書ける（このコードでは `Optional` を使用）。

## Union（複数型）

```python
from typing import Union

value: Union[int, float] = 0.6   # int か float
# Python 3.10 以降: int | float
```

## タプルの型ヒント

```python
def load_model() -> tuple[AutoModelForCausalLM, AutoTokenizer]:
    return model, tokenizer

# 固定長タプル
coord: tuple[int, float] = (4, 0.6)
```

## `from __future__ import annotations`

```python
from __future__ import annotations
```

ファイル先頭に書くと、型ヒントの評価が遅延され、**前方参照**（まだ定義されていないクラスを型ヒントに書く）が可能になる。`run_hf.py` の先頭に記述されている。

```python
from __future__ import annotations

class Foo:
    def method(self) -> Bar:   # Bar はこの時点で未定義でもOK
        ...

class Bar:
    pass
```

## このプロジェクトでの主な型ヒント一覧

| 型 | 使用箇所 | 意味 |
|---|---|---|
| `Optional[str]` | `early_stop` フィールド | 早期終了理由（なければ None） |
| `Optional[Path]` | `output_dir` | 保存先（保存しない場合は None） |
| `Optional[EarlyStopConfig]` | `early_stop_cfg` | 早期終了設定（無効時は None） |
| `list[dict]` | `results` | 実験結果リスト |
| `dict[str, np.ndarray]` | `hidden_states` | レイヤー名→隠れ状態の辞書 |
| `dict[str, list]` | `hs_buffer` | キャプチャバッファ |
| `tuple[AutoModelForCausalLM, AutoTokenizer]` | `load_model_and_tokenizer` の返り値 | モデルとトークナイザーのペア |
