#!/bin/bash
# run_full_sweep_v2.sh — full_sweep 再実験スクリプト（Algorithm A〜E 全込み版）
#
# 目的:
#   DeepSeek-R1-Distill-Qwen-7B の full_sweep は Algorithm E（stagnation_after_move）
#   が未実装の run_local.py で実行されたため、early_stop=None が多数存在する。
#   このスクリプトは現行の run_local.py（A〜E 全アルゴリズム）で同一グリッドを
#   再実行し、results/hanoi/full_sweep_v2/<slug>/ に保存する。
#
# 元データとの差分:
#   旧: results/hanoi/full_sweep/<slug>/          ← Algorithm D まで
#   新: results/hanoi/full_sweep_v2/<slug>/       ← Algorithm E 込み（このスクリプト）
#
# Usage（コンテナ内 /app から）:
#   bash runners/scripts/run_full_sweep_v2.sh [OPTIONS]
#
# OPTIONS:
#   --models "ID1 ID2 ..."  対象モデル（スペース区切り・引用符必須）
#                           default: "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"
#   --trials N              1セルあたりの試行数 (default: 25)
#   --ns "2 3 4 5 6"        N の範囲（スペース区切り・引用符必須）
#   --ts "0.1 0.2 ..."      温度グリッド（スペース区切り・引用符必須）
#   --analyze               スイープ完了後に解析パイプラインを自動実行
#   --dry-run               コマンドを表示するのみ・実行しない
#
# 例:
#   bash runners/scripts/run_full_sweep_v2.sh --dry-run
#   bash runners/scripts/run_full_sweep_v2.sh --analyze

set -e

# ===========================================================================
# デフォルト値
# ===========================================================================

MODELS_STR="deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"
TRIALS=25
NS_STR="2 3 4 5 6"
TS_STR="0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1.0"
N_SHOT=0
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
        --n-shot)  N_SHOT="$2";      shift 2 ;;
        --analyze) DO_ANALYZE=true;  shift   ;;
        --dry-run) DRY_RUN=true;     shift   ;;
        *)
            echo "[ERROR] 不明な引数: $1"
            echo "  使用可能: --models --trials --ns --ts --n-shot --analyze --dry-run"
            exit 1
            ;;
    esac
done

read -ra MODELS <<< "$MODELS_STR"
read -ra NS     <<< "$NS_STR"
read -ra TS     <<< "$TS_STR"

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
echo "  Full Sweep v2  (Algorithm A-E 全込み・再実験版)"
echo "========================================================"
echo "  出力ベース: results/hanoi/full_sweep_v2/"
echo "  モデル数  : ${#MODELS[@]}"
for M in "${MODELS[@]}"; do
    echo "    - $M"
done
echo "  N         : ${NS[*]}"
echo "  T         : ${TS[*]}"
echo "  n-shot    : ${N_SHOT}"
echo "  trials/セル: ${TRIALS}"
echo "  総試行数  : ${TOTAL}  (${TOTAL_PER_MODEL} × ${#MODELS[@]} モデル)"
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
    python3 /tmp/_check_vram_v2.py "$model_id"
}

cat > /tmp/_check_vram_v2.py << 'PYEOF'
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
    BASE_DIR="results/hanoi/full_sweep_v2/${SLUG}"

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
            echo "  [${COUNT}/${CELLS}]  model=${SLUG}  N=${N}  T=${T}"
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
                --model-id    ${MODEL_ID}    \
                --N           ${N}           \
                --trials      ${TRIALS}      \
                --n-shot      ${N_SHOT}      \
                --temperature ${T}           \
                --sweep-type  full_sweep     \
                --output-dir  ${OUT_DIR}     \
                --output      ${SUMMARY}"

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

        FIG_DIR="figures/full_sweep_v2/${SLUG}"
        mkdir -p "$FIG_DIR"

        python3 analysis/run_pipeline.py \
            --data-dir "$BASE_DIR"       \
            --out-dir  "$FIG_DIR"        \
            --title    "${MODEL_ID}"     \
            --analyzers phase_transition spin_glass critical_dynamics

        echo "  figures -> $FIG_DIR"
        echo ""
    fi

    echo "  完了: $SLUG"
    echo ""
done

echo "========================================================"
echo "  全モデル完了"
echo "========================================================"
echo ""
echo "  解析コマンド（--analyze を付けなかった場合）:"
for MODEL_ID in "${MODELS[@]}"; do
    SLUG=$(model_slug "$MODEL_ID")
    echo ""
    echo "  python3 analysis/run_pipeline.py \\"
    echo "      --data-dir results/hanoi/full_sweep_v2/${SLUG}/ \\"
    echo "      --out-dir  figures/full_sweep_v2/${SLUG}/ \\"
    echo "      --title    \"${MODEL_ID}\" \\"
    echo "      --analyzers phase_transition spin_glass critical_dynamics"
done
echo ""
