# 06 引数・入出力・リダイレクト・Heredoc

## コマンドライン引数

```bash
bash run_scaling_sweep.sh --model Qwen14B --trials 30
#                          $1       $2       $3     $4
```

| 変数 | 値 |
|---|---|
| `$1` | `--model` |
| `$2` | `Qwen14B` |
| `$3` | `--trials` |
| `$4` | `30` |
| `$#` | `4`（引数の個数） |

## shift — 引数をずらす

```bash
while [[ $# -gt 0 ]]; do
    case "$1" in
        --model)   MODEL_TAG="$2"; shift 2 ;;
        # shift 2: $1と$2を消費。$3が新しい$1になる
        --dry-run) DRY_RUN=true;   shift   ;;
        # shift  : $1だけ消費
    esac
done
```

`shift N` で引数リストを N 個前に詰める。`while $# -gt 0` で引数がなくなるまでループ。

## read — 標準入力から読み込む

```bash
# ユーザーへの確認プロンプト（run_scaling_sweep.sh）
echo "続行しますか? [y/N]"
read -r ans
[[ "$ans" =~ ^[Yy]$ ]] || { echo "中止しました。"; exit 1; }
```

```bash
# 文字列を配列として読み込む
NS_OVERRIDE="3 4 5"
read -ra NS <<< "$NS_OVERRIDE"
# -r : バックスラッシュを文字として扱う
# -a : 配列として読み込む
# <<< : ヒアストリング（変数の内容を標準入力として渡す）

echo "${NS[@]}"   # 3 4 5
```

## リダイレクト

| 記号 | 意味 |
|---|---|
| `>` | 標準出力をファイルへ（上書き） |
| `>>` | 標準出力をファイルへ（追記） |
| `2>` | 標準エラーをファイルへ |
| `2>/dev/null` | エラーを捨てる（表示しない） |
| `<` | ファイルを標準入力として渡す |

```bash
# エラーを捨てて、コマンドが失敗したら "0" を出力
EXISTING=$(python3 -c "..." 2>/dev/null || echo "0")

# ログをファイルに保存
bash run_phase_diagram.sh >> experiment.log 2>&1
# 2>&1 : 標準エラーも標準出力と同じ場所（ファイル）へ
```

## Heredoc（ヒアドキュメント）

複数行の文字列をコマンドに渡す。`run_scaling_sweep.sh` でインライン Python を実行するために使用。

```bash
python3 - <<PYEOF
import torch
weight_gb = $WEIGHT_GB     # シェル変数が展開される
free_bytes, total_bytes = torch.cuda.mem_get_info(0)
print(f"空き VRAM: {free_bytes / 1e9:.1f} GB")
PYEOF
```

- `<<PYEOF` : `PYEOF` が単独で現れる行までを標準入力として渡す
- `python3 -` : `-` は「標準入力からスクリプトを読む」という意味
- 終了マーカー（`PYEOF`）は行の先頭に空白なしで書く

**変数展開を無効にしたい場合**（Python の `{}` と衝突するとき）：

```bash
python3 - <<'PYEOF'    # マーカーをシングルクォートで囲む
# このブロック内のシェル変数は展開されない
# Python の {変数} がそのまま渡される
PYEOF
```

## プロセス置換 `<(...)`

コマンドの出力をファイルのように扱う（`db/sync.sh`）：

```bash
while IFS= read -r -d '' meta; do
    python3 db/sync_one.py "$meta"
done < <(find results/ -name "meta.json" -print0 | sort -z)
#       ^ ^─────────────────────────────────────────────────
#       | プロセス置換: find|sort の出力を仮想ファイルとして while に渡す
#       リダイレクト: while ループの標準入力として接続

# なぜパイプ（|）を使わないか：
#   find ... | while read ... の場合、while がサブシェルで実行され
#   n_inserted などの変数が while 終了後に参照できなくなる
# → プロセス置換を使うと while が同じシェルで実行される
```
