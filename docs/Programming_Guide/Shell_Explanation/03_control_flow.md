# 03 制御フロー：if / for / case・条件式

## if 文

```bash
if [[ 条件 ]]; then
    # 真のとき
elif [[ 別の条件 ]]; then
    # 別条件が真のとき
else
    # それ以外
fi
```

### よく使う条件式

**文字列の比較**

```bash
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
fi

if [[ "$DRY_RUN" == true ]]; then
    echo "[DRY-RUN]"
else
    eval "$CMD"
fi

if [[ -n "$NS_OVERRIDE" ]]; then    # -n: 文字列が空でない
    read -ra NS <<< "$NS_OVERRIDE"
fi

if [[ -z "$MODEL_TAG" ]]; then      # -z: 文字列が空
    echo "MODEL_TAG is required"
fi
```

**数値の比較**

| 演算子 | 意味 |
|---|---|
| `-eq` | equal (==) |
| `-ne` | not equal (!=) |
| `-ge` | greater or equal (>=) |
| `-gt` | greater than (>) |
| `-le` | less or equal (<=) |
| `-lt` | less than (<) |

```bash
if [[ "$EXISTING" -ge "$TRIALS" ]]; then
    echo "[SKIP] 既存結果あり (trials=${EXISTING})"
    continue
fi

if [[ $# -gt 0 ]]; then   # 引数が1つ以上あるとき
    ...
fi
```

**ファイル・ディレクトリの存在確認**

```bash
if [[ -f "$SUMMARY" ]]; then        # -f: ファイルが存在する
    echo "summary.json found"
fi

if [[ -d "$BASE_DIR" ]]; then       # -d: ディレクトリが存在する
    echo "directory exists"
fi
```

**論理演算**

```bash
if [[ -f "$SUMMARY" ]] && [[ "$EXISTING" -ge "$TRIALS" ]]; then
    continue
fi

if [[ "$MODEL_TAG" == "Qwen14B" ]] || [[ "$MODEL_TAG" == "Llama8B" ]]; then
    echo "supported"
fi
```

**正規表現マッチ**

```bash
if [[ "$ans" =~ ^[Yy]$ ]]; then    # =~: 正規表現マッチ
    echo "Yes"
fi
# ^[Yy]$ : 先頭から末尾まで Y か y の1文字
```

## for ループ

```bash
# 値のリストでループ（run_temp_sweep.sh）
for T in 0.2 0.3 0.4 0.5 0.6; do
    echo "T=${T}"
done

# 配列でループ（run_phase_diagram.sh）
NS=(2 3 4 5 6)
for N in "${NS[@]}"; do
    echo "N=${N}"
done

# ネストしたループ（相図のグリッドスイープ）
for N in "${NS[@]}"; do
    for T in "${TS[@]}"; do
        # (N, T) のセルごとに実験を実行
    done
done
```

`continue` でループの残りをスキップ、`break` でループを終了：

```bash
for N in "${NS[@]}"; do
    if [[ -f "$SUMMARY" ]] && [[ "$EXISTING" -ge "$TRIALS" ]]; then
        echo "  [SKIP]"
        continue          # 次の N へ
    fi
    # 実験実行
done
```

## case 文

`if-elif` の連鎖より読みやすい、複数パターンの分岐。`run_scaling_sweep.sh` のモデル設定テーブル：

```bash
case "$MODEL_TAG" in
    Qwen14B)
        MODEL_ID="deepseek-ai/DeepSeek-R1-Distill-Qwen-14B"
        WEIGHT_GB=7.0
        ;;          # このパターンの終わり（;;で次のパターンへ進まない）
    Llama8B)
        MODEL_ID="deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
        WEIGHT_GB=4.0
        ;;
    *)              # どれにもマッチしないとき（デフォルト）
        echo "[ERROR] 不明な MODEL_TAG: $MODEL_TAG"
        exit 1
        ;;
esac
```

引数パースでも使用：

```bash
while [[ $# -gt 0 ]]; do
    case "$1" in
        --model)   MODEL_TAG="$2"; shift 2 ;;
        --trials)  TRIALS="$2";    shift 2 ;;
        --dry-run) DRY_RUN=true;   shift   ;;
        *)
            echo "[ERROR] 不明な引数: $1"
            exit 1
            ;;
    esac
done
```
