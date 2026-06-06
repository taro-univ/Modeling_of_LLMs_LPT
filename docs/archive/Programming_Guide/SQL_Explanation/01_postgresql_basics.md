# 01 PostgreSQL基礎：概念・接続・Docker経由での操作

## このプロジェクトでの構成

```
ホスト（WSL2）
  └─ Docker Compose
       ├─ hanoi-minimal コンテナ  ← 実験スクリプト実行
       └─ db コンテナ（postgres:16-alpine）
            └─ experiments データベース
                 ├─ experiments テーブル  ← 実験条件1件 = 1行
                 └─ trials テーブル       ← 試行1件 = 1行
```

接続情報（`docker-compose.yml` より）：

| 項目 | 値 |
|---|---|
| ホスト | `db`（コンテナ内）/ `localhost`（ホストから） |
| ポート | `5432` |
| DB名 | `experiments` |
| ユーザー | `exp_user` |
| パスワード | `exp_pass` |

環境変数 `DATABASE_URL` としてまとめて管理：
```
postgresql://exp_user:exp_pass@localhost:5432/experiments
```

## psql での接続

```bash
# ホストから直接接続（ポート 5432 をフォワード済み）
psql postgresql://exp_user:exp_pass@localhost:5432/experiments

# コンテナ内から接続
docker compose exec db psql -U exp_user -d experiments
```

## psql の基本コマンド

| コマンド | 意味 |
|---|---|
| `\l` | データベース一覧 |
| `\dt` | テーブル一覧 |
| `\d experiments` | テーブルの構造を表示 |
| `\d trials` | 同上 |
| `\q` | 終了 |
| `\x` | 縦表示モード切替（結果が見やすくなる） |

## RDB（リレーショナルDB）の基本概念

| 概念 | 説明 | この研究での例 |
|---|---|---|
| **テーブル** | 行と列からなる表 | `experiments`, `trials` |
| **行（レコード）** | データの1件 | 1つの実験条件 / 1回の試行 |
| **列（カラム）** | データの属性 | `N`, `temperature`, `accuracy` |
| **主キー（PRIMARY KEY）** | 行を一意に識別するカラム | `id`（自動採番） |
| **外部キー（FOREIGN KEY）** | 別テーブルの主キーへの参照 | `trials.experiment_id → experiments.id` |
| **インデックス** | 検索を高速化する索引 | `idx_experiments_lookup` |

## テーブル間の関係

```
experiments (1) ──── (多) trials
     id  ←────────── experiment_id
```

1つの実験条件（`experiments` の1行）に対して、複数の試行（`trials` の複数行）が紐づく。
`ON DELETE CASCADE` により、実験条件を削除すると紐づく試行も自動削除される。
