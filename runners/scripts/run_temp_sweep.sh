#!/bin/bash
# run_temp_sweep.sh — Temperature sweep experiment (N=3, trials=10)
# Usage: bash run_temp_sweep.sh

set -e

N=3
TRIALS=10
N_SHOT=2

for T in 0.2 0.3 0.4 0.5 0.6; do
    T_TAG=$(echo $T | tr '.' '_')
    OUT_DIR="results/hanoi/temp_sweep/N${N}_T${T_TAG}"
    SUMMARY="results/hanoi/temp_sweep/N${N}_T${T_TAG}/summary.json"

    echo "=========================================="
    echo "  N=${N}  T=${T}  trials=${TRIALS}  n_shot=${N_SHOT}"
    echo "=========================================="

    python3 runners/run_local.py \
        --N           ${N}       \
        --trials      ${TRIALS}  \
        --n-shot      ${N_SHOT}  \
        --temperature ${T}       \
        --sweep-type  temp_sweep \
        --output-dir  ${OUT_DIR} \
        --output      ${SUMMARY}
done

echo ""
echo "All sweeps done. Run: python3 analysis/analyze_temp_sweep.py"
