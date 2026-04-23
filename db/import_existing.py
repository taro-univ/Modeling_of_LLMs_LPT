"""
db/import_existing.py — 既存 JSON 結果を PostgreSQL へ一括取り込み

対応フォーマット:
  results/hanoi/results_NX_main.json          → sweep_type='main'
  results/hanoi/results_NX_hf/summary.json    → sweep_type='hf'
  results/hanoi/{sweep_type}/NX_TY_Z/summary.json

実行方法:
  # DB コンテナ起動後、ホストから
  python3 db/import_existing.py

  # 接続先を変える場合
  DATABASE_URL=postgresql://... python3 db/import_existing.py
"""

import json
import os
import re
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://exp_user:exp_pass@localhost:5432/experiments",
)
RESULTS_ROOT = Path(__file__).parent.parent / "results"

# sweep ディレクトリ名 → モデル対応
# main は Ollama 経由、それ以外は HuggingFace
MODEL_OLLAMA = "deepseek-r1:14b"
MODEL_HF     = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"

# ---------------------------------------------------------------------------
# パーサー
# ---------------------------------------------------------------------------

DIR_PATTERN = re.compile(r"^N(\d+)_T(\d+)_(\d+)$")  # N3_T0_3 → N=3, T=0.3


def parse_dir_name(name: str) -> tuple[int, float]:
    """'N3_T0_3' → (3, 0.3)"""
    m = DIR_PATTERN.match(name)
    if not m:
        raise ValueError(f"ディレクトリ名をパースできません: {name!r}")
    n = int(m.group(1))
    temperature = float(f"{m.group(2)}.{m.group(3)}")
    return n, temperature


def collect_sources() -> list[dict]:
    """取り込み対象ファイルの情報をすべて列挙して返す。"""
    sources = []
    hanoi = RESULTS_ROOT / "hanoi"

    # --- results_NX_main.json ---
    for p in sorted(hanoi.glob("results_N*_main.json")):
        m = re.match(r"results_N(\d+)_main\.json", p.name)
        if not m:
            continue
        sources.append({
            "path":        p,
            "environment": "hanoi",
            "model":       MODEL_OLLAMA,
            "N":           int(m.group(1)),
            "temperature": None,            # Ollama デフォルト（不明）
            "sweep_type":  "main",
        })

    # --- results_NX_hf/summary.json ---
    for p in sorted(hanoi.glob("results_N*_hf/summary.json")):
        m = re.match(r"results_N(\d+)_hf", p.parent.name)
        if not m:
            continue
        sources.append({
            "path":        p,
            "environment": "hanoi",
            "model":       MODEL_HF,
            "N":           int(m.group(1)),
            "temperature": 0.6,             # run_hf.py のデフォルト値
            "sweep_type":  "hf",
        })

    # --- {sweep_type}/NX_TY_Z/summary.json ---
    for sweep_dir in sorted(hanoi.iterdir()):
        if not sweep_dir.is_dir():
            continue
        if sweep_dir.name.startswith("results_"):
            continue
        sweep_type = sweep_dir.name  # 'temp_sweep', 'pq_sweep', 'phase_diagram'
        for cond_dir in sorted(sweep_dir.iterdir()):
            p = cond_dir / "summary.json"
            if not p.exists():
                continue
            try:
                n, temperature = parse_dir_name(cond_dir.name)
            except ValueError as e:
                print(f"  [WARN] {e}", file=sys.stderr)
                continue
            sources.append({
                "path":        p,
                "environment": "hanoi",
                "model":       MODEL_HF,
                "N":           n,
                "temperature": temperature,
                "sweep_type":  sweep_type,
            })

    return sources


# ---------------------------------------------------------------------------
# DB 操作
# ---------------------------------------------------------------------------

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


def import_source(cur, src: dict) -> tuple[int, int]:
    """1ファイルを取り込み、(experiments挿入数, trials挿入数) を返す。"""
    trials_data: list[dict] = json.loads(src["path"].read_text())

    # num_predict / num_ctx は trial[0] から代表値として取得
    first = trials_data[0] if trials_data else {}
    exp_params = {
        "environment": src["environment"],
        "model":       src["model"],
        "N":           src["N"],
        "temperature": src["temperature"],
        "sweep_type":  src["sweep_type"],
        "num_predict": first.get("num_predict"),
        "num_ctx":     first.get("num_ctx"),
    }

    # 重複チェック
    cur.execute(CHECK_DUPLICATE, exp_params)
    row = cur.fetchone()
    if row:
        print(f"  SKIP (already exists, id={row[0]}): {src['path'].relative_to(RESULTS_ROOT)}")
        return 0, 0

    # experiments INSERT
    cur.execute(INSERT_EXPERIMENT, exp_params)
    experiment_id = cur.fetchone()[0]

    # trials INSERT
    trial_rows = []
    for t in trials_data:
        trial_rows.append({
            "experiment_id":   experiment_id,
            "trial_num":       t.get("trial"),
            "accuracy":        t.get("accuracy"),
            "total_tokens":    t.get("total_tokens"),
            "reasoning_tokens": t.get("reasoning_tokens"),
            "moves_extracted": t.get("moves_extracted"),
            "moves_captured":  t.get("moves_captured"),
            "v_score":         t.get("v_score"),
            "elapsed_sec":     t.get("elapsed_sec"),
            "early_stop":      t.get("early_stop"),
        })
    psycopg2.extras.execute_batch(cur, INSERT_TRIAL, trial_rows)

    return 1, len(trial_rows)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    sources = collect_sources()
    print(f"取り込み対象: {len(sources)} ファイル")

    conn = psycopg2.connect(DATABASE_URL)
    total_exp = total_trials = 0
    try:
        with conn:
            cur = conn.cursor()
            for src in sources:
                rel = src["path"].relative_to(RESULTS_ROOT)
                print(f"  {rel}  (N={src['N']}, T={src['temperature']}, sweep={src['sweep_type']})")
                n_exp, n_tri = import_source(cur, src)
                total_exp    += n_exp
                total_trials += n_tri
    finally:
        conn.close()

    print(f"\n完了: experiments +{total_exp}, trials +{total_trials}")


if __name__ == "__main__":
    main()
