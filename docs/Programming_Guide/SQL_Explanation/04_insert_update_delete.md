# 04 INSERT / UPDATE / DELETE・RETURNING

## INSERT

```sql
INSERT INTO experiments (environment, model, N, temperature, sweep_type, num_predict, num_ctx)
VALUES ('hanoi', 'deepseek-ai/DeepSeek-R1-Distill-Qwen-7B', 4, 0.8, 'phase_diagram', 6000, NULL);
```

### RETURNING：挿入した行の値を返す

`sync_one.py` で新規実験 ID を取得するために使用：

```sql
INSERT INTO experiments (environment, model, N, temperature, sweep_type, num_predict, num_ctx)
VALUES (%(environment)s, %(model)s, %(N)s, %(temperature)s, %(sweep_type)s,
        %(num_predict)s, %(num_ctx)s)
RETURNING id;
```

`RETURNING id` により、採番された `id` を INSERT 直後に取得できる（SELECT を追加発行しなくてよい）。

```python
cur.execute(INSERT_EXPERIMENT, exp_params)
experiment_id = cur.fetchone()[0]   # RETURNING で返ってきた id
```

### 複数行の一括 INSERT（execute_batch）

`sync_one.py` で全試行を一括挿入：

```sql
INSERT INTO trials (experiment_id, trial_num, accuracy, total_tokens,
                    reasoning_tokens, moves_extracted, moves_captured,
                    v_score, elapsed_sec, early_stop)
VALUES (%(experiment_id)s, %(trial_num)s, %(accuracy)s, %(total_tokens)s,
        %(reasoning_tokens)s, %(moves_extracted)s, %(moves_captured)s,
        %(v_score)s, %(elapsed_sec)s, %(early_stop)s);
```

Python 側（psycopg2）：

```python
psycopg2.extras.execute_batch(cur, INSERT_TRIAL, trial_rows)
# trial_rows は dict のリスト。通常の execute より大幅に高速。
```

## UPDATE

既存行の値を変更する。

```sql
-- N=4 の全実験に notes を追加
UPDATE experiments
SET notes = 'Layer 1 完了分'
WHERE N = 4 AND sweep_type = 'phase_diagram';

-- 特定 ID の temperature を修正
UPDATE experiments
SET temperature = 0.8
WHERE id = 12;
```

## DELETE

```sql
-- 特定実験を削除（ON DELETE CASCADE で trials も連動削除）
DELETE FROM experiments WHERE id = 12;

-- 全 pq_sweep データを削除
DELETE FROM experiments WHERE sweep_type = 'pq_sweep';
```

## 重複チェックパターン（sync_one.py の CHECK_DUPLICATE）

同じ条件の実験を二重登録しないための SELECT：

```sql
SELECT id FROM experiments
WHERE environment = %(environment)s
  AND model       = %(model)s
  AND N           = %(N)s
  AND sweep_type  = %(sweep_type)s
  AND (
        (%(temperature)s IS NULL AND temperature IS NULL)
        OR temperature = %(temperature)s
      )
LIMIT 1;
```

`temperature` が `NULL` の場合、`= NULL` は常に FALSE になるため、
`IS NULL` との組み合わせで NULL 同士の一致を正しく判定している。

```python
cur.execute(CHECK_DUPLICATE, exp_params)
row = cur.fetchone()
if row:
    print(f"skipped (id={row[0]})")
    return 0   # 既存 → スキップ
```
