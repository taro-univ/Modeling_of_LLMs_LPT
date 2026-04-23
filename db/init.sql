-- =============================================================================
-- experiments: 1条件セット = 1行（N, temperature, model, sweep_type など）
-- =============================================================================
CREATE TABLE IF NOT EXISTS experiments (
    id           SERIAL PRIMARY KEY,
    environment  TEXT    NOT NULL,          -- 'hanoi' など、今後拡張可
    model        TEXT    NOT NULL,          -- 'deepseek-r1:14b' など
    N            INTEGER NOT NULL,          -- 複雑度（円盤数）
    temperature  DOUBLE PRECISION,          -- サンプリング温度（NULL = モデルデフォルト）
    sweep_type   TEXT,                      -- 'temp_sweep' / 'pq_sweep' / 'main' など
    num_predict  INTEGER,                   -- 最大出力トークン数
    num_ctx      INTEGER,                   -- コンテキストウィンドウサイズ
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    notes        TEXT
);

-- =============================================================================
-- trials: 1試行 = 1行
-- =============================================================================
CREATE TABLE IF NOT EXISTS trials (
    id               SERIAL PRIMARY KEY,
    experiment_id    INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    trial_num        INTEGER NOT NULL,
    accuracy         SMALLINT,             -- 0 or 1
    total_tokens     INTEGER,
    reasoning_tokens INTEGER,
    moves_extracted  INTEGER,
    moves_captured   INTEGER,
    v_score          REAL,
    elapsed_sec      REAL,
    early_stop       TEXT                  -- NULL / 'goal_reached' / 'move_ceiling' / 'move_loop_repeat'
);

-- =============================================================================
-- インデックス
-- =============================================================================
CREATE INDEX IF NOT EXISTS idx_trials_experiment ON trials(experiment_id);
CREATE INDEX IF NOT EXISTS idx_experiments_lookup ON experiments(environment, N, temperature);
