# 03 SELECT：データの取得・集計・JOIN

## 基本構文

```sql
SELECT カラム名, ...
FROM テーブル名
WHERE 条件
ORDER BY カラム名 ASC|DESC
LIMIT 件数;
```

### 例：N=4 の実験条件を全件取得

```sql
SELECT id, model, N, temperature, sweep_type, created_at
FROM experiments
WHERE N = 4
ORDER BY created_at DESC;
```

### 例：特定実験の試行を全件取得

```sql
SELECT trial_num, accuracy, total_tokens, early_stop
FROM trials
WHERE experiment_id = 3
ORDER BY trial_num;
```

## WHERE の条件式

```sql
WHERE N = 4
WHERE temperature > 1.0
WHERE temperature BETWEEN 0.5 AND 1.5
WHERE early_stop IS NULL          -- NULL のチェックは = ではなく IS NULL
WHERE early_stop IS NOT NULL
WHERE early_stop = 'goal_reached'
WHERE early_stop IN ('goal_reached', 'move_loop_repeat')
WHERE model LIKE '%Qwen%'         -- 部分一致（% はワイルドカード）
WHERE N = 4 AND temperature < 1.0
WHERE N = 4 OR N = 5
```

## 集計関数

```sql
SELECT
    COUNT(*)                           AS n_trials,
    AVG(accuracy)                      AS mean_accuracy,
    SUM(accuracy)                      AS n_correct,
    AVG(total_tokens)                  AS avg_tokens,
    STDDEV(accuracy)                   AS std_accuracy
FROM trials
WHERE experiment_id = 3;
```

| 関数 | 意味 |
|---|---|
| `COUNT(*)` | 行数 |
| `AVG(col)` | 平均 |
| `SUM(col)` | 合計 |
| `MAX(col)` | 最大値 |
| `MIN(col)` | 最小値 |
| `STDDEV(col)` | 標準偏差 |

## GROUP BY：グループ集計

相図のセル `(N, T)` ごとに accuracy の平均を出す：

```sql
SELECT
    e.N,
    e.temperature,
    COUNT(t.id)       AS n_trials,
    AVG(t.accuracy)   AS mean_accuracy
FROM experiments e
JOIN trials t ON t.experiment_id = e.id
WHERE e.sweep_type = 'phase_diagram'
GROUP BY e.N, e.temperature
ORDER BY e.N, e.temperature;
```

## JOIN：テーブルの結合

`experiments` と `trials` は `experiment_id` で紐づいている。

```sql
-- INNER JOIN: 両テーブルに存在する行のみ取得
SELECT
    e.N,
    e.temperature,
    t.trial_num,
    t.accuracy,
    t.early_stop
FROM experiments e
JOIN trials t ON t.experiment_id = e.id
WHERE e.model LIKE '%Qwen-7B%'
  AND e.N = 4
ORDER BY e.temperature, t.trial_num;
```

## early_stop の内訳集計

SG相 vs 常磁性相の割合を確認するクエリ：

```sql
SELECT
    e.N,
    e.temperature,
    t.early_stop,
    COUNT(*) AS cnt
FROM experiments e
JOIN trials t ON t.experiment_id = e.id
WHERE e.sweep_type = 'phase_diagram'
GROUP BY e.N, e.temperature, t.early_stop
ORDER BY e.N, e.temperature, cnt DESC;
```

## 相境界付近の取得

$m \approx 0.5$ 近傍のセルを抽出（相境界推定）：

```sql
SELECT
    e.N,
    e.temperature,
    AVG(t.accuracy) AS m
FROM experiments e
JOIN trials t ON t.experiment_id = e.id
WHERE e.sweep_type = 'phase_diagram'
GROUP BY e.N, e.temperature
HAVING AVG(t.accuracy) BETWEEN 0.3 AND 0.7
ORDER BY e.N, e.temperature;
```

`HAVING` は `GROUP BY` 後の集計結果に対する条件（`WHERE` は集計前）。
