# 01 Linux基礎：ファイルシステム・基本コマンド

## ディレクトリ構造

```
/                    ← ルートディレクトリ
├── home/shona/      ← ホームディレクトリ（~で省略可）
│   └── Modeling_of_LLMs_LPT/   ← プロジェクトルート
├── app/             ← Docker コンテナ内のマウント先
└── usr/, var/, etc/ ← システムディレクトリ
```

- **絶対パス**：`/home/shona/Modeling_of_LLMs_LPT/results`（`/` から始まる）
- **相対パス**：`results/hanoi/phase_diagram`（カレントディレクトリからの相対位置）
- `.` ：カレントディレクトリ、`..`：1つ上のディレクトリ

## よく使う基本コマンド

### echo — 文字列の出力

```bash
echo "N=${N}  T=${T}  trials=${TRIALS}"
echo ""                          # 空行
echo "All sweeps done."
```

### ls — ファイル一覧

```bash
ls results/hanoi/phase_diagram   # ディレクトリ内のファイル表示
ls -la                           # 詳細表示（パーミッション・サイズ・日時）
```

### mkdir — ディレクトリ作成

```bash
mkdir results/hanoi/N3_T0_6
mkdir -p results/hanoi/phase_diagram/N3_T0_6   # -p: 中間ディレクトリも一括作成
```

### find — ファイルを検索

`db/sync.sh` の核心部分：

```bash
find results/ -name "meta.json" -print0
# results/ 以下で meta.json という名のファイルを全て検索
# -print0: ファイルパスを null 文字で区切って出力（スペースを含むパスに対応）
```

| オプション | 意味 |
|---|---|
| `-name "*.sh"` | ファイル名のパターンマッチ |
| `-type f` | ファイルのみ（ディレクトリは除外） |
| `-print0` | null 区切り出力（`read -d ''` と組み合わせる） |

### sort — 並び替え

```bash
find results/ -name "meta.json" -print0 | sort -z
# -z: null 区切りのまま並び替え（find -print0 とセットで使う）
```

### tr — 文字の置換・削除

スクリプト内で `.` を `_` に置き換えてディレクトリ名を作るのに使用：

```bash
T_TAG=$(echo "0.6" | tr '.' '_')
# → T_TAG="0_6"

echo "Hello World" | tr ' ' '_'
# → Hello_World

echo "abc" | tr 'a-z' 'A-Z'
# → ABC（小文字→大文字）
```

### cat — ファイル内容の表示

```bash
cat results/hanoi/N3_T0_6/summary.json   # ファイル内容をそのまま出力
```

## パーミッション（権限）

```bash
ls -la runners/scripts/run_temp_sweep.sh
# -rwxr-xr-x  1 shona shona ...
#  ^^^         → 所有者: 読み書き実行
#     ^^^      → グループ: 読み実行
#        ^^^   → その他: 読み実行

chmod +x runners/scripts/run_temp_sweep.sh   # 実行権限を付与
```

## シェルスクリプトの実行方法

```bash
bash runners/scripts/run_temp_sweep.sh      # bash で実行（実行権限不要）
./runners/scripts/run_temp_sweep.sh         # 直接実行（実行権限が必要）
```

`docker compose exec hanoi-minimal bash` でコンテナに入ってから実行するのがこのプロジェクトの標準。
