# 05 psycopg2：PythonからPostgreSQLを操作する

`sync_one.py` で使用しているライブラリ。

## 基本の接続〜クローズ

```python
import psycopg2

DATABASE_URL = "postgresql://exp_user:exp_pass@localhost:5432/experiments"

conn = psycopg2.connect(DATABASE_URL)
try:
    # DB 操作
    ...
finally:
    conn.close()   # 必ずクローズ
```

## カーソル

SQL を実行する窓口。`conn.cursor()` で取得する。

```python
cur = conn.cursor()

cur.execute("SELECT id, N, temperature FROM experiments WHERE N = 4")
rows = cur.fetchall()    # 全行をリストで取得: [(1, 4, 0.6), (2, 4, 0.8), ...]
row  = cur.fetchone()    # 1行だけ取得: (1, 4, 0.6)
```

## パラメータの渡し方

**SQL インジェクション対策**として、値は文字列結合でなく `%s` / `%(name)s` プレースホルダーで渡す。

```python
# 位置プレースホルダー（%s）
cur.execute("SELECT id FROM experiments WHERE N = %s AND temperature = %s", (4, 0.8))

# 名前付きプレースホルダー（%(name)s）← sync_one.py で使用
params = {"N": 4, "temperature": 0.8, "model": "deepseek-ai/..."}
cur.execute("""
    SELECT id FROM experiments
    WHERE N = %(N)s AND temperature = %(temperature)s AND model = %(model)s
""", params)
```

## トランザクション（with conn:）

`sync_one.py` の `with conn:` ブロックがトランザクションを管理している。

```python
conn = psycopg2.connect(DATABASE_URL)
try:
    with conn:                    # トランザクション開始
        cur = conn.cursor()
        cur.execute(INSERT_EXPERIMENT, exp_params)
        experiment_id = cur.fetchone()[0]
        psycopg2.extras.execute_batch(cur, INSERT_TRIAL, trial_rows)
    # with ブロックを正常終了 → COMMIT（DB に確定）
    # 例外が発生 → ROLLBACK（全て取り消し）
except Exception as e:
    print(f"error: {e}")
finally:
    conn.close()
```

- **COMMIT**：ブロック内の全変更を DB に確定する
- **ROLLBACK**：途中で例外が起きたとき、全変更を取り消す（半端なデータが残らない）

## execute_batch（一括挿入の高速化）

```python
import psycopg2.extras

trial_rows = [
    {"experiment_id": 1, "trial_num": 1, "accuracy": 1, ...},
    {"experiment_id": 1, "trial_num": 2, "accuracy": 0, ...},
    # ...
]

psycopg2.extras.execute_batch(cur, INSERT_TRIAL, trial_rows)
```

`execute_batch` は複数行を少ないラウンドトリップでまとめて送信するため、
`cur.execute()` をループするより大幅に高速。

## fetchone / fetchall の使い分け

```python
cur.execute("SELECT id FROM experiments WHERE N = 4 LIMIT 1")
row = cur.fetchone()   # None（結果なし）or タプル (id,)
if row:
    exp_id = row[0]

cur.execute("SELECT id, accuracy FROM trials WHERE experiment_id = 1")
rows = cur.fetchall()  # [(1, 1), (2, 0), ...]  空なら []
```

## よく使うエラー

| エラー | 原因 |
|---|---|
| `psycopg2.OperationalError` | 接続失敗（DB が起動していない、URL が間違い） |
| `psycopg2.IntegrityError` | 制約違反（NULL 禁止カラムに NULL、外部キー不一致など） |
| `psycopg2.ProgrammingError` | SQL 文法エラー |

```bash
# DB が起動しているか確認
docker compose ps
docker compose up -d db   # 起動していなければ起動
```
