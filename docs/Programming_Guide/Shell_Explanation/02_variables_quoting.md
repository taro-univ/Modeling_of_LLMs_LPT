# 02 変数・クォーティング

## 変数の定義と参照

```bash
N=3                           # 定義（= の前後にスペースを入れてはいけない）
TRIALS=10
BASE_DIR="results/hanoi/phase_diagram"

echo $N                       # 参照: 3
echo ${N}                     # 波括弧付き（推奨・他の文字との区切りが明確）
echo "N=${N}"                 # ダブルクォート内でも展開される: N=3
echo 'N=${N}'                 # シングルクォート内では展開されない: N=${N}
```

波括弧 `{}` は文字が続くときに必須：

```bash
OUT_DIR="results/hanoi/N${N}_T${T_TAG}"
# ${N} と ${T_TAG} を区切らないと変数名が誤認される
# $N_T_TAG → 変数名 "N_T_TAG" として解釈されてしまう（意図と違う）
```

## クォーティングの種類

| 種類 | 変数展開 | グロブ展開 | 用途 |
|---|---|---|---|
| なし | される | される | 単純な数値・英字のみのとき |
| `"..."` | される | されない | 変数を含む文字列（**通常はこちらを使う**） |
| `'...'` | されない | されない | 文字通りの文字列として扱いたいとき |

```bash
T="0.6"
T_TAG=$(echo "$T" | tr '.' '_')   # $T をダブルクォートで囲む

# 良い例
if [[ "$1" == "--dry-run" ]]; then ...   # $1 を "" で保護

# 悪い例（$1 が空のとき構文エラーになる場合がある）
if [[ $1 == "--dry-run" ]]; then ...
```

## 環境変数

シェルセッション全体で参照できる変数。`export` で子プロセスにも継承される。

```bash
export DATABASE_URL="postgresql://exp_user:exp_pass@localhost:5432/experiments"
# Python スクリプト側で os.environ.get("DATABASE_URL") として読み取れる

export PYTHONPATH=/app
```

`docker-compose.yml` の `environment:` セクションで設定されている変数は、
コンテナ起動時から自動的に環境変数として設定されている。

## 特殊変数

| 変数 | 意味 | 使用例 |
|---|---|---|
| `$0` | スクリプト自身のパス | `echo "Usage: $0 --dry-run"` |
| `$1`, `$2`, ... | コマンドライン引数 | `MODEL_TAG="$1"` |
| `$#` | 引数の個数 | `while [[ $# -gt 0 ]]` |
| `$?` | 直前のコマンドの終了コード（0=成功） | `if [[ $? -ne 0 ]]; then` |
| `$@` | 全引数（個別要素として展開） | `"$@"` |
| `$$` | 現在のシェルの PID | ログファイル名のユニーク化など |

```bash
# run_scaling_sweep.sh の引数パース部分
while [[ $# -gt 0 ]]; do        # 引数が残っている間ループ
    case "$1" in
        --model)  MODEL_TAG="$2"; shift 2 ;;   # 引数を消費して次へ
        --trials) TRIALS="$2";    shift 2 ;;
        --dry-run) DRY_RUN=true;  shift   ;;
    esac
done
```

## 変数のデフォルト値

```bash
MODEL_TAG="${MODEL_TAG:-Qwen14B}"   # MODEL_TAG が未定義か空なら Qwen14B を使う
OUT="${1:-results/default}"         # 第1引数がなければ results/default を使う
```
