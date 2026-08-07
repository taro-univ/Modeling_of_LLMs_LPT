#!/bin/bash
# Run a small Pancake debug sweep.
#
# Usage:
#   docker compose exec hanoi-minimal bash runners/scripts/run_pancake_debug_sweep.sh
#
# Environment overrides:
#   MODEL_ID, NS, TEMPERATURES, TRIALS, NUM_PREDICT, DEVICE, SEED_BASE,
#   N_SHOT, REPETITION_PENALTY, OUTPUT_ROOT, ANALYZE, DRY_RUN, REUSE_MODEL

set -euo pipefail

MODEL_ID="${MODEL_ID:-deepseek-ai/DeepSeek-R1-Distill-Qwen-14B}"
NS="${NS:-3 4}"
TEMPERATURES="${TEMPERATURES:-0.0 0.3 0.6 0.9 1.0}"
TRIALS="${TRIALS:-5}"
NUM_PREDICT="${NUM_PREDICT:-4096}"
DEVICE="${DEVICE:-cuda:0}"
SEED_BASE="${SEED_BASE:-1}"
N_SHOT="${N_SHOT:-0}"
REPETITION_PENALTY="${REPETITION_PENALTY:-1.1}"
OUTPUT_ROOT="${OUTPUT_ROOT:-results/debug_prompt/pancake}"
ANALYZE="${ANALYZE:-1}"
DRY_RUN="${DRY_RUN:-0}"
REUSE_MODEL="${REUSE_MODEL:-1}"

model_slug() {
    echo "$1" | awk -F'/' '{print $NF}' | tr '[:upper:]' '[:lower:]'
}

temperature_label() {
    echo "$1" | tr '.' '_'
}

run_cmd() {
    if [[ "$DRY_RUN" == "1" ]]; then
        printf '[DRY-RUN]'
        printf ' %q' "$@"
        printf '\n'
    else
        "$@"
    fi
}

read -ra NS_ARRAY <<< "$NS"
read -ra TEMPERATURE_ARRAY <<< "$TEMPERATURES"
SLUG="$(model_slug "$MODEL_ID")"
BASE_DIR="${OUTPUT_ROOT}/${SLUG}"
TOTAL=$(( ${#NS_ARRAY[@]} * ${#TEMPERATURE_ARRAY[@]} * TRIALS ))
COUNT=0

echo "========================================================"
echo "  Pancake debug sweep"
echo "========================================================"
echo "  model      : ${MODEL_ID}"
echo "  output     : ${BASE_DIR}"
echo "  N          : ${NS_ARRAY[*]}"
echo "  T          : ${TEMPERATURE_ARRAY[*]}"
echo "  trials/cell: ${TRIALS}"
echo "  num_predict: ${NUM_PREDICT}"
echo "  device     : ${DEVICE}"
echo "  seed_base  : ${SEED_BASE}"
echo "  total runs : ${TOTAL}"
echo "  reuse model: ${REUSE_MODEL}"
echo "========================================================"

if [[ "$REUSE_MODEL" == "1" ]]; then
    CMD=(
        python3 runners/pancake_debug_sweep.py
        --model-id "$MODEL_ID"
        --device "$DEVICE"
        --ns "$NS"
        --temperatures "$TEMPERATURES"
        --trials "$TRIALS"
        --seed-base "$SEED_BASE"
        --num_predict "$NUM_PREDICT"
        --repetition-penalty "$REPETITION_PENALTY"
        --n-shot "$N_SHOT"
        --output-root "$OUTPUT_ROOT"
    )
    if [[ "$ANALYZE" != "1" ]]; then
        CMD+=(--no-analyze)
    fi
    run_cmd "${CMD[@]}"
    exit 0
fi

for N in "${NS_ARRAY[@]}"; do
    for T in "${TEMPERATURE_ARRAY[@]}"; do
        T_TAG="$(temperature_label "$T")"
        for TRIAL in $(seq 0 "$((TRIALS - 1))"); do
            SEED="$((SEED_BASE + TRIAL))"
            OUT_DIR="${BASE_DIR}/N${N}_seed${SEED}_np${NUM_PREDICT}_T${T_TAG}"
            DEBUG_JSON="${OUT_DIR}/debug.json"
            COUNT=$((COUNT + 1))

            echo "--------------------------------------------------------"
            echo "  [${COUNT}/${TOTAL}] N=${N} T=${T} seed=${SEED}"
            echo "  out=${OUT_DIR}"
            echo "--------------------------------------------------------"

            if [[ -f "$DEBUG_JSON" ]]; then
                echo "  [SKIP] existing ${DEBUG_JSON}"
                continue
            fi

            if [[ "$DRY_RUN" != "1" ]]; then
                mkdir -p "$OUT_DIR"
            fi
            run_cmd python3 runners/debug_prompt.py \
                --puzzle pancake \
                --N "$N" \
                --seed "$SEED" \
                --model-id "$MODEL_ID" \
                --device "$DEVICE" \
                --num_predict "$NUM_PREDICT" \
                --temperature "$T" \
                --repetition-penalty "$REPETITION_PENALTY" \
                --n-shot "$N_SHOT" \
                --output-dir "$OUT_DIR"
        done
    done
done

if [[ "$ANALYZE" == "1" ]]; then
    SUMMARY_CSV="${BASE_DIR}/pancake_debug_summary.csv"
    SUMMARY_JSON="${BASE_DIR}/pancake_debug_summary.json"
    run_cmd python3 analysis/analyze_pancake_debug.py "$BASE_DIR" \
        --csv-out "$SUMMARY_CSV" \
        --json-out "$SUMMARY_JSON"
fi
