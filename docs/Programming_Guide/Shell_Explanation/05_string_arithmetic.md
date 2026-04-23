# 05 文字列操作・算術展開・コマンド置換

## コマンド置換 `$(...)`

コマンドの出力を変数に代入したり、別のコマンドの引数として使う。

```bash
T_TAG=$(echo "$T" | tr '.' '_')
# echo "0.6" → "0.6"
# tr '.' '_' → "0_6"
# T_TAG="0_6"

# Python の実行結果を取得
EXISTING=$(python3 -c "import json; d=json.load(open('$SUMMARY')); print(len(d))" 2>/dev/null || echo "0")
# summary.json の試行数を取得。失敗時は "0"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# $0 : このスクリプトのパス
# dirname "$0" : スクリプトが置かれているディレクトリ
# cd ... && pwd : そのディレクトリの絶対パスを取得
```

バッククォート `` `...` `` でも同じことができるが、入れ子にできないので `$(...)` が推奨。

## 算術展開 `$(( ... ))`

整数演算を行う。

```bash
COUNT=$(( COUNT + 1 ))           # インクリメント
CELLS=$(( ${#NS[@]} * ${#TS[@]} ))  # 配列要素数の積
TOTAL=$(( 5 * 8 * TRIALS ))
REMAINING=$(( TOTAL - COUNT ))

# 演算子
$(( 10 + 3 ))   # 13（加算）
$(( 10 - 3 ))   # 7 （減算）
$(( 10 * 3 ))   # 30（乗算）
$(( 10 / 3 ))   # 3 （整数除算、切り捨て）
$(( 10 % 3 ))   # 1 （余り）
$(( 2 ** 4 ))   # 16（べき乗）
```

`$(( ))` 内では `$` なしで変数名を使えるが、`${#NS[@]}` のような特殊展開は `${}` が必要。

## 文字列の長さ

```bash
echo "${#MODEL_TAG}"   # MODEL_TAG の文字数
```

## パイプ `|`

左側のコマンドの標準出力を、右側のコマンドの標準入力に渡す。

```bash
echo "0.6" | tr '.' '_'
# echo が "0.6\n" を出力 → tr が "0_6\n" に変換

find results/ -name "meta.json" -print0 | sort -z
# find の出力（null区切りパス一覧）を sort に渡して並び替え
```

## while + read + find の組み合わせ（db/sync.sh）

```bash
while IFS= read -r -d '' meta; do
    python3 db/sync_one.py "$meta"
done < <(find results/ -name "meta.json" -print0 | sort -z)
```

分解して理解する：

| 部分 | 意味 |
|---|---|
| `find ... -print0` | パスを null 区切りで出力（スペース含むパス対応） |
| `sort -z` | null 区切りのまま並び替え |
| `< <(...)` | プロセス置換：`(...)` の出力をファイルとして while に渡す |
| `IFS=` | IFS（区切り文字）を空にして行頭・行末の空白を保持 |
| `read -r` | バックスラッシュを特殊文字として解釈しない |
| `read -d ''` | null 文字を区切りとして読み込む（`-print0` と対応） |

## 複数行コマンド（バックスラッシュ改行）

長いコマンドを読みやすく折り返す：

```bash
python3 runners/run_hf.py \
    --N           ${N}       \
    --trials      ${TRIALS}  \
    --n-shot      ${N_SHOT}  \
    --temperature ${T}       \
    --sweep-type  phase_diagram \
    --output-dir  ${OUT_DIR} \
    --output      ${SUMMARY}
# \ の後に空白・コメントを入れてはいけない
```

## 終了コード

コマンドが成功したかどうかを示す整数（0=成功、0以外=失敗）。

```bash
python3 db/sync_one.py "$meta"
exit_code=$?   # $? で直前のコマンドの終了コードを取得

case ${exit_code} in
    0) echo "OK" ;;
    2) echo "waiting" ;;
    *) echo "error" ;;
esac
```

```bash
# || : 左が失敗したとき右を実行
python3 -c "import json; ..." 2>/dev/null || echo "0"
# python3 が失敗（終了コード非0）したら "0" を出力

# && : 左が成功したとき右を実行
cd "$(dirname "$0")" && pwd
```
