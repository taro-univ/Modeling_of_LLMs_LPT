#!/bin/bash
# db/sync.sh — results/ 以下の meta.json を全て DB に同期する
#
# 使い方:
#   bash db/sync.sh                        # プロジェクトルートから実行
#   DATABASE_URL=postgresql://... bash db/sync.sh
#
# meta.json があるディレクトリだけが対象。
# summary.json がまだないもの（実験実行中）は waiting 扱いでスキップ。

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SYNC_ONE="${SCRIPT_DIR}/sync_one.py"
RESULTS_DIR="${ROOT_DIR}/results"

n_inserted=0
n_skipped=0
n_waiting=0
n_error=0

echo "=== db/sync.sh  $(date '+%Y-%m-%d %H:%M:%S') ==="
echo "results: ${RESULTS_DIR}"
echo ""

while IFS= read -r -d '' meta; do
    output=$(python3 "${SYNC_ONE}" "${meta}" 2>&1)
    exit_code=$?

    echo "${output}"

    case ${exit_code} in
        0)
            case ${output} in
                inserted*) (( n_inserted++ )) ;;
                skipped*)  (( n_skipped++  )) ;;
            esac
            ;;
        2) (( n_waiting++ )) ;;
        *) (( n_error++   )) ;;
    esac
done < <(find "${RESULTS_DIR}" -name "meta.json" -print0 | sort -z)

echo ""
echo "--- 結果 ---"
echo "  inserted : ${n_inserted}"
echo "  skipped  : ${n_skipped}"
echo "  waiting  : ${n_waiting}"
echo "  error    : ${n_error}"
