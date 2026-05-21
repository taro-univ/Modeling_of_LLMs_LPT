#!/usr/bin/env bash
# check_gpu_memory.sh
#
# GPU の空き VRAM を確認し、閾値を下回る場合は exit 1 を返す。
# Pipeline Orchestrator が 14B モデルのロード前に呼び出す。
#
# Usage:
#   bash runners/scripts/check_gpu_memory.sh [--threshold-mib N]
#
# Options:
#   --threshold-mib N   空き VRAM の最小要件（MiB）。デフォルト: 5000
#
# Exit codes:
#   0  空き VRAM >= threshold（実行可）
#   1  空き VRAM < threshold（実行不可 or GPU 情報取得失敗）

set -euo pipefail

THRESHOLD_MIB=5000

# --- 引数パース ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --threshold-mib)
            THRESHOLD_MIB="$2"
            shift 2
            ;;
        *)
            echo "[ERROR] Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# --- nvidia-smi の存在確認 ---
if ! command -v nvidia-smi &>/dev/null; then
    echo "[ERROR] nvidia-smi not found. Cannot check GPU memory." >&2
    exit 1
fi

# --- GPU 情報取得 ---
# nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits
# → 各 GPU の空きメモリ（MiB）を 1 行ずつ出力
GPU_FREE_MIB=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null | head -n1 | tr -d '[:space:]')

if [[ -z "$GPU_FREE_MIB" ]]; then
    echo "[ERROR] Failed to retrieve GPU memory info from nvidia-smi." >&2
    exit 1
fi

echo "[INFO] GPU free memory: ${GPU_FREE_MIB} MiB / threshold: ${THRESHOLD_MIB} MiB"

# --- 閾値チェック ---
if (( GPU_FREE_MIB >= THRESHOLD_MIB )); then
    echo "[OK] Sufficient GPU memory available."
    exit 0
else
    echo "[WARN] GPU memory ${GPU_FREE_MIB} MiB < required ${THRESHOLD_MIB} MiB." >&2
    exit 1
fi
