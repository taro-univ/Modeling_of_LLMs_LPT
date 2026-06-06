# 05 ファイルI/O・Pathlib・JSON

## Pathlib（パス操作）

文字列でなく `Path` オブジェクトでファイルパスを扱う。OS 差異（`/` vs `\`）を吸収してくれる。

```python
from pathlib import Path

# パスの生成
base = Path("results/hanoi")
p    = base / "N4_T0_6" / "summary.json"   # / 演算子で結合
# → results/hanoi/N4_T0_6/summary.json

# パス情報
p.parent   # results/hanoi/N4_T0_6
p.name     # summary.json
p.stem     # summary
p.suffix   # .json

# 存在確認
p.exists()        # True / False
p.is_file()
p.is_dir()

# ディレクトリ作成
p.parent.mkdir(parents=True, exist_ok=True)
# parents=True  : 中間ディレクトリも作る
# exist_ok=True : 既に存在してもエラーにしない
```

### run_hf.py でのパス解決パターン

```python
base = args.output_dir or f"results/hanoi/results_N{args.N}_hf"
output_dir = Path(base)
summary_path = output_dir / "summary.json"
meta_path    = summary_path.parent / "meta.json"
```

## ファイルの読み書き

```python
# テキスト書き込み
with open("log.txt", "w", encoding="utf-8") as f:
    f.write("hello\n")

# テキスト読み込み
with open("log.txt", "r", encoding="utf-8") as f:
    content = f.read()   # 全体を文字列で
    # または
    for line in f:       # 1行ずつ
        print(line.strip())
```

`with` ブロックを使うと、ブロック終了時に自動でファイルが閉じられる（`f.close()` 不要）。

## JSON

辞書・リストをファイルに保存・読み込みする。実験結果（`summary.json`・`meta.json`）に使用。

```python
import json

# 書き込み（dict → JSON ファイル）
meta = {"model": "deepseek-ai/...", "N": 4, "temperature": 0.6}
with open("meta.json", "w", encoding="utf-8") as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)
# ensure_ascii=False : 日本語をそのまま出力（エスケープしない）
# indent=2           : 見やすく整形

# 読み込み（JSON ファイル → dict）
with open("meta.json") as f:
    data = json.load(f)

print(data["N"])   # 4

# 文字列への変換
s = json.dumps(meta, ensure_ascii=False)

# 文字列からの変換
meta2 = json.loads(s)
```

### summary.json の保存パターン（run_hf.py）

```python
results: list[dict] = [...]   # 各試行の結果辞書のリスト

if summary_path is not None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
```

### summary.json の読み込みパターン（analyze_phase_diagram.py）

```python
path = base_dir / f"N{N}_T{tag}" / "summary.json"
if path.exists():
    with open(path) as f:
        trials: list[dict] = json.load(f)
```

## NumPy の npz（隠れ状態の保存）

複数の NumPy 配列をまとめて1ファイルに保存する形式。

```python
import numpy as np

# 保存
np.savez(
    "trial_001_hidden.npz",
    layer_m1=array1,       # キーワード引数でアレイ名を指定
    layer_m8=array2,
    move_steps=np.array([10, 25, 40]),
    move_texts=np.array(["Move 1 from A to C"], dtype=object),
)

# 読み込み
data = np.load("trial_001_hidden.npz", allow_pickle=True)
layer_m1   = data["layer_m1"]    # shape: (num_moves, hidden_size)
move_steps = data["move_steps"]
```

`**` アンパック構文で辞書を展開して渡すのが `run_hf.py` でのパターン：

```python
np.savez(
    npz_path,
    **result_gen.hidden_states,          # {"layer_m1": arr, "layer_m8": arr, ...}
    move_steps=result_gen.move_steps,
    move_texts=np.array(result_gen.move_texts, dtype=object),
)
```
