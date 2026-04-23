#!/bin/bash
# run_pq_sweep.sh — P(q) 解析用ターゲットスイープ
#
# スピングラス相（low-T, loop_repeat）と常磁性相（high-T, no_move_catchall）の
# 境界を P(q) overlap 分布で特定するため、N=3,4,5 の各 T で 30 試行を収集する。
#
# 出力先: results/hanoi/pq_sweep/N{N}_T{T}/
#
# Usage:
#   docker compose exec hanoi-minimal bash run_pq_sweep.sh
#   docker compose exec hanoi-minimal bash run_pq_sweep.sh --dry-run

set -e

TRIALS=30
BASE_DIR="results/hanoi/pq_sweep"
DRY_RUN=false

if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "[DRY-RUN] コマンドを表示するのみ。実行はしません。"
fi

# N ごとの n-shot 設定（phase_diagram と同じ設定を踏襲）
declare -A NSHOT_MAP
NSHOT_MAP[3]=2
NSHOT_MAP[4]=2
NSHOT_MAP[5]=1

# スピングラス相 (loop_repeat 支配) → 低温側
# 常磁性相 (no_move_catchall 支配) → 高温側
# 境界付近を重点的にサンプリング
declare -A TS_MAP
TS_MAP[3]="0.2 0.6 1.0 1.2 1.5 2.0"   # N=3: 低T〜高T（境界は T~1.0-1.2 付近）
TS_MAP[4]="0.2 0.4 0.8 1.2 1.5 2.0"   # N=4: 全域崩壊だが崩壊モード遷移を捉える
TS_MAP[5]="0.2 0.4 1.0 1.5 2.0"       # N=5: spin glass (low) vs paramagnetic (high)

TOTAL=0
for N in 3 4 5; do
    for T in ${TS_MAP[$N]}; do
        TOTAL=$(( TOTAL + TRIALS ))
    done
done

echo "========================================================"
echo "  P(q) Sweep  (スピングラス vs 常磁性 境界特定)"
echo "  trials/cell: ${TRIALS}"
echo "  総試行数: ${TOTAL}"
echo "========================================================"
echo ""

for N in 3 4 5; do
    N_SHOT=${NSHOT_MAP[$N]}
    for T in ${TS_MAP[$N]}; do
        T_TAG=$(echo "$T" | tr '.' '_')
        OUT_DIR="${BASE_DIR}/N${N}_T${T_TAG}"
        SUMMARY="${OUT_DIR}/summary.json"

        echo "--------------------------------------------------"
        echo "  N=${N}  T=${T}  n_shot=${N_SHOT}  trials=${TRIALS}"
        echo "--------------------------------------------------"

        # 既存結果をスキップ
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
            --sweep-type  pq_sweep   \
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
echo "  完了。P(q) 解析を実行してください:"
echo "  python3 analyze_pq.py"
echo "========================================================"
