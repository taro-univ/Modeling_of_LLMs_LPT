# 07 正規表現（re モジュール）

LLM の出力テキストから "Move 1 from A to C" のような手を抽出するために使う。

## 基本

```python
import re

pattern = re.compile(r'Move\s+(\d+)\s+from\s+([ABC])\s+to\s+([ABC])', re.IGNORECASE)
```

- `r'...'` : raw string（`\` をエスケープとして解釈しない）
- `re.IGNORECASE` : 大文字・小文字を区別しない

## 主なメタ文字

| 記号 | 意味 | 例 |
|---|---|---|
| `\d` | 数字1文字 | `\d+` → "1", "12", "123" |
| `\s` | 空白文字（スペース・タブ・改行） | `\s+` → 1文字以上の空白 |
| `\w` | 英数字・アンダースコア | |
| `+` | 1回以上の繰り返し | `\d+` → "1", "12", ... |
| `*` | 0回以上の繰り返し | |
| `?` | 0回か1回 | |
| `.` | 任意の1文字（改行以外） | |
| `[ABC]` | A, B, C のいずれか1文字 | |
| `(...)` | グループ（マッチ結果を取り出す） | |

## re.findall（全マッチを取得）

```python
text = "Move 1 from A to C\nMove 2 from A to B\nMove 1 from C to B"

# グループなし: マッチした文字列のリスト
matches = re.findall(r'Move \d+ from [ABC] to [ABC]', text)
# ["Move 1 from A to C", "Move 2 from A to B", "Move 1 from C to B"]

# グループあり: タプルのリスト
matches = re.findall(
    r'Move\s+(\d+)\s+from\s+([ABC])\s+to\s+([ABC])',
    text, re.IGNORECASE
)
# [("1","A","C"), ("2","A","B"), ("1","C","B")]

for disk, src, dst in matches:
    print(f"disk={disk}, {src}→{dst}")
```

`hanoi_env.py` の `extract_moves_from_text` でまさにこのパターンを使用：

```python
def extract_moves_from_text(self, text: str) -> list:
    matches = re.findall(
        r'Move\s+(\d+)\s+from\s+([ABC])\s+to\s+([ABC])',
        text, re.IGNORECASE,
    )
    return [f"Move {d} from {s.upper()} to {t.upper()}" for d, s, t in matches]
```

## re.compile（パターンを事前コンパイル）

同じパターンを繰り返し使う場合、`compile` で事前にコンパイルすると速い。

```python
# モジュールレベルで1度だけコンパイル
_MOVE_RE_WITH_DISK = re.compile(
    r'Move\s+(\d+)\s+from\s+([ABC])\s+to\s+([ABC])',
    re.IGNORECASE,
)

# 繰り返し呼び出し
current_moves_full = _MOVE_RE_WITH_DISK.findall(accumulated_text)
```

## re.search（最初の1マッチを取得）

```python
m = re.search(r'Move\s+(\d+)\s+from\s+([ABC])\s+to\s+([ABC])', move_str, re.IGNORECASE)
if m:
    disk = int(m.group(1))   # 1番目のグループ
    src  = m.group(2)        # 2番目のグループ
    dst  = m.group(3)        # 3番目のグループ
```

`hanoi_env.py` の `_parse_move` で使用。

## re.match vs re.search vs re.findall

| 関数 | 動作 |
|---|---|
| `re.match` | 文字列の**先頭**にマッチするか |
| `re.search` | 文字列の**どこか**にマッチする最初の1つ |
| `re.findall` | 文字列の**すべての**マッチをリストで返す |

このプロジェクトでは `findall`（全手を取得）と `search`（1手のパース）を使い分けている。
