# CLAUDE.md

## 実行環境

Docker Compose で実験コンテナ (`hanoi-minimal`) と PostgreSQL (`db`) を管理する。

```bash
# 初回ビルド & 起動
docker compose up -d --build

# コンテナに入る（実験実行はすべてここから）
docker compose exec hanoi-minimal bash

# 停止
docker compose down
```

コンテナ内では `/app` がプロジェクトルートにマウントされる。
`PYTHONPATH=/app` が設定済みなので `python runners/run_hf.py` のように直接実行できる。




### 実験後の DB 同期（コンテナ内）

```bash
bash db/sync.sh
```

`meta.json` が存在するディレクトリを自動検出して PostgreSQL に取り込む。
`run_hf.py` は実験開始時に `meta.json` を自動生成するため、手動操作は不要。


---

## 実験ループの流れ

```
run_hf.py 実行
    │
    ├─ 実験開始直後に meta.json を自動生成（summary.json と同ディレクトリ）
    │       meta.json: モデル名・N・T・n_shot・日時などの実験メタデータ
    │
    ├─ 各試行ごとに LLM を呼び出し → moves を評価 → accuracy を記録
    │
    └─ 全試行完了後に summary.json を保存
            summary.json: 各試行の accuracy / early_stop 理由 / 手数 などの配列

bash db/sync.sh
    │
    └─ meta.json が存在するディレクトリを再帰的に検出し PostgreSQL に取り込む
            （既にインポート済みのディレクトリはスキップ）

analysis/*.py
    └─ DB または summary.json を読み込み、相図・P(q)・スケーリング則を解析・描画
```

### summary.json の主要フィールド

| フィールド | 型 | 説明 |
|---|---|---|
| `accuracy` | int (0/1) | 正解なら 1 |
| `early_stop` | str \| null | 早期終了の理由（下表参照） |
| `num_moves` | int | 生成した手数 |
| `temperature` | float | 生成温度 $T$ |
| `N` | int | ディスク数（複雑度） |

### early_stop の種類と物理的解釈

| 値 | 意味 | 対応する相 |
|---|---|---|
| `goal_reached` | 正解手列を完成 | 秩序相 (Ordered) |
| `move_loop_repeat` | 手がループして脱出できない | スピングラス相 (SG) |
| `move_ceiling` / null (no-move) | 手をほとんど出力しない | 常磁性相 (PM) |

---

## 物理変数の対応表

コード中に登場する変数と、統計力学上の対応物の一覧。

| コード変数 | 物理的意味 | 統計力学での対応 |
|---|---|---|
| `temperature` (float) | 生成温度 $T$ | 熱浴温度・ノイズ強度 |
| `N` (int) | ディスク数（問題複雑度） | システムサイズ・エネルギー障壁高さ |
| `accuracy` (0 or 1) | 秩序変数 $m$ | 磁化（1=秩序、0=無秩序） |
| `n_shot` (int) | few-shot 例示数 | 外部磁場 $h$（秩序相を安定化） |
| `K(N) = 2^N - 1` | 最短解の手数 | Hopfield 項のパターン数（記憶容量に対応） |

### 相図の読み方

```
N
6  | ░░░░░░░░░░░░
5  | ▓░░░░░░░░░░░
4  | ▓▓▓░░░░░░░░░    ░ = 崩壊相（SG + PM）
3  | ▓▓▓▓▓▓░░░░░░    ▓ = 秩序相
2  | ▓▓▓▓▓▓▓▓▓░░░
   └──────────── T
     0.2  1.0  2.0
```

相境界のスケーリング則：$T_c(N) = A \cdot N^{-\alpha}$（または指数型）。
指数 $\alpha$ のモデル普遍性がこの研究の主要検証命題。

---

## Markdown 数式ルール（GitHub 向け）

### インライン vs ブロック

- インライン：`$T_c(N)$` のように `$` 1つで囲む。`$ T $` のように**内側にスペースを入れない**。
- ブロック：`$$` で囲み、**上下に必ず空行を入れる**。

```markdown
（空行）
$$
T_c(N) = A \cdot N^{-\alpha}
$$
（空行）
```

### アンダースコアのエスケープ

Markdown の斜体記法（`_text_`）と競合するため以下を徹底する。

- 数式内でアンダースコアを多用する場合は `\_` とエスケープするか、ブロック表示にする。
- 変数名・ラベルにアンダースコアが含まれる場合は `\text{dtype\_bytes}` のように `\text{}` で囲む。

### その他
実験の詳細についてはdocsに保存してある各mdファイルを参照すること

archiveフォルダーについては、実験済みのものを保存してあるため
言及がない限り参照しないでよい