# 01 Python基礎：変数・型・制御フロー・関数

## 変数と基本型

```python
N = 4              # int（ディスク数）
temperature = 0.6  # float（生成温度）
model_id = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"  # str
no_save = False    # bool
```

数値演算：

```python
min_moves = (2 ** N) - 1   # べき乗は **
d_hat = min_moves / N      # 除算は常に float を返す
n = 29 // 4                # 整数除算（切り捨て）
r = 29 % 4                 # 余り
```

## 制御フロー

### if / elif / else

```python
if accuracy == 1:
    status = "PASS"
elif accuracy == 0:
    status = "FAIL"
else:
    status = "UNKNOWN"
```

### for ループ

```python
for trial in range(1, trials + 1):   # 1 から trials まで
    print(f"Trial {trial}")

for peg in ['A', 'B', 'C']:
    print(peg)
```

### while ループ

```python
step = 0
while step < num_predict:
    step += 1
```

### ループ制御

```python
for r in results:
    if r["accuracy"] == 1:
        break       # ループを即終了
    if r["early_stop"] is None:
        continue    # 次のイテレーションへスキップ
```

## 関数定義

```python
def calc_num_predict(N: int) -> int:
    """N に応じた最大出力トークン数を返す。"""
    return (2 ** N - 1) * 20

result = calc_num_predict(4)  # 300
```

- `def` で定義、`return` で値を返す
- `->` は返り値の型ヒント（省略可）
- 三重引用符 `"""..."""` はdocstring（関数の説明）

### デフォルト引数

```python
def run(N: int, trials: int = 10, temperature: float = 0.6):
    pass

run(4)               # trials=10, temperature=0.6 が使われる
run(4, trials=20)    # trials だけ上書き
```

### *args と **kwargs（可変引数）

```python
def f(*args):      # タプルとして受け取る
    print(args)    # (1, 2, 3)

def g(**kwargs):   # 辞書として受け取る
    print(kwargs)  # {'N': 4, 'T': 0.6}
```

## f-string（文字列フォーマット）

```python
N = 4
T = 0.6
print(f"N={N}  T={T:.2f}")   # N=4  T=0.60
path = f"results/hanoi/N{N}_T{T:.1f}"  # results/hanoi/N4_T0.6
tag = f"{T:.1f}".replace(".", "_")     # "0_6"
```

## None と is 演算子

```python
output_dir = None

if output_dir is None:
    print("保存しない")

if output_dir is not None:
    output_dir.mkdir(parents=True, exist_ok=True)
```

`None` は「値がない」ことを表す特別なオブジェクト。等価比較には `==` ではなく `is` を使う。
