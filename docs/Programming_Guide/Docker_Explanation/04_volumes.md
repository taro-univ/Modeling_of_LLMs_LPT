# 04 ボリューム：データの永続化とファイル共有

コンテナを削除するとコンテナ内のファイルは消えるが、ボリュームに保存したデータは残る。
このプロジェクトでは **3種類のマウント** が使われている。

## マウントの種類と使い分け

| 種類 | 定義方法 | データの場所 | 用途 |
|---|---|---|---|
| **バインドマウント** | `./host/path:/container/path` | ホストのディレクトリ | ソースコード・実験結果 |
| **named volume** | `volume_name:/container/path` | Docker が管理する領域 | DBデータなど永続化が必要なもの |
| **匿名ボリューム** | `/container/path`のみ | Docker が管理する領域 | 一時的なデータ（このプロジェクトでは未使用） |

## バインドマウント①：プロジェクトルート

```yaml
volumes:
  - .:/app
# ホスト: /home/shona/Modeling_of_LLMs_LPT/
# コンテナ: /app/
```

**効果：ホスト側でファイルを編集するとコンテナに即反映される。**

```
ホスト（VS Code で編集）         コンテナ（Python を実行）
/home/shona/.../runners/run_hf.py  ←→  /app/runners/run_hf.py
/home/shona/.../results/           ←→  /app/results/
/home/shona/.../docs/              ←→  /app/docs/
```

- コンテナをリビルドせずにコードを変更して即座に実験できる
- `results/` に書き出した JSON はホスト側でも直接参照できる
- 双方向なので、コンテナ内で生成したファイルはホスト側にも現れる

## バインドマウント②：HuggingFace モデルキャッシュ

```yaml
volumes:
  - ~/.cache/huggingface:/root/.cache/huggingface
# ホスト: /home/shona/.cache/huggingface/
# コンテナ: /root/.cache/huggingface/
```

**効果：モデルのダウンロードキャッシュをコンテナ間で共有・永続化する。**

- `AutoModelForCausalLM.from_pretrained("deepseek-ai/...")` は初回にモデルをダウンロードしてキャッシュに保存する
- このマウントがないとコンテナを再作成するたびに 7B モデル（約 4GB）を再ダウンロードしてしまう
- `~/.cache/huggingface` はホスト側に実体があるため、コンテナを削除してもモデルは残る

```bash
# キャッシュの場所を確認（ホスト側）
ls ~/.cache/huggingface/hub/
# models--deepseek-ai--DeepSeek-R1-Distill-Qwen-7B/ などが並ぶ
```

## Named Volume：PostgreSQL データ

```yaml
# サービス定義
db:
  volumes:
    - pgdata:/var/lib/postgresql/data

# トップレベルの宣言
volumes:
  pgdata:
```

**効果：`docker compose down` してコンテナを削除してもDBデータが残る。**

- PostgreSQL はデータを `/var/lib/postgresql/data` に保存する
- named volume `pgdata` はコンテナのライフサイクルとは独立して Docker が管理
- 実体は `/var/lib/docker/volumes/modeling_of_llms_lpt_pgdata/_data/`（ホスト上）

```bash
# ボリューム一覧
docker volume ls

# ボリュームの詳細（マウントポイント確認）
docker volume inspect modeling_of_llms_lpt_pgdata

# 【注意】ボリュームごと削除するとDBデータが全部消える
docker compose down -v   # ← 実験データが消えるので原則使わない
docker compose down      # ← コンテナだけ削除（データは残る）
```

## 初期化 SQL のマウント

```yaml
db:
  volumes:
    - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql
```

これはバインドマウントではなく、`db` コンテナへのファイルのマウント。
`/docker-entrypoint-initdb.d/` は PostgreSQL コンテナの**初回起動時のみ**実行される特別なディレクトリ。

**注意点**：
- 初回起動後に `init.sql` を変更しても自動で再実行されない
- テーブル定義を変えたい場合は `docker compose down -v && docker compose up -d` でボリュームごとリセットが必要
- `CREATE TABLE IF NOT EXISTS` にしているため、二重実行してもエラーにはならない

## まとめ：データフロー

```
ホスト（WSL2）
├── /home/shona/Modeling_of_LLMs_LPT/   ──→  コンテナ /app/  （バインドマウント①）
│   ├── runners/run_hf.py                      実験スクリプト
│   └── results/hanoi/                         実験結果 JSON（双方向）
│
├── ~/.cache/huggingface/               ──→  コンテナ /root/.cache/huggingface/
│   └── models--deepseek-ai--...              （バインドマウント②）
│
└── /var/lib/docker/volumes/pgdata/    ←──  db コンテナ /var/lib/postgresql/data/
    └── （PostgreSQL のデータファイル）         （named volume）
```
