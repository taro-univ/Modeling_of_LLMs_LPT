#!/bin/bash
# Run a fixed-instance Pancake debug sweep while loading the model once.
#
# Required:
#   INSTANCES_FILE
#
# Optional:
#   MODEL_ID, TEMPERATURES, NUM_PREDICT, DEVICE, N_SHOT,
#   REPETITION_PENALTY, OUTPUT_ROOT, ANALYZE, DRY_RUN

set -euo pipefail

: "${INSTANCES_FILE:?INSTANCES_FILE is required}"

MODEL_ID="${MODEL_ID:-deepseek-ai/DeepSeek-R1-Distill-Qwen-14B}"
TEMPERATURES="${TEMPERATURES:-}"
NUM_PREDICT="${NUM_PREDICT:-}"
DEVICE="${DEVICE:-cuda:0}"
N_SHOT="${N_SHOT:-0}"
REPETITION_PENALTY="${REPETITION_PENALTY:-1.1}"
OUTPUT_ROOT="${OUTPUT_ROOT:-results/debug_prompt/pancake}"
ANALYZE="${ANALYZE:-1}"
DRY_RUN="${DRY_RUN:-0}"

run_cmd() {
    if [[ "$DRY_RUN" == "1" ]]; then
        printf '[DRY-RUN]'
        printf ' %q' "$@"
        printf '\n'
    else
        "$@"
    fi
}

CMD=(
    python3 runners/pancake_debug_sweep.py
    --model-id "$MODEL_ID"
    --device "$DEVICE"
    --instances-file "$INSTANCES_FILE"
    --repetition-penalty "$REPETITION_PENALTY"
    --n-shot "$N_SHOT"
    --output-root "$OUTPUT_ROOT"
)

if [[ -n "$TEMPERATURES" ]]; then
    CMD+=(--temperatures "$TEMPERATURES")
fi
if [[ -n "$NUM_PREDICT" ]]; then
    CMD+=(--num_predict "$NUM_PREDICT")
fi
if [[ "$ANALYZE" != "1" ]]; then
    CMD+=(--no-analyze)
fi

run_cmd "${CMD[@]}"
