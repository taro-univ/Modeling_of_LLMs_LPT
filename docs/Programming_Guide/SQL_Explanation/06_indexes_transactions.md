# 06 インデックスとトランザクション

## インデックス

テーブルの特定カラムに作る「索引」。WHERE や JOIN の検索を高速化する。

### なぜ必要か

インデックスなしの場合、`WHERE experiment_id = 3` を評価するために trials テーブルの**全行を順番にスキャン**する（シーケンシャルスキャン）。trials が数万行になるとここがボトルネックになる。

```sql
-- インデックスなし: O(N) のフルスキャン
SELECT * FROM trials WHERE experiment_id = 3;

-- インデックスあり: O(log N) のインデックススキャン
CREATE INDEX IF NOT EXISTS idx_trials_experiment ON trials(experiment_id);
```

### このプロジェクトのインデックス

```sql
-- trials.experiment_id: JOIN 時に頻繁に使う
CREATE INDEX IF NOT EXISTS idx_trials_experiment
    ON trials(experiment_id);

-- (environment, N, temperature): CHECK_DUPLICATE クエリの WHERE 句に対応
CREATE INDEX IF NOT EXISTS idx_experiments_lookup
    ON experiments(environment, N, temperature);
```

複合インデックス `(environment, N, temperature)` は、左端のカラムから順に使われる。
`WHERE environment = 'hanoi' AND N = 4` のような部分的な条件でも有効。

### インデックスの確認

```sql
-- テーブルのインデックス一覧
\d experiments
\d trials

-- または
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'trials';
```

## トランザクション

複数の SQL 操作を「全て成功」か「全て取り消し」にまとめる仕組み。

### 概念

```
BEGIN
  INSERT INTO experiments ...   ← これが成功しても
  INSERT INTO trials ...        ← これが失敗したら
ROLLBACK                        ← 両方取り消し（中途半端な状態にしない）

BEGIN
  INSERT INTO experiments ...   ← 成功
  INSERT INTO trials ...        ← 成功
COMMIT                          ← 両方確定
```

### psycopg2 での実装（sync_one.py）

```python
with conn:                          # BEGIN
    cur = conn.cursor()
    cur.execute(INSERT_EXPERIMENT, exp_params)
    experiment_id = cur.fetchone()[0]

    psycopg2.extras.execute_batch(cur, INSERT_TRIAL, trial_rows)
# 正常終了 → COMMIT
# 例外発生 → ROLLBACK
```

これにより、`experiments` の挿入は成功したが `trials` の挿入が途中で失敗した場合でも、`experiments` の行は残らない。

### 手動での COMMIT / ROLLBACK（psql 操作時）

```sql
BEGIN;

INSERT INTO experiments (environment, model, N, temperature, sweep_type)
VALUES ('hanoi', 'test-model', 3, 0.6, 'test');

-- ここで内容を確認してから決める
SELECT * FROM experiments ORDER BY id DESC LIMIT 3;

COMMIT;    -- 確定
-- または
ROLLBACK;  -- 取り消し
```

psql はデフォルトで **autocommit オフ**（明示的に COMMIT が必要）。
psycopg2 はデフォルトで autocommit オフ（`with conn:` か明示的な `conn.commit()` が必要）。

## EXPLAIN（クエリの実行計画）

重いクエリのボトルネックを調べるときに使う。

```sql
EXPLAIN ANALYZE
SELECT e.N, e.temperature, AVG(t.accuracy)
FROM experiments e
JOIN trials t ON t.experiment_id = e.id
WHERE e.sweep_type = 'phase_diagram'
GROUP BY e.N, e.temperature;
```

出力例：
```
Index Scan using idx_trials_experiment on trials t  (cost=...)
  → インデックスが使われていれば OK
Seq Scan on experiments e
  → フルスキャン（件数が少なければ問題なし）
```
