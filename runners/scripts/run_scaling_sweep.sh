#!/bin/bash
# run_scaling_sweep.sh — スケーリング則抽出実験 (scaling_law_design.md 参照)
#
# 複数モデルで同一の (N, T) グリッドを走らせ、T_c(N, M) のスケーリング則を抽出する。
# 出力先: results/hanoi/scaling/{MODEL_TAG}/N{N}_T{T}/
#
# Usage:
#   docker compose exec hanoi-minimal bash run_scaling_sweep.sh [OPTIONS]
#
#   OPTIONS:
#     --model   MODEL_TAG   対象モデル (default: Qwen14B)
#     --trials  N           試行回数   (default: 20)
#     --ns      "2 3 4 5"  Nの範囲    (default: "2 3 4 5 6", スペース区切りで引用符必須)
#     --dry-run             コマンド表示のみ、実行しない
#
#   MODEL_TAG の選択肢:
#     Qwen14B         DeepSeek-R1-Distill-Qwen-14B    (デフォルト・最優先)
#     Llama8B         DeepSeek-R1-Distill-Llama-8B
#     Qwen1_5B        DeepSeek-R1-Distill-Qwen-1.5B
#     QwenInstruct7B  Qwen/Qwen2.5-7B-Instruct        (要コード修正・後述)
#
# 例:
#   bash run_scaling_sweep.sh --model Qwen14B --trials 30
#   bash run_scaling_sweep.sh --model Llama8B --trials 20 --ns "3 4 5"
#   bash run_scaling_sweep.sh --dry-run
#
# 注意: QwenInstruct7B は run_hf.py の <think> プリフィルが非対応のため、
#       --model-id 変更に加えて run_hf.py の think-prefill 処理を無効化してから実行すること。

set -e

# ===========================================================================
# 引数パース
# ===========================================================================

MODEL_TAG="Qwen14B"
TRIALS=20
NS_OVERRIDE=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --model)   MODEL_TAG="$2";   shift 2 ;;
        --trials)  TRIALS="$2";      shift 2 ;;
        --ns)      NS_OVERRIDE="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true;     shift   ;;
        *)
            echo "[ERROR] 不明な引数: $1"
            echo "  使用可能: --model --trials --ns --dry-run"
            exit 1
            ;;
    esac
done

# ===========================================================================
# モデル設定テーブル
# ===========================================================================

case "$MODEL_TAG" in
    Qwen14B)
        MODEL_ID="deepseek-ai/DeepSeek-R1-Distill-Qwen-14B"
        WEIGHT_GB=7.0
        KV_BYTES_PER_TOKEN=196608   # 2 × 48L × 8H_kv × 128d × 2bytes
        ;;
    Llama8B)
        MODEL_ID="deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
        WEIGHT_GB=4.0
        KV_BYTES_PER_TOKEN=131072   # 2 × 32L × 8H_kv × 128d × 2bytes
        ;;
    Qwen1_5B)
        MODEL_ID="deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"
        WEIGHT_GB=0.75
        KV_BYTES_PER_TOKEN=49152    # 2 × 28L × 2H_kv × 64d  × 2bytes (Qwen2.5-1.5B)
        ;;
    QwenInstruct7B)
        MODEL_ID="Qwen/Qwen2.5-7B-Instruct"
        WEIGHT_GB=3.5
        KV_BYTES_PER_TOKEN=114688   # 2 × 28L × 4H_kv × 128d × 2bytes
        echo "[WARNING] QwenInstruct7B は <think> プリフィル非対応モデルです。"
        echo "          run_hf.py の think-prefill 処理を無効化してから実行してください。"
        echo "          続行しますか? [y/N]"
        read -r ans
        [[ "$ans" =~ ^[Yy]$ ]] || { echo "中止しました。"; exit 1; }
        ;;
    *)
        echo "[ERROR] 不明な MODEL_TAG: $MODEL_TAG"
        echo "  使用可能: Qwen14B / Llama8B / Qwen1_5B / QwenInstruct7B"
        exit 1
        ;;
esac

# ===========================================================================
# VRAM 事前検証
# ===========================================================================

echo ""
echo "========================================================"
echo "  VRAM 事前検証  ($MODEL_TAG)"
echo "========================================================"

python3 - <<PYEOF
import subprocess, sys

weight_gb        = $WEIGHT_GB
kv_bytes_per_tok = $KV_BYTES_PER_TOKEN
model_tag        = "$MODEL_TAG"

# GPU 空き VRAM を取得
try:
    import torch
    free_bytes, total_bytes = torch.cuda.mem_get_info(0)
    free_gb  = free_bytes  / 1e9
    total_gb = total_bytes / 1e9
    print(f"  GPU VRAM : {total_gb:.1f} GB 総量 / {free_gb:.1f} GB 空き")
except Exception as e:
    print(f"  [WARN] VRAM 取得失敗: {e}")
    free_gb = 12.0
    total_gb = 12.0

print(f"  モデル重み (NF4): {weight_gb:.2f} GB")
print()
print(f"  {'S (max tokens)':>16} | {'KV (GB)':>8} | {'合計 (GB)':>10} | {'余裕':>8} | {'判定':>4}")
print("  " + "-" * 60)

safe = True
for S in [4096, 8192, 12288, 16384]:
    kv_gb   = kv_bytes_per_tok * S / 1e9
    total   = weight_gb + kv_gb
    margin  = free_gb - total
    if margin > 1.0:
        flag = "✓ OK"
    elif margin > 0:
        flag = "△ ギリギリ"
        safe = False
    else:
        flag = "✗ NG"
        safe = False
    print(f"  {S:>16,} | {kv_gb:>8.3f} | {total:>10.2f} | {margin:>+7.2f} | {flag}")

print()
if not safe:
    print("  [WARNING] 一部トークン長で VRAM が不足する可能性があります。")
    print("            --num_predict を小さくするか、N の上限を下げることを検討してください。")
else:
    print("  [OK] 全トークン長で VRAM に余裕があります。")
PYEOF

echo ""

# DRY_RUN 時は VRAM 確認のみ続行
if [[ "$DRY_RUN" == true ]]; then
    echo "[DRY-RUN] コマンドを表示するのみ。実行はしません。"
fi

# ===========================================================================
# スイープ設定
# ===========================================================================

BASE_DIR="results/hanoi/scaling/${MODEL_TAG}"

# N ごとの n-shot（experiment_design.md に準拠）
declare -A NSHOT_MAP
NSHOT_MAP[2]=1
NSHOT_MAP[3]=2
NSHOT_MAP[4]=2
NSHOT_MAP[5]=1
NSHOT_MAP[6]=1

# N ごとの num_predict
# 14B は N=4,5 で実際に解を生成しきるため、7B より余裕を持たせる
declare -A NPREDICT_MAP
if [[ "$MODEL_TAG" == "Qwen14B" ]]; then
    NPREDICT_MAP[2]=4096
    NPREDICT_MAP[3]=4096
    NPREDICT_MAP[4]=6144   # 14B が N=4 で解を生成しきるための余裕
    NPREDICT_MAP[5]=8192   # 14B が N=5 で挑戦できるための余裕
    NPREDICT_MAP[6]=12288  # N=6 解 = 63手 × ~100 tokens + reasoning
else
    NPREDICT_MAP[2]=4096
    NPREDICT_MAP[3]=4096
    NPREDICT_MAP[4]=4096
    NPREDICT_MAP[5]=4096
    NPREDICT_MAP[6]=8192
fi

# --ns 指定があればそれを使い、なければデフォルト
if [[ -n "$NS_OVERRIDE" ]]; then
    read -ra NS <<< "$NS_OVERRIDE"
else
    NS=(2 3 4 5 6)
fi
TS=(0.2 0.4 0.6 0.8 1.0 1.2 1.5 2.0)

TOTAL=$(( ${#NS[@]} * ${#TS[@]} * TRIALS ))
echo "========================================================"
echo "  Scaling Sweep  model=${MODEL_TAG}"
echo "  N       : ${NS[*]}"
echo "  T       : ${TS[*]}"
echo "  trials  : ${TRIALS} / cell"
echo "  総試行数: ${TOTAL}"
echo "========================================================"
echo ""

# ===========================================================================
# スイープ実行
# ===========================================================================

COUNT=0
CELLS=$(( ${#NS[@]} * ${#TS[@]} ))

for N in "${NS[@]}"; do
    N_SHOT=${NSHOT_MAP[$N]}
    N_PREDICT=${NPREDICT_MAP[$N]}

    for T in "${TS[@]}"; do
        COUNT=$(( COUNT + 1 ))
        T_TAG=$(echo "$T" | tr '.' '_')
        OUT_DIR="${BASE_DIR}/N${N}_T${T_TAG}"
        SUMMARY="${OUT_DIR}/summary.json"

        echo "--------------------------------------------------"
        echo "  [${COUNT}/${CELLS}] N=${N}  T=${T}  n_shot=${N_SHOT}  num_predict=${N_PREDICT}"
        echo "--------------------------------------------------"

        # 既存結果をスキップ
        if [[ -f "$SUMMARY" ]]; then
            EXISTING=$(python3 -c \
                "import json; d=json.load(open('$SUMMARY')); print(len(d))" \
                2>/dev/null || echo "0")
            if [[ "$EXISTING" -ge "$TRIALS" ]]; then
                echo "  [SKIP] 既存結果あり (trials=${EXISTING})"
                continue
            fi
        fi

        CMD="python3 runners/run_hf.py \
            --model-id    ${MODEL_ID}  \
            --N           ${N}         \
            --trials      ${TRIALS}    \
            --n-shot      ${N_SHOT}    \
            --temperature ${T}         \
            --sweep-type  scaling_sweep \
            --num_predict ${N_PREDICT} \
            --output-dir  ${OUT_DIR}   \
            --output      ${SUMMARY}"

        if [[ "$DRY_RUN" == true ]]; then
            echo "  [CMD] $CMD"
        else
            eval "$CMD"
        fi
        echo ""
    done
done

echo "========================================================"
echo "  全セル完了。スケーリング解析を実行してください:"
echo "  python3 analyze_scaling.py --model ${MODEL_TAG}"
echo "========================================================"
