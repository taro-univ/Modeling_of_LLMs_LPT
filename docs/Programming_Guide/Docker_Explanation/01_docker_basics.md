# 01 Docker基礎：イメージ・コンテナ・基本コマンド

## なぜ Docker を使うか

実験環境の問題：「自分のマシンでは動くが別の環境では動かない」を防ぐ。

- CUDA バージョン・Python バージョン・ライブラリのバージョンを完全に固定できる
- ホスト OS を汚染しない（インストールしたパッケージがホストに残らない）
- コンテナを捨てて再作成すれば常にクリーンな状態に戻せる

## イメージとコンテナの違い

| 概念 | 説明 | 例え |
|---|---|---|
| **イメージ** | 環境の設計図（読み取り専用） | クラスの定義 |
| **コンテナ** | イメージから起動した実体（読み書き可能） | クラスのインスタンス |

```
Dockerfile → (build) → イメージ → (run) → コンテナ
```

同じイメージから複数のコンテナを起動できる。コンテナを削除してもイメージは残る。

## このプロジェクトのイメージ構成

```
nvidia/cuda:12.8.0-devel-ubuntu22.04   ← ベースイメージ（DockerHub から取得）
    └── + python3, pip, git, curl      ← apt-get で追加
        └── + requirements.txt の依存  ← pip で追加
            └── + PyTorch (cu128)      ← 別途インストール
                = modeling_of_llms_lpt-hanoi-minimal  ← ビルド済みイメージ
```

`db` コンテナは `postgres:16-alpine`（DockerHub 公式イメージ）をそのまま使用。

## 基本コマンド

### イメージ操作

```bash
docker images                          # ローカルのイメージ一覧
docker image rm <image_id>             # イメージを削除
docker pull postgres:16-alpine         # DockerHub からイメージを取得
```

### コンテナ操作

```bash
docker ps                              # 実行中のコンテナ一覧
docker ps -a                           # 停止中も含む全コンテナ
docker stop <container_id>             # コンテナを停止
docker rm <container_id>               # コンテナを削除（停止後）
docker logs <container_id>             # ログを確認
docker logs -f <container_id>          # ログをリアルタイムで追う
```

### コンテナ内に入る

```bash
docker exec -it <container_id> bash
# -i: 標準入力をつなぐ (interactive)
# -t: 疑似ターミナルを確保 (tty)
```

## Docker Compose との関係

このプロジェクトでは Docker コマンドを直接使わず、`docker compose` コマンドを使う。
複数コンテナ（`hanoi-minimal` + `db`）をまとめて管理できる。

```bash
# 個別 Docker コマンドとの対応
docker compose up -d        ≒  docker run (複数コンテナを同時に起動)
docker compose down         ≒  docker stop + docker rm
docker compose exec <svc> bash  ≒  docker exec -it <container> bash
docker compose logs <svc>   ≒  docker logs <container>
docker compose build        ≒  docker build
```

`docker compose` は `docker-compose.yml` を自動的に読み込むため、常にプロジェクトルートから実行する。
