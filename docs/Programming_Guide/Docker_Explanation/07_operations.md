# 07 日常操作・ログ確認・トラブルシューティング

## 日常の操作フロー

### 実験開始

```bash
# プロジェクトルートで
cd /home/shona/Modeling_of_LLMs_LPT

# 初回 or Dockerfile/requirements.txt を変更した場合
docker compose up -d --build

# 2回目以降（コードのみ変更した場合）
docker compose up -d          # コンテナが停止していた場合

# コンテナに入る
docker compose exec hanoi-minimal bash
```

### 実験実行（コンテナ内）

```bash
# コンテナ内に入らずにコマンドを実行する方法
docker compose exec hanoi-minimal bash runners/scripts/run_phase_diagram.sh
docker compose exec hanoi-minimal python3 runners/run_hf.py --N 4 --dry-run
```

### 実験終了後

```bash
# DB に結果を同期（コンテナ内から）
bash db/sync.sh

# コンテナを停止（データは残る）
docker compose down

# または起動したまま放置でもOK（db は常時稼働）
```

## ログの確認

```bash
# サービスのログを見る
docker compose logs hanoi-minimal     # 全ログ
docker compose logs -f hanoi-minimal  # リアルタイムで追う（Ctrl+C で終了）
docker compose logs --tail=50 db      # 最後の50行だけ

# コンテナ内で直接コマンドを実行してログを確認
docker compose exec hanoi-minimal nvidia-smi
docker compose exec db pg_isready -U exp_user -d experiments
```

## コンテナの状態確認

```bash
docker compose ps
# NAME                                    IMAGE   STATUS          PORTS
# modeling_of_llms_lpt-db-1              ...     Up (healthy)    0.0.0.0:5432->5432/tcp
# modeling_of_llms_lpt-hanoi-minimal-1   ...     Up

# 詳細な情報
docker inspect modeling_of_llms_lpt-hanoi-minimal-1
```

`STATUS` の見方：
| 表示 | 意味 |
|---|---|
| `Up` | 稼働中 |
| `Up (healthy)` | 稼働中でヘルスチェック成功 |
| `Up (unhealthy)` | 稼働中だがヘルスチェック失敗（DB の起動待ちなど） |
| `Exited (0)` | 正常終了（コマンドが完了した） |
| `Exited (1)` | エラーで終了 |

## よくあるトラブルと対処

### GPU が認識されない

```bash
docker compose exec hanoi-minimal python3 -c "import torch; print(torch.cuda.is_available())"
# False → GPU が使えていない

# 原因の調査
nvidia-smi                     # ホスト側でドライバが動いているか
docker compose exec hanoi-minimal nvidia-smi  # コンテナに GPU が渡されているか
```

対処：
1. NVIDIA Container Toolkit がインストールされているか確認
2. `docker-compose.yml` の `deploy.resources.reservations.devices` の記述を確認
3. Docker デーモンを再起動: `sudo systemctl restart docker`

---

### DB に接続できない

```bash
docker compose ps  # db が healthy か確認
docker compose logs db  # PostgreSQL のエラーログを確認
```

対処：
1. `db` が `(healthy)` になるまで待つ（起動直後は `(starting)` や `(unhealthy)` のことがある）
2. `docker compose restart db` で再起動
3. `docker compose down && docker compose up -d` でフルリセット

---

### イメージのビルドが途中で失敗する

```bash
docker compose build --no-cache
# キャッシュを無視して最初からビルドし直す
```

よくある原因：
- ネットワークが不安定で `apt-get` や `pip install` がタイムアウト
- `requirements.txt` のパッケージバージョンが非対応

---

### コンテナ内の変更が反映されない

バインドマウントでコンテナと共有しているため、コードの変更はリビルド不要で即時反映される。
ただし以下の場合はリビルドが必要：
- `Dockerfile` を変更した
- `requirements.txt` にパッケージを追加・変更した

```bash
docker compose up -d --build   # リビルドして再起動
```

---

### DB データをリセットしたい

```bash
# 【注意】実験データが全て消える
docker compose down -v         # コンテナとボリュームを削除
docker compose up -d           # 再起動（init.sql が再実行されテーブルが再作成される）
```

---

### ディスク容量の確認

```bash
# Docker が使っているディスク容量
docker system df

# 不要なイメージ・コンテナ・ボリュームを一括削除（使用中のものは除外）
docker system prune

# ボリュームも含めて削除（pgdata は消えるので注意）
docker system prune --volumes
```

## イメージの再利用とキャッシュ管理

```bash
# ビルド済みイメージを確認
docker images | grep hanoi

# イメージを削除して最初からビルドし直す
docker rmi modeling_of_llms_lpt-hanoi-minimal
docker compose up -d --build
```

`requirements.txt` や `Dockerfile` を変えずにコードだけ変えた場合はリビルド不要（バインドマウントで同期されているため）。
