# 08 NumPy基礎

隠れ状態ベクトルの保存・P(q) 解析・相図描画で多用する。

## ndarray（多次元配列）

```python
import numpy as np

# 1次元配列
a = np.array([1, 2, 3, 4])        # dtype は自動推定（int64）
b = np.array([1.0, 2.0, 3.0])     # float64

# 2次元配列（行列）
m = np.array([[1, 2], [3, 4]])     # shape: (2, 2)

# 形状確認
a.shape    # (4,)
m.shape    # (2, 2)
a.dtype    # dtype('int64')
```

## 配列の生成

```python
np.zeros((3, 4))           # 3×4 のゼロ行列
np.ones((5,), dtype=float) # 長さ5の1ベクトル
np.empty((0, 4096))        # 中身未初期化（サイズだけ確保）
np.arange(0, 10, 2)        # [0, 2, 4, 6, 8]
np.linspace(0.2, 2.0, 10)  # 0.2〜2.0 を10等分
```

## インデックスとスライス

```python
hs = np.zeros((15, 4096))   # shape: (num_moves, hidden_size)

hs[0]        # 1行目（1手目の隠れ状態）
hs[-1]       # 最終行
hs[:, 0]     # 全行の0列目
hs[2:5]      # 2〜4行目
hs.shape[0]  # 行数 = num_moves
```

## 演算

```python
a = np.array([1.0, 2.0, 3.0])
b = np.array([4.0, 5.0, 6.0])

a + b               # [5., 7., 9.]   要素ごとの加算
a * b               # [4., 10., 18.] 要素ごとの乗算
a / np.linalg.norm(a)   # 正規化（単位ベクトル化）

np.dot(a, b)        # 内積 → 32.0
np.sum(a)           # 合計 → 6.0
np.mean(a)          # 平均 → 2.0
np.std(a)           # 標準偏差
```

## stack（配列を重ねる）

`run_hf.py` での隠れ状態バッファの結合：

```python
hs_buffer = []   # list of 1D array, each shape (4096,)

# 各手の隠れ状態を追加
hs_buffer.append(tensor.float().cpu().numpy())   # (4096,)

# リストを2次元配列にまとめる
hidden = np.stack(hs_buffer, axis=0)  # shape: (num_moves, 4096)
```

## dtype 指定

```python
move_steps = np.array([10, 25, 40], dtype=np.int32)
hidden     = np.empty((0, 4096), dtype=np.float32)
move_texts = np.array(["Move 1 from A to C"], dtype=object)  # 可変長文字列
```

## npz の保存と読み込み（→ 05_file_io も参照）

```python
# 保存
np.savez("trial_001.npz", layer_m1=hidden, move_steps=steps)

# 読み込み
data = np.load("trial_001.npz", allow_pickle=True)
layer_m1 = data["layer_m1"]   # shape: (num_moves, hidden_size)
```

## P(q) 解析での使い方（analyze_pq.py）

重複度（overlap）$q^{\mu\nu}$ は2試行の隠れ状態ベクトルのコサイン類似度：

$$
q^{\mu\nu} = \frac{\boldsymbol{h}^\mu \cdot \boldsymbol{h}^\nu}{|\boldsymbol{h}^\mu||\boldsymbol{h}^\nu|}
$$

```python
def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))

# 全試行ペアの overlap を計算
overlaps = []
for i in range(len(hidden_list)):
    for j in range(i + 1, len(hidden_list)):
        q = cosine(hidden_list[i], hidden_list[j])
        overlaps.append(q)

overlaps_arr = np.array(overlaps)
```
