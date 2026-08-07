#!/bin/bash
# Run the roadmap Pancake min_moves-stratified sweep.
#
# This is the concrete launcher for:
#   docs/research_state/roadmap_2026_09_conference.md section 6.1
#   docs/research_state/pancake_stratified_sweep_spec.md
#
# Usage inside the container:
#   bash runners/scripts/run_pancake_minmoves_stratified_sweep.sh
#
# Dry run:
#   DRY_RUN=1 bash runners/scripts/run_pancake_minmoves_stratified_sweep.sh
#
# Optional overrides:
#   MODEL_ID, INSTANCES_FILE, TEMPERATURES, NUM_PREDICT, DEVICE, N_SHOT,
#   REPETITION_PENALTY, OUTPUT_ROOT, ANALYZE, DRY_RUN

set -euo pipefail

DEFAULT_INSTANCES_FILE="configs/pancake_instances/N3-5_T0_6_minmoves_stratified_v1.json"

export INSTANCES_FILE="${INSTANCES_FILE:-$DEFAULT_INSTANCES_FILE}"
export TEMPERATURES="${TEMPERATURES:-0.6}"
export NUM_PREDICT="${NUM_PREDICT:-8192}"
export OUTPUT_ROOT="${OUTPUT_ROOT:-results/debug_prompt/pancake/minmoves_stratified}"
export ANALYZE="${ANALYZE:-1}"
export DRY_RUN="${DRY_RUN:-0}"

if [[ ! -f "$INSTANCES_FILE" ]]; then
    echo "[ERROR] INSTANCES_FILE not found: $INSTANCES_FILE" >&2
    echo "Generate or restore the stratified instances file first." >&2
    exit 1
fi

echo "========================================================"
echo "  Pancake min_moves-stratified sweep"
echo "========================================================"
echo "  instances : ${INSTANCES_FILE}"
echo "  T         : ${TEMPERATURES}"
echo "  num_predict: ${NUM_PREDICT}"
echo "  output_root: ${OUTPUT_ROOT}"
echo "  analyze   : ${ANALYZE}"
echo "  dry_run   : ${DRY_RUN}"
echo "========================================================"

bash runners/scripts/run_pancake_debug_stratified_sweep.sh
