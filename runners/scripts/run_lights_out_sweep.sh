#!/bin/bash
# run_lights_out_sweep.sh — Lights Out パズルのフルスイープ
#
# Hanoi の run_full_sweep.sh に相当するが、以下の点が異なる：
#   - --puzzle lights_out   : LightsOutEnv を使用
#   - --seed SEED           : 同一 N なら全 T で同一初期盤面を保証（公平な比較）
#   - --no-loop-detection   : Algorithm C を無効化（involution により誤検知するため）
#   - N: 3, 4, 5 のみ      : LightsOutEnv の対応サイズ
#
# 出力先: results/lights_out/<model-slug>/N{N}_T{T}/
#
# Usage:
#   docker compose exec hanoi-minimal bash runners/scripts/run_lights_out_sweep.sh [OPTIONS]
#
# OPTIONS:
#   --models "ID1 ID2 ..."  スイープするモデル ID（スペース区切り・引用符必須）
#                           (default: "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B")
#   --trials N              1セルあたりの試行数 (default: 25)
#   --ns "3 4 5"            N の範囲（LightsOutEnv は 3,4,5 のみ対応）
#   --ts "0.2 0.4 ..."      温度グリッド
#   --seed N                初期盤面シード (default: 42)
#   --analyze               スイープ完了後に解析パイプラインを自動実行
#   --dry-run               コマンドを表示するのみ・実行しない
#
# 例:
#   bash runners/scripts/run_lights_out_sweep.sh
#   bash runners/scripts/run_lights_out_sweep.sh --models "Qwen/Qwen3-7B" --dry-run

set -e

# ===========================================================================
# デフォルト値
# ===========================================================================

MODELS_STR="deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"
TRIALS=25
NS_STR="3 4 5"
TS_STR="0.2 0.4 0.6 0.8 1.0 1.2 1.5 2.0"
SEED=42
DO_ANALYZE=false
DRY_RUN=false

# ===========================================================================
# 引数パース
# ===========================================================================

while [[ $# -gt 0 ]]; do
    case "$1" in
        --models)  MODELS_STR="$2";  shift 2 ;;
        --trials)  TRIALS="$2";      shift 2 ;;
        --ns)      NS_STR="$2";      shift 2 ;;
        --ts)      TS_STR="$2";      shift 2 ;;
        --seed)    SEED="$2";        shift 2 ;;
        --analyze) DO_ANALYZE=true;  shift   ;;
        --dry-run) DRY_RUN=true;     shift   ;;
        *)
            echo "[ERROR] 不明な引数: $1"
            echo "  使用可能: --models --trials --ns --ts --seed --analyze --dry-run"
            exit 1
            ;;
    esac
done

read -ra MODELS <<< "$MODELS_STR"
read -ra NS     <<< "$NS_STR"
read -ra TS     <<< "$TS_STR"

# N の値を検証（3,4,5 のみ）
for N in "${NS[@]}"; do
    if [[ "$N" != "3" && "$N" != "4" && "$N" != "5" ]]; then
        echo "[ERROR] LightsOutEnv は N=3,4,5 のみ対応しています（指定: N=${N}）"
        exit 1
    fi
done

# ===========================================================================
# ユーティリティ
# ===========================================================================

model_slug() {
    echo "$1" | awk -F'/' '{print $NF}' | tr '[:upper:]' '[:lower:]'
}

# ===========================================================================
# 事前サマリー表示
# ===========================================================================

TOTAL_PER_MODEL=$(( ${#NS[@]} * ${#TS[@]} * TRIALS ))
TOTAL=$(( ${#MODELS[@]} * TOTAL_PER_MODEL ))

echo "========================================================"
echo "  Lights Out Sweep"
echo "========================================================"
echo "  モデル数   : ${#MODELS[@]}"
for M in "${MODELS[@]}"; do
    echo "    - $M"
done
echo "  N          : ${NS[*]}  (LightsOutEnv: 3,4,5 のみ)"
echo "  T          : ${TS[*]}"
echo "  trials/セル : ${TRIALS}"
echo "  seed       : ${SEED}  (盤面固定)"
echo "  loop検出   : 無効 (--no-loop-detection, involution のため)"
echo "  総試行数   : ${TOTAL}  (${TOTAL_PER_MODEL} × ${#MODELS[@]} モデル)"
echo "========================================================"
echo ""

if [[ "$DRY_RUN" == true ]]; then
    echo "[DRY-RUN] コマンドを表示するのみ。実行はしません。"
    echo ""
fi

# ===========================================================================
# VRAM チェック
# ===========================================================================

check_vram() {
    local model_id="$1"
    python3 /tmp/check_vram_lights_out.py "$model_id"
}

cat > /tmp/check_vram_lights_out.py << 'PYEOF'
import sys

model_id = sys.argv[1]
try:
    import torch
    free_bytes, total_bytes = torch.cuda.mem_get_info(0)
    free_gb  = free_bytes  / 1e9
    total_gb = total_bytes / 1e9
    print(f"  GPU VRAM: {total_gb:.1f} GB 総量 / {free_gb:.1f} GB 空き")
    if free_gb < 5.0:
        print(f"  [WARNING] 空き VRAM が {free_gb:.1f} GB しかありません。")
        sys.exit(1)
    else:
        print(f"  [OK] VRAM に余裕があります。")
except Exception as e:
    print(f"  [WARN] VRAM 取得失敗: {e}")
PYEOF

# ===========================================================================
# スイープ本体
# ===========================================================================

for MODEL_ID in "${MODELS[@]}"; do
    SLUG=$(model_slug "$MODEL_ID")
    BASE_DIR="results/lights_out/${SLUG}"

    echo "###################################################################"
    echo "  MODEL: $MODEL_ID"
    echo "  SLUG : $SLUG"
    echo "  出力 : $BASE_DIR"
    echo "###################################################################"
    echo ""

    if [[ "$DRY_RUN" == false ]]; then
        check_vram "$MODEL_ID" || exit 1
        echo ""
    fi

    CELLS=$(( ${#NS[@]} * ${#TS[@]} ))
    COUNT=0

    for N in "${NS[@]}"; do
        for T in "${TS[@]}"; do
            COUNT=$(( COUNT + 1 ))
            T_TAG=$(echo "$T" | tr '.' '_')
            OUT_DIR="${BASE_DIR}/N${N}_T${T_TAG}"
            SUMMARY="${OUT_DIR}/summary.json"

            echo "--------------------------------------------------"
            echo "  [${COUNT}/${CELLS}]  model=${SLUG}  N=${N}  T=${T}  seed=${SEED}"
            echo "--------------------------------------------------"

            # 既存結果をスキップ（冪等）
            if [[ -f "$SUMMARY" ]]; then
                EXISTING=$(python3 -c \
                    "import json; d=json.load(open('$SUMMARY')); print(len(d))" \
                    2>/dev/null || echo "0")
                if [[ "$EXISTING" -ge "$TRIALS" ]]; then
                    echo "  [SKIP] 既存結果あり (trials=${EXISTING})"
                    continue
                fi
            fi

            CMD="python3 runners/run_local.py \
                --model-id          ${MODEL_ID}    \
                --puzzle            lights_out     \
                --N                 ${N}           \
                --trials            ${TRIALS}      \
                --temperature       ${T}           \
                --seed              ${SEED}        \
                --no-loop-detection                \
                --n-shot            0              \
                --sweep-type        lights_out_sweep \
                --output-dir        ${OUT_DIR}     \
                --output            ${SUMMARY}"

            if [[ "$DRY_RUN" == true ]]; then
                echo "  [CMD] $CMD"
            else
                eval "$CMD"
            fi
            echo ""
        done
    done

    # ===========================================================================
    # 解析パイプライン
    # ===========================================================================

    if [[ "$DO_ANALYZE" == true && "$DRY_RUN" == false ]]; then
        echo "###################################################################"
        echo "  解析開始: $SLUG"
        echo "###################################################################"
        echo ""

        FIG_DIR="figures/lights_out_sweep/${SLUG}"
        mkdir -p "$FIG_DIR"

        python3 analysis/run_pipeline.py \
            --data-dir  "$BASE_DIR"                            \
            --out-dir   "$FIG_DIR"                             \
            --title     "${SLUG} (Lights Out)"                 \
            --ns        "${NS[@]}"                             \
            --ts        "${TS[@]}"                             \
            --analyzers phase_transition spin_glass

        echo "  → ${FIG_DIR}/"
        echo ""
    fi

    echo "  完了: $SLUG"
    echo ""
done

# ===========================================================================
# 完了メッセージ
# ===========================================================================

echo "========================================================"
echo "  全モデル完了"
echo "========================================================"
echo ""
echo "  解析コマンド（--analyze を付けなかった場合）:"
for MODEL_ID in "${MODELS[@]}"; do
    SLUG=$(model_slug "$MODEL_ID")
    BASE_DIR="results/lights_out/${SLUG}"
    FIG_DIR="figures/lights_out_sweep/${SLUG}"
    echo ""
    echo "  python3 analysis/run_pipeline.py \\"
    echo "    --data-dir ${BASE_DIR} \\"
    echo "    --out-dir  ${FIG_DIR} \\"
    echo "    --ns ${NS[*]} --ts ${TS[*]} \\"
    echo "    --analyzers phase_transition spin_glass"
done
echo ""
