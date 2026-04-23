# 02 データ構造：list / dict / tuple / set

## list（リスト）

順序付き・変更可能なシーケンス。

```python
disks = [4, 3, 2, 1]       # 数値リスト
pegs  = ['A', 'B', 'C']    # 文字列リスト
mixed = [1, "A", 0.6]      # 型混在も可

disks.append(0)            # 末尾に追加 → [4,3,2,1,0]
disks.pop()                # 末尾を取り出して削除 → 0、リストは [4,3,2,1]
disks[-1]                  # 末尾要素 → 1（負のインデックス）
disks[1:3]                 # スライス → [3, 2]
len(disks)                 # 要素数 → 4
```

`hanoi_env.py` では各ペグの円盤スタックをリストで表現：

```python
state = {
    'A': [4, 3, 2, 1],  # 底から順に積まれた円盤（末尾が頂上）
    'B': [],
    'C': [],
}
top_disk = state['A'][-1]   # 頂上の円盤 = 1
state['A'].pop()            # 円盤を取り出す
state['B'].append(top_disk) # 別ペグに積む
```

### リスト内包表記

```python
# for ループの簡潔な書き方
accuracies = [r["accuracy"] for r in results]
avg = sum(accuracies) / len(accuracies)

# 条件付き
passed = [r for r in results if r["accuracy"] == 1]
```

## dict（辞書）

キーと値のペア。キーで高速アクセス（O(1)）。

```python
meta = {
    "model":       "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
    "N":           4,
    "temperature": 0.6,
    "sweep_type":  "hf",
}

meta["N"]                          # 4
meta.get("n_shot", 0)              # キーがなければデフォルト値 0 を返す
meta["device"] = "cuda:0"          # キーを追加
"model" in meta                    # True（キー存在チェック）
```

### 辞書のイテレーション

```python
for key, value in meta.items():
    print(f"{key}: {value}")

for key in meta:               # キーのみ
    print(key)
```

### 辞書の集計パターン

`run_hf.py` の early_stop カウント：

```python
es_counts: dict[str, int] = {}
for r in results:
    reason = r.get("early_stop") or "none"
    es_counts[reason] = es_counts.get(reason, 0) + 1
# {"goal_reached": 7, "move_loop_repeat": 3}
```

## tuple（タプル）

順序付き・変更不可のシーケンス。関数から複数値を返すときや辞書のキーに使う。

```python
# 複数値の返却
def load_model():
    return model, tokenizer        # タプルとして返る

model, tokenizer = load_model()    # アンパック

# 辞書のキーとして使う（list はキーになれない）
data: dict[tuple[int, float], list] = {}
data[(4, 0.6)] = results           # (N, T) をキーに
```

## set（集合）

重複なし・順序なし。

```python
pegs = {'A', 'B', 'C'}
third = (pegs - {'A', 'C'}).pop()   # 'B'（残り1要素を取り出す）

# ループ検出での重複排除
unique_moves = set(generated_ids)   # 重複トークンを除いて繰り返し処理
```

## ネストした構造

実験結果は「辞書のリスト」として管理：

```python
results: list[dict] = [
    {"trial": 1, "accuracy": 1, "early_stop": "goal_reached", "total_tokens": 312},
    {"trial": 2, "accuracy": 0, "early_stop": "move_loop_repeat", "total_tokens": 1024},
]

# アクセス
results[0]["accuracy"]   # 1
results[1]["early_stop"] # "move_loop_repeat"
```
