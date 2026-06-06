# 05 ネットワーク：コンテナ間通信と外部接続

このプロジェクトには3つの通信経路がある。それぞれの仕組みを詳細に解説する。

## Docker ネットワークの基本

Docker Compose でサービスを定義すると、**同名プロジェクトのサービスは自動的に同一ブリッジネットワークに接続される**。

```bash
# このプロジェクトのネットワーク確認
docker network inspect modeling_of_llms_lpt_default
```

実際の構成（`docker inspect` の結果より）：

```
ネットワーク名: modeling_of_llms_lpt_default
ドライバ: bridge

コンテナ:
  hanoi-minimal   IP: 172.21.0.3/16
  db              IP: 172.21.0.2/16
```

ブリッジネットワークは Docker が管理する仮想スイッチ。同じネットワーク内のコンテナは互いに通信できる。

## 通信経路①：hanoi-minimal → db（SQL接続）

```
hanoi-minimal コンテナ
  sync_one.py
    psycopg2.connect("postgresql://exp_user:exp_pass@db:5432/experiments")
                                                        ↑
                                               サービス名 "db" をホスト名として使う
```

**DNS 解決の仕組み：**

Docker Compose の内蔵 DNS サーバーが `db` というホスト名を `172.21.0.2`（db コンテナの IP）に解決する。IP アドレスはコンテナ再起動のたびに変わる可能性があるが、サービス名 `db` は常に正しい IP を返す。

```
sync_one.py
  → "db" を DNS に問い合わせ
  → Docker 内蔵 DNS が 172.21.0.2 を返す
  → TCP:5432 で PostgreSQL に接続
  → SQL を実行
```

**なぜ `localhost:5432` ではなく `db:5432` か：**
コンテナ内から見た `localhost` は `hanoi-minimal` コンテナ自身を指す。PostgreSQL は別コンテナ（`db`）で動いているため、サービス名 `db` を使う必要がある。

**ホスト側からの接続：**

```yaml
db:
  ports:
    - "5432:5432"   # ホストの 5432 → db コンテナの 5432 に転送
```

このポートマッピングにより、ホスト（WSL2）からは `localhost:5432` で接続できる：

```bash
# ホスト側から
psql postgresql://exp_user:exp_pass@localhost:5432/experiments
```

## 通信経路②：hanoi-minimal → WSL2ホスト上の Ollama

```
hanoi-minimal コンテナ
  run.py (Ollama API 版)
    requests.post("http://host.docker.internal:11434/api/generate")
                           ↑
                   WSL2 ホストの IP を指す特別なホスト名
```

**`host.docker.internal` の仕組み：**

通常、コンテナからホストマシンへの通信は特別な設定が必要。`host.docker.internal` はホストのゲートウェイ IP を自動的に解決するために Docker が提供する特別なホスト名。

しかし **Linux（WSL2含む）では `host.docker.internal` が自動では設定されない**。
そのため `docker-compose.yml` で明示的に追加している：

```yaml
hanoi-minimal:
  extra_hosts:
    - "host.docker.internal:host-gateway"
    # host-gateway は Docker が自動で検出したホストの IP に解決される
    # → 実際は 172.21.0.1（ブリッジネットワークのゲートウェイ）に解決される
```

```
hanoi-minimal (172.21.0.3)
  → "host.docker.internal" を DNS に問い合わせ
  → extra_hosts により 172.21.0.1（ゲートウェイ）に解決
  → ゲートウェイ経由でホスト（WSL2）の Ollama (127.0.0.1:11434) に到達
```

**ネットワーク経路の全体像：**

```
hanoi-minimal コンテナ (172.21.0.3)
    │
    │ host.docker.internal → 172.21.0.1
    ▼
ブリッジネットワーク ゲートウェイ (172.21.0.1)
    │
    │ NAT（ネットワークアドレス変換）
    ▼
WSL2 ホスト (127.0.0.1)
    └── Ollama サーバー (127.0.0.1:11434)
```

## 通信経路③：WSL2 ↔ Windows ホスト

WSL2 自体も仮想化環境であり、Windows と WSL2 間にも仮想ネットワークがある。

```
Windows ホスト
    │
    │ (仮想ネットワーク)
    ▼
WSL2 カーネル
    │
    │ (Dockerブリッジ)
    ▼
Docker コンテナ群
  ├── hanoi-minimal (172.21.0.3)
  └── db (172.21.0.2)
```

GPU は WSL2 から Docker コンテナに直接渡される（NVIDIA Container Toolkit経由、→ 06_gpu_cuda 参照）。

## 通信経路のまとめ

| 通信 | ホスト名 | ポート | 経路 |
|---|---|---|---|
| hanoi-minimal → db | `db` | `5432` | Docker 内蔵 DNS + ブリッジ |
| hanoi-minimal → Ollama | `host.docker.internal` | `11434` | extra_hosts + ゲートウェイ |
| ホスト → db | `localhost` | `5432` | ポートマッピング (5432:5432) |

## 環境変数による接続先の切り替え

`DATABASE_URL` を環境変数にしているのは、接続先を変えたいときにコードを修正しなくて済むようにするため：

```yaml
# docker-compose.yml（コンテナ内）
environment:
  - DATABASE_URL=postgresql://exp_user:exp_pass@db:5432/experiments
#                                                ^^
#                                         サービス名でアクセス
```

```bash
# ホスト側から直接 sync.sh を実行する場合
DATABASE_URL=postgresql://exp_user:exp_pass@localhost:5432/experiments bash db/sync.sh
#                                                       ^^^^^^^^^
#                                                  localhost でアクセス
```

```python
# sync_one.py
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://exp_user:exp_pass@localhost:5432/experiments",  # フォールバック
)
```

コンテナ内からは `db:5432`、ホストからは `localhost:5432`。コードは変えず環境変数だけ切り替える。

## ネットワークのトラブルシューティング

```bash
# コンテナ同士が通信できるか確認
docker compose exec hanoi-minimal ping db

# db コンテナへの接続テスト
docker compose exec hanoi-minimal python3 -c "
import psycopg2, os
conn = psycopg2.connect(os.environ['DATABASE_URL'])
print('接続成功')
conn.close()
"

# ポートが開いているか確認（ホスト側）
curl -s http://localhost:11434/api/tags   # Ollama が応答するか

# ネットワーク設定の確認
docker network inspect modeling_of_llms_lpt_default
```
