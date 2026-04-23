# 02 DDL：テーブル定義（init.sql の解説）

DDL（Data Definition Language）はテーブル構造を定義・変更する SQL。

## CREATE TABLE

```sql
CREATE TABLE IF NOT EXISTS experiments (
    id           SERIAL PRIMARY KEY,
    environment  TEXT    NOT NULL,
    model        TEXT    NOT NULL,
    N            INTEGER NOT NULL,
    temperature  DOUBLE PRECISION,
    sweep_type   TEXT,
    num_predict  INTEGER,
    num_ctx      INTEGER,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    notes        TEXT
);
```

### 主な型

| 型 | 説明 | 使用カラム |
|---|---|---|
| `SERIAL` | 自動採番整数（1, 2, 3, ...） | `id` |
| `INTEGER` | 整数 | `N`, `num_predict`, `trial_num` |
| `DOUBLE PRECISION` | 倍精度浮動小数点 | `temperature` |
| `REAL` | 単精度浮動小数点 | `v_score`, `elapsed_sec` |
| `SMALLINT` | 小整数（0 or 1 の accuracy に使用） | `accuracy` |
| `TEXT` | 可変長文字列 | `model`, `environment`, `early_stop` |
| `TIMESTAMPTZ` | タイムゾーン付き日時 | `created_at` |

### 制約

```sql
id        SERIAL PRIMARY KEY      -- 主キー（一意 + NOT NULL を自動付与）
model     TEXT   NOT NULL         -- NULL 禁止
temperature DOUBLE PRECISION      -- NULL 許容（= 省略時は NULL）
created_at TIMESTAMPTZ DEFAULT NOW()  -- 挿入時に現在時刻を自動セット
```

## trials テーブル

```sql
CREATE TABLE IF NOT EXISTS trials (
    id               SERIAL PRIMARY KEY,
    experiment_id    INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    trial_num        INTEGER NOT NULL,
    accuracy         SMALLINT,
    total_tokens     INTEGER,
    reasoning_tokens INTEGER,
    moves_extracted  INTEGER,
    moves_captured   INTEGER,
    v_score          REAL,
    elapsed_sec      REAL,
    early_stop       TEXT
);
```

### REFERENCES（外部キー制約）

```sql
experiment_id INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE
```

- `REFERENCES experiments(id)` : `experiments.id` に存在する値しか入れられない
- `ON DELETE CASCADE` : 親行（experiments）を削除すると子行（trials）も自動削除
- `NOT NULL` : 必ず実験条件と紐づく必要がある

## インデックス

```sql
CREATE INDEX IF NOT EXISTS idx_trials_experiment  ON trials(experiment_id);
CREATE INDEX IF NOT EXISTS idx_experiments_lookup ON experiments(environment, N, temperature);
```

- `idx_trials_experiment` : `experiment_id` で trials を絞り込む JOIN を高速化
- `idx_experiments_lookup` : `(environment, N, temperature)` の組み合わせで重複チェック（`CHECK_DUPLICATE` クエリ）を高速化

## IF NOT EXISTS

`CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` により、`init.sql` を何度実行しても既存のテーブル・インデックスを破壊しない（冪等）。
