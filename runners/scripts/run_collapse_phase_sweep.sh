#!/bin/bash
# run_collapse_phase_sweep.sh — 崩壊相スイープ（SG→PM 相境界の決定）
#
# full_sweep（T=0.1〜1.0）では到達できない崩壊相内部（T=1.0〜3.0）を対象に、
# SG相（move_loop_repeat）と PM相（no_move / stagnation）の境界温度
# T_{SG→PM}(N) を決定する。
#
# 収集したデータは実験後に以下の解析スクリプトへ直接渡せる:
#   python3 analysis/analyze_phase_diagram.py --dir results/hanoi/collapse_phase/<slug>/
#   python3 analysis/analyze_pq.py            --dir results/hanoi/collapse_phase/<slug>/
#
# Usage:
#   docker compose exec hanoi-minimal bash runners/scripts/run_collapse_phase_sweep.sh [OPTIONS]
#
# OPTIONS:
#   --models "ID1 ID2 ..."  スイープするモデル ID（スペース区切り・引用符必須）
#                           (default: "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B")
#   --trials N              1セルあたりの試行数 (default: 30)
#   --ns "3 4 5"            N の範囲（スペース区切り・引用符必須）
#   --ts "1.0 1.1 ..."      温度グリッド（スペース区切り・引用符必須）
#   --analyze               スイープ完了後に解析スクリプトを自動実行
#   --dry-run               コマンドを表示するのみ・実行しない
#
# 例:
#   # デフォルトモデル（7B）で崩壊相グリッド
#   bash runners/scripts/run_collapse_phase_sweep.sh
#
#   # 内容確認のみ
#   bash runners/scripts/run_collapse_phase_sweep.sh --dry-run

set -e

# ===========================================================================
# デフォルト値
# ===========================================================================

MODELS_STR="deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"
TRIALS=30
NS_STR="3 4 5 6"
TS_STR="1.1 1.2 1.3 1.4 1.5 1.8 2.0 2.5 3.0"
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
    # "org/ModelName-Tag" → "modelname-tag"
    echo "$1" | awk -F'/' '{print $NF}' | tr '[:upper:]' '[:lower:]'
}

# ===========================================================================
# 事前サマリー表示
# ===========================================================================

TOTAL_PER_MODEL=$(( ${#NS[@]} * ${#TS[@]} * TRIALS ))
TOTAL=$(( ${#MODELS[@]} * TOTAL_PER_MODEL ))

echo "========================================================"
echo "  Full Sweep  (phase diagram + P(q) + model sweep)"
echo "========================================================"
echo "  モデル数  : ${#MODELS[@]}"
for M in "${MODELS[@]}"; do
    echo "    - $M"
done
echo "  N         : ${NS[*]}"
echo "  T         : ${TS[*]}"
echo "  n-shot    : ${N_SHOT}  (0=外部磁場なし / >0=外部磁場あり)"
echo "  trials/セル: ${TRIALS}"
echo "  総試行数  : ${TOTAL}  (${TOTAL_PER_MODEL} × ${#MODELS[@]} モデル)"
echo "========================================================"
echo ""

if [[ "$DRY_RUN" == true ]]; then
    echo "[DRY-RUN] コマンドを表示するのみ。実行はしません。"
    echo ""
fi

# ===========================================================================
# VRAM チェック（モデル実行前に確認）
# ===========================================================================

check_vram() {
    local model_id="$1"
    python3 - "$model_id" <<'PYEOF'
import sys
model_id = sys.argv[1]

try:
    import torch
    free_bytes, total_bytes = torch.cuda.mem_get_info(0)
    free_gb  = free_bytes  / 1e9
    total_gb = total_bytes / 1e9
    print(f"  GPU VRAM: {total_gb:.1f} GB 総量 / {free_gb:.1f} GB 空き")

    # 簡易判定: 空き < 5 GB は危険
    if free_gb < 5.0:
        print(f"  [WARNING] 空き VRAM が {free_gb:.1f} GB しかありません。")
        print("            他のプロセスを停止してから再実行してください。")
        sys.exit(1)
    else:
        print(f"  [OK] VRAM に余裕があります。")
except Exception as e:
    print(f"  [WARN] VRAM 取得失敗: {e}")
PYEOF
}

# ===========================================================================
# スイープ本体
# ===========================================================================

for MODEL_ID in "${MODELS[@]}"; do
    SLUG=$(model_slug "$MODEL_ID")
    BASE_DIR="results/hanoi/collapse_phase/${SLUG}"

    echo "###################################################################"
    echo "  MODEL: $MODEL_ID"
    echo "  SLUG : $SLUG"
    echo "  出力 : $BASE_DIR"
    echo "###################################################################"
    echo ""

    # VRAM チェック（dry-run 時はスキップ）
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
            echo "  [${COUNT}/${CELLS}]  model=${SLUG}  N=${N}  T=${T}  n_shot=${N_SHOT}  (h=0)"
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

            CMD="python3 runners/run_local.py \
                --model-id    ${MODEL_ID}    \
                --N           ${N}           \
                --trials      ${TRIALS}      \
                --n-shot      ${N_SHOT}      \
                --temperature ${T}           \
                --sweep-type  collapse_phase \
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
    # 解析スクリプト実行
    # ===========================================================================

    if [[ "$DO_ANALYZE" == true && "$DRY_RUN" == false ]]; then
        echo "###################################################################"
        echo "  解析開始: $SLUG"
        echo "###################################################################"
        echo ""

        FIG_DIR="figures/collapse_phase/${SLUG}"
        mkdir -p "$FIG_DIR"

        # 2相・3相相図（accuracy + early_stop 内訳）
        echo "  [1/2] 相図解析..."
        python3 analysis/analyze_phase_diagram.py \
            --dir "$BASE_DIR"                     \
            --ns  "${NS[@]}"                      \
            --ts  "${TS[@]}"                      \
            --out "${FIG_DIR}/phase_diagram.png"
        echo "  → ${FIG_DIR}/phase_diagram.png"

        # P(q) 分布・q_EA・自己相関（SG判別指標）
        echo "  [2/2] P(q) 解析..."
        python3 analysis/analyze_pq.py                       \
            --dir       "$BASE_DIR"                          \
            --ns        "${NS[@]}"                           \
            --ts        "${TS[@]}"                           \
            --out-dist  "${FIG_DIR}/pq_dist.png"             \
            --out-summary "${FIG_DIR}/pq_summary.png"
        echo "  → ${FIG_DIR}/pq_dist.png"
        echo "  → ${FIG_DIR}/pq_summary.png"

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
    BASE_DIR="results/hanoi/collapse_phase/${SLUG}"
    echo ""
    echo "  # $SLUG"
    echo "  python3 analysis/analyze_phase_diagram.py --dir $BASE_DIR --ns ${NS[*]} --ts ${TS[*]}"
    echo "  python3 analysis/analyze_pq.py            --dir $BASE_DIR --ns ${NS[*]} --ts ${TS[*]}"
done
echo ""
