# 04 配列と連想配列

## 通常の配列（インデックス配列）

```bash
NS=(2 3 4 5 6)           # 配列の定義（スペース区切り）
TS=(0.2 0.4 0.6 0.8 1.0 1.2 1.5 2.0)

NS[0]    # 先頭要素 → 2（インデックスは 0 始まり）
NS[2]    # 3番目    → 4
```

### 全要素の展開

```bash
echo "${NS[@]}"          # 全要素を空白区切りで展開: 2 3 4 5 6
echo "${NS[*]}"          # 同上（"$@" と "$*" の違いと同じ）

for N in "${NS[@]}"; do  # 全要素をループ
    echo "$N"
done
```

`"${NS[@]}"` のようにダブルクォートで囲むと、要素にスペースが含まれても1要素として正しく扱われる。

### 要素数の取得

```bash
echo "${#NS[@]}"         # 要素数 → 5
CELLS=$(( ${#NS[@]} * ${#TS[@]} ))   # 5 × 8 = 40（グリッドのセル数）
```

### 配列の結合（`read -ra` による文字列からの生成）

```bash
NS_OVERRIDE="3 4 5"
read -ra NS <<< "$NS_OVERRIDE"
# NS=("3" "4" "5") として展開される
# read -ra: 配列として読み込む (-r: バックスラッシュを解釈しない)
# <<<: ヒアストリング（文字列を標準入力として渡す）
```

## 連想配列（`declare -A`）

キーに任意の文字列を使える辞書型。`run_phase_diagram.sh` や `run_scaling_sweep.sh` で N ごとの設定を管理するために使用。

```bash
declare -A NSHOT_MAP      # 連想配列の宣言（declare -A が必須）
NSHOT_MAP[2]=1
NSHOT_MAP[3]=2
NSHOT_MAP[4]=2
NSHOT_MAP[5]=1
NSHOT_MAP[6]=1

# 参照
N_SHOT=${NSHOT_MAP[$N]}   # N=4 なら N_SHOT=2
```

```bash
declare -A TS_MAP
TS_MAP[3]="0.2 0.6 1.0 1.2 1.5 2.0"
TS_MAP[4]="0.2 0.4 0.8 1.2 1.5 2.0"
TS_MAP[5]="0.2 0.4 1.0 1.5 2.0"

# 使い方：N=3 の場合のループ
for T in ${TS_MAP[$N]}; do   # TS_MAP[$N] をスペース区切りで展開
    echo "T=${T}"
done
```

### Python の dict との対応

```python
# Python
NSHOT_MAP = {2: 1, 3: 2, 4: 2, 5: 1, 6: 1}
n_shot = NSHOT_MAP[N]
```

```bash
# Bash（同等）
declare -A NSHOT_MAP
NSHOT_MAP[2]=1; NSHOT_MAP[3]=2; NSHOT_MAP[4]=2; NSHOT_MAP[5]=1; NSHOT_MAP[6]=1
N_SHOT=${NSHOT_MAP[$N]}
```

## `run_phase_diagram.sh` での実際の使い方まとめ

```bash
# N ごとの n-shot を連想配列で管理
declare -A NSHOT_MAP
NSHOT_MAP[2]=1; NSHOT_MAP[3]=2; NSHOT_MAP[4]=2; NSHOT_MAP[5]=1; NSHOT_MAP[6]=1

NS=(2 3 4 5 6)
TS=(0.2 0.4 0.6 0.8 1.0 1.2 1.5 2.0)

# グリッドの総セル数
CELLS=$(( ${#NS[@]} * ${#TS[@]} ))   # 5 × 8 = 40

COUNT=0
for N in "${NS[@]}"; do
    N_SHOT=${NSHOT_MAP[$N]}          # N に対応する n-shot を取得
    for T in "${TS[@]}"; do
        COUNT=$(( COUNT + 1 ))
        echo "[${COUNT}/${CELLS}] N=${N}  T=${T}  n_shot=${N_SHOT}"
    done
done
```
