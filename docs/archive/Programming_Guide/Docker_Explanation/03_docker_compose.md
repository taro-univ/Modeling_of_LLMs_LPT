# 03 Docker Compose：複数コンテナの定義と管理

`docker-compose.yml` はこのプロジェクトの全コンテナ構成を宣言的に記述するファイル。

## ファイル全体の構造

```yaml
services:        # コンテナの定義
  hanoi-minimal: # サービス名（コンテナの論理的な名前）
    ...
  db:
    ...

volumes:         # 名前付きボリュームの宣言
  pgdata:
```

## hanoi-minimal サービス

```yaml
hanoi-minimal:
  build:
    context: .           # Dockerfile を探すディレクトリ（プロジェクトルート）
    dockerfile: Dockerfile
```

`build` はイメージを DockerHub から pull するのではなく、ローカルでビルドすることを意味する。
`image:` を使う場合（`db` サービス）はビルドなしで pull する。

```yaml
  tty: true
  stdin_open: true
```

`docker compose exec hanoi-minimal bash` でインタラクティブなシェルに入れるようにする設定。
`tty: true` は疑似ターミナル確保、`stdin_open: true` は標準入力を開いたままにする。

```yaml
  environment:
    - PYTHONPATH=/app
    - OLLAMA_BASE_URL=http://host.docker.internal:11434
    - OLLAMA_HOST=http://host.docker.internal:11434
    - DATABASE_URL=postgresql://exp_user:exp_pass@db:5432/experiments
```

コンテナ内の環境変数を設定する。Python スクリプトは `os.environ.get("DATABASE_URL")` で読み取る。
`db:5432` の `db` はサービス名で、Docker の DNS がコンテナの IP に解決する（→ 05_network 参照）。

```yaml
  depends_on:
    db:
      condition: service_healthy
```

`db` コンテナが `healthy`（ヘルスチェック成功）になるまで `hanoi-minimal` の起動を待つ。
これがないと PostgreSQL が起動しきる前に Python スクリプトが接続を試みてエラーになる。

```yaml
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: all
            capabilities: [gpu]
```

GPU へのアクセスを許可する設定（→ 06_gpu_cuda 参照）。

## db サービス

```yaml
db:
  image: postgres:16-alpine
```

`alpine` ベースの軽量な PostgreSQL 16 公式イメージを使用。ビルド不要。

```yaml
  environment:
    POSTGRES_DB: experiments
    POSTGRES_USER: exp_user
    POSTGRES_PASSWORD: exp_pass
```

PostgreSQL の初期化パラメータ。コンテナ初回起動時にこのユーザー・DB が作成される。

```yaml
  volumes:
    - pgdata:/var/lib/postgresql/data    # データの永続化（named volume）
    - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql  # 初期化 SQL
```

- `pgdata:/var/lib/postgresql/data`：DB データを named volume に保存（コンテナ削除後も残る）
- `./db/init.sql:...`：PostgreSQL の慣例で、`/docker-entrypoint-initdb.d/` に置いた `.sql` は初回起動時に自動実行される → テーブルとインデックスが自動作成される

```yaml
  ports:
    - "5432:5432"
```

`"ホストのポート:コンテナのポート"` の形式。ホストの 5432 番ポートに来た接続をコンテナの 5432 に転送する。
これにより `psql postgresql://exp_user:exp_pass@localhost:5432/experiments` でホストから直接接続できる。

```yaml
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U exp_user -d experiments"]
    interval: 5s
    timeout: 5s
    retries: 5
```

5秒ごとに `pg_isready` コマンドで PostgreSQL が応答可能か確認する。
5回連続成功すると `healthy` になり、`hanoi-minimal` の起動が許可される。

## 主要な docker compose コマンド

```bash
# ビルドして起動（初回・Dockerfile 変更時）
docker compose up -d --build
# -d: バックグラウンド実行（detached）

# 起動（ビルド済みイメージを使う）
docker compose up -d

# 停止（コンテナを削除）
docker compose down

# 停止（コンテナ・ボリュームごと削除 ← DB データが消える！）
docker compose down -v

# コンテナの状態確認
docker compose ps

# ログ確認
docker compose logs hanoi-minimal
docker compose logs -f db           # リアルタイムで追う

# コンテナ内に入る
docker compose exec hanoi-minimal bash

# 特定のコマンドを実行してすぐ終了
docker compose exec hanoi-minimal python3 runners/run_hf.py --N 3

# イメージのリビルドのみ（起動しない）
docker compose build
```
