#!/bin/bash
# run_phase_diagram.sh — 案A フルグリッドスイープ（相図描画用）
#
# N=2~6, T=0.2~2.0 の (N,T) グリッドで accuracy を測定し、
# 秩序-無秩序相図を描くためのデータを収集する。
#
# n-shot は N ごとに固定（experiment_design.md 参照）:
#   N=2 → 1,  N=3 → 2,  N=4 → 2,  N=5 → 1,  N=6 → 1
#
# Usage:
#   docker compose exec hanoi-minimal bash run_phase_diagram.sh
#   docker compose exec hanoi-minimal bash run_phase_diagram.sh --dry-run
#
# 推定所要時間: 約 2.5〜3 時間

set -e

TRIALS=10
BASE_DIR="results/hanoi/phase_diagram"
DRY_RUN=false

if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "[DRY-RUN] コマンドを表示するのみ。実行はしません。"
fi

# N ごとの n-shot 設定（実験設計書に従い固定）
declare -A NSHOT_MAP
NSHOT_MAP[2]=1
NSHOT_MAP[3]=2
NSHOT_MAP[4]=2
NSHOT_MAP[5]=1
NSHOT_MAP[6]=1

NS=(2 3 4 5 6)
TS=(0.2 0.4 0.6 0.8 1.0 1.2 1.5 2.0)

TOTAL=$(( ${#NS[@]} * ${#TS[@]} * TRIALS ))
echo "========================================================"
echo "  Phase Diagram Sweep  (案A)"
echo "  N: ${NS[*]}"
echo "  T: ${TS[*]}"
echo "  trials/cell: ${TRIALS}"
echo "  総試行数: ${TOTAL}"
echo "========================================================"
echo ""

COUNT=0
CELLS=$(( ${#NS[@]} * ${#TS[@]} ))

for N in "${NS[@]}"; do
    N_SHOT=${NSHOT_MAP[$N]}
    for T in "${TS[@]}"; do
        COUNT=$(( COUNT + 1 ))
        T_TAG=$(echo "$T" | tr '.' '_')
        OUT_DIR="${BASE_DIR}/N${N}_T${T_TAG}"
        SUMMARY="${OUT_DIR}/summary.json"

        echo "--------------------------------------------------"
        echo "  [${COUNT}/${CELLS}] N=${N}  T=${T}  n_shot=${N_SHOT}"
        echo "--------------------------------------------------"

        # 既存結果をスキップ（再実行時の継続に対応）
        if [[ -f "$SUMMARY" ]]; then
            EXISTING=$(python3 -c "import json; d=json.load(open('$SUMMARY')); print(len(d))" 2>/dev/null || echo "0")
            if [[ "$EXISTING" -ge "$TRIALS" ]]; then
                echo "  [SKIP] 既存結果あり (trials=${EXISTING})"
                continue
            fi
        fi

        CMD="python3 runners/run_hf.py \
            --N           ${N}       \
            --trials      ${TRIALS}  \
            --n-shot      ${N_SHOT}  \
            --temperature ${T}       \
            --sweep-type  phase_diagram \
            --output-dir  ${OUT_DIR} \
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
echo "  全セル完了。解析を実行してください:"
echo "  python3 analyze_phase_diagram.py"
echo "========================================================"
