"""
db/sync_one.py — meta.json 1件を読んで DB に同期する

終了コード:
  0  inserted  : 新規データを DB に挿入した
  0  skipped   : 既に DB に存在する（冪等）
  2  waiting   : summary.json がまだ存在しない（実験実行中）
  1  error     : それ以外のエラー

使い方:
  python3 db/sync_one.py results/hanoi/phase_diagram/N3_T0_6/meta.json
"""

import json
import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://exp_user:exp_pass@localhost:5432/experiments",
)

# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

CHECK_DUPLICATE = """
    SELECT id FROM experiments
    WHERE environment = %(environment)s
      AND model       = %(model)s
      AND N           = %(N)s
      AND sweep_type  = %(sweep_type)s
      AND (
            (%(temperature)s IS NULL AND temperature IS NULL)
            OR temperature = %(temperature)s
          )
    LIMIT 1
"""

INSERT_EXPERIMENT = """
    INSERT INTO experiments (environment, model, N, temperature, sweep_type,
                             num_predict, num_ctx)
    VALUES (%(environment)s, %(model)s, %(N)s, %(temperature)s, %(sweep_type)s,
            %(num_predict)s, %(num_ctx)s)
    RETURNING id
"""

INSERT_TRIAL = """
    INSERT INTO trials (experiment_id, trial_num, accuracy, total_tokens,
                        reasoning_tokens, moves_extracted, moves_captured,
                        v_score, elapsed_sec, early_stop)
    VALUES (%(experiment_id)s, %(trial_num)s, %(accuracy)s, %(total_tokens)s,
            %(reasoning_tokens)s, %(moves_extracted)s, %(moves_captured)s,
            %(v_score)s, %(elapsed_sec)s, %(early_stop)s)
"""

# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main(meta_path: Path) -> int:
    summary_path = meta_path.parent / "summary.json"

    if not summary_path.exists():
        print(f"waiting  {meta_path.parent.name}: summary.json がまだありません")
        return 2

    meta    = json.loads(meta_path.read_text())
    trials  = json.loads(summary_path.read_text())
    first   = trials[0] if trials else {}

    required = ("environment", "model", "N", "sweep_type")
    missing  = [k for k in required if k not in meta]
    if missing:
        print(f"error    {meta_path}: meta.json に必須キーがありません: {missing}",
              file=sys.stderr)
        return 1

    exp_params = {
        "environment": meta["environment"],
        "model":       meta["model"],
        "N":           int(meta["N"]),
        "temperature": meta.get("temperature"),   # None 許容
        "sweep_type":  meta["sweep_type"],
        "num_predict": first.get("num_predict"),
        "num_ctx":     first.get("num_ctx"),
    }

    conn = psycopg2.connect(DATABASE_URL)
    try:
        with conn:
            cur = conn.cursor()

            cur.execute(CHECK_DUPLICATE, exp_params)
            row = cur.fetchone()
            if row:
                print(f"skipped  {meta_path.parent.name} (id={row[0]})")
                return 0

            cur.execute(INSERT_EXPERIMENT, exp_params)
            experiment_id = cur.fetchone()[0]

            trial_rows = [
                {
                    "experiment_id":    experiment_id,
                    "trial_num":        t.get("trial"),
                    "accuracy":         t.get("accuracy"),
                    "total_tokens":     t.get("total_tokens"),
                    "reasoning_tokens": t.get("reasoning_tokens"),
                    "moves_extracted":  t.get("moves_extracted"),
                    "moves_captured":   t.get("moves_captured"),
                    "v_score":          t.get("v_score"),
                    "elapsed_sec":      t.get("elapsed_sec"),
                    "early_stop":       t.get("early_stop"),
                }
                for t in trials
            ]
            psycopg2.extras.execute_batch(cur, INSERT_TRIAL, trial_rows)

        print(f"inserted {meta_path.parent.name} → experiment id={experiment_id}, "
              f"{len(trial_rows)} trials")
        return 0

    except Exception as e:
        print(f"error    {meta_path.parent.name}: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <path/to/meta.json>", file=sys.stderr)
        sys.exit(1)

    sys.exit(main(Path(sys.argv[1])))
