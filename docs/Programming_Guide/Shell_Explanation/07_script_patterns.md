# 07 スクリプトのパターン・慣用句

## Shebang（シバン）

スクリプトの1行目に書く「このスクリプトを実行するインタープリタ」の指定。

```bash
#!/bin/bash
```

`bash run_temp_sweep.sh` のように `bash` を明示して実行する場合は不要だが、
`./run_temp_sweep.sh` と直接実行する場合に必要。

## set コマンド（エラー制御）

スクリプト冒頭の `set` はスクリプト全体の挙動を制御する。

```bash
set -e          # コマンドが失敗（終了コード非0）したら即座に終了
set -u          # 未定義変数を参照するとエラーで終了
set -o pipefail # パイプ中のどれかが失敗したら全体を失敗扱い
set -uo pipefail  # -u と pipefail を同時指定（db/sync.sh）
```

`set -e` がないと、途中でコマンドが失敗しても後続のコマンドが実行され続け、壊れた状態でデータが書かれる可能性がある。

## --dry-run パターン

実際には実行せず、実行されるコマンドだけ表示して確認するための仕組み。

```bash
DRY_RUN=false

if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "[DRY-RUN] コマンドを表示するのみ。実行はしません。"
fi

# ... スイープループ内 ...

CMD="python3 runners/run_hf.py \
    --N ${N} \
    --temperature ${T} ..."

if [[ "$DRY_RUN" == true ]]; then
    echo "  [CMD] $CMD"   # コマンドを表示するだけ
else
    eval "$CMD"           # 実際に実行
fi
```

使い方：
```bash
bash run_phase_diagram.sh --dry-run   # 確認のみ
bash run_phase_diagram.sh             # 実際に実行
```

## eval — 文字列をコマンドとして実行

```bash
CMD="python3 runners/run_hf.py --N ${N} --temperature ${T}"

eval "$CMD"   # 文字列を展開してコマンドとして実行
```

`eval` は変数展開の結果をさらにコマンドとして解釈する。コマンドを変数に組み立てておいて後で実行するパターンで使う。

**注意**：`eval` はユーザー入力をそのまま渡すとセキュリティリスクになる（スクリプト内の制御された変数にのみ使う）。

## スキップパターン（冪等性の確保）

再実行時に完了済みのセルをスキップし、途中から再開できるようにする：

```bash
SUMMARY="${OUT_DIR}/summary.json"

if [[ -f "$SUMMARY" ]]; then
    EXISTING=$(python3 -c \
        "import json; d=json.load(open('$SUMMARY')); print(len(d))" \
        2>/dev/null || echo "0")
    if [[ "$EXISTING" -ge "$TRIALS" ]]; then
        echo "  [SKIP] 既存結果あり (trials=${EXISTING})"
        continue   # for ループの次のイテレーションへ
    fi
fi
```

1. `summary.json` が存在するか確認
2. 存在する場合、試行数が目標に達しているか確認
3. 達していれば `continue` でスキップ

→ スクリプトが途中でクラッシュした場合でも `bash run_phase_diagram.sh` を再実行すれば安全に再開できる。

## 終了コードの使い分け（db/sync.sh）

```bash
while IFS= read -r -d '' meta; do
    output=$(python3 db/sync_one.py "$meta" 2>&1)
    exit_code=$?

    case ${exit_code} in
        0)
            case ${output} in
                inserted*) (( n_inserted++ )) ;;   # 先頭が "inserted"
                skipped*)  (( n_skipped++  )) ;;   # 先頭が "skipped"
            esac
            ;;
        2) (( n_waiting++ )) ;;   # sync_one.py の終了コード 2 = waiting
        *) (( n_error++   )) ;;
    esac
done < <(find ...)
```

`sync_one.py` の終了コードの設計：

| 終了コード | 意味 |
|---|---|
| `0` | 成功（inserted or skipped） |
| `2` | 待機中（summary.json 未生成） |
| `1` | エラー |

## 進捗表示のパターン

```bash
COUNT=0
CELLS=$(( ${#NS[@]} * ${#TS[@]} ))

for N in "${NS[@]}"; do
    for T in "${TS[@]}"; do
        COUNT=$(( COUNT + 1 ))
        echo "--------------------------------------------------"
        echo "  [${COUNT}/${CELLS}] N=${N}  T=${T}"
        echo "--------------------------------------------------"
    done
done
```

## まとめ：各スクリプトの構造

| スクリプト | 特徴的なパターン |
|---|---|
| `run_temp_sweep.sh` | シンプルな for ループ、`set -e` |
| `run_phase_diagram.sh` | 連想配列・ネストループ・dry-run・スキップ |
| `run_pq_sweep.sh` | N ごとに異なる T のリスト（`declare -A TS_MAP`） |
| `run_scaling_sweep.sh` | 引数パース（`while/case`）・heredoc・VRAM 検証・インタラクティブ確認 |
| `db/sync.sh` | `find -print0` + `while read -d ''`・終了コードによる集計 |
