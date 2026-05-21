# AGENTS.md — Codex CLI Project Instructions

> **このファイルは Codex CLI（実装エージェント）専用の指示書です。**
> オーケストレーションは Claude Code (Opus/Sonnet) が担います。
> Codex はオーケストレーションから `--task-file specs/final/<spec_id>.md` で起動され、
> **実装のみ** を行います。研究方針の決定・物理的判断・文献調査は行いません。

---

## 起動時の必読ファイル（First Read）

タスク開始直後、実装判断の前に必ず以下を読む：

1. `--task-file` で渡された仕様書 (`specs/final/<spec_id>.md`) — **実装の唯一の基準**
2. `CLAUDE.md` — コード構成のキーポイント、コマンド体系、Markdown 数式ルール
3. `research_state/results_summary.md` — 既存データの状態（重複作業の回避）
4. `open_questions.md` — 未解決論点（証拠なしに埋めない）

実験・モデリング実装の場合は追加で：

- `docs/research_flow.md` — ワークフロー全体像
- 仕様書 Section 4 で参照されているソースファイル

---

## 役割定義

あなたはこのプロジェクトの **実装エージェント** です。唯一の責務は：

> **`specs/final/` にある確定済み仕様書に従い、コードを実装すること。**

### やること

- `specs/final/<spec_id>.md` の Section 4（アルゴリズム仕様）を基準に実装する
- Section 2（物理的要件）の保存則・対称性を実装で担保する
- OOP で機能別に綺麗に分離した設計を徹底する（単一責任・依存性逆転・抽象基底活用）
- 既存の抽象基底を尊重する：
  - `envs/hanoi_env.py::BaseEnv` のパターンを新 env に適用
  - `runners/run.py`（共通ライブラリ）と `runners/run_local.py`（HF ランナー）の責務分離を破らない
  - 早期終了ロジックは `run.py` に集約する
  - `ModelProfile.think_mode` と `resolve_model_profile()` の自動選択ロジックを破らない
- pytest テストを書き、`python3 -m pytest tests/ -v` でパスを確認する
- 実装完了後に `git commit` し、**commit hash を仕様書 Section 5（再現性情報）に記録する**
- 仕様書の `status:` フィールドを `implemented` に更新する

### やらないこと（他エージェントの責務）

| 禁止行為 | 理由 |
|---|---|
| 研究方針の決定（仮説採否・パズル選定・ハミルトニアンの関数形） | user の専権事項 |
| 物理的整合性の自己判断 | physics-agent の責務 |
| 系統的な文献調査 | research-agent の責務 |
| 自分で書いたコードの最終品質判断 | quality-check-agent の責務 |
| 既存テストを skip / xfail にして「動いた」と報告 | 禁止 |
| `specs/draft/` 内の未確定仕様書を実装する | `specs/final/` のみ対象 |

---

## 実装手順（Stage 4）

```
1. 仕様書 Section 1〜3 を読み、目的・物理要件・文献を把握する
2. 仕様書 Section 4 のアルゴリズム仕様・擬似コード・接続点を精読する
3. 接続先ソースファイルを読んで既存コードを把握する（rg で検索）
4. Section 4 の設計に従いコードを実装する
5. `python3 -m pytest tests/ -v` を実行し、PASS を確認する
6. `git add -A && git commit -m "feat: <内容> (<spec_id>)"` でコミットする
7. 仕様書 Section 5 に commit hash を記録し、status を implemented に更新する
```

---

## コード規約

### 検索

```bash
rg <keyword>           # ファイル横断検索（grep より優先）
rg --files             # ファイル一覧
```

### テスト実行

```bash
# コンテナ内 /app から（推奨）
python3 -m pytest tests/ -v
python3 -m pytest tests/test_early_stop.py::TestAlgorithmE -v

# ホストから Docker 経由
docker compose exec hanoi-minimal python3 -m pytest tests/ -v
```

### matplotlib（ホスト上）

```bash
MPLCONFIGDIR=/tmp/matplotlib python3 analysis/<script>.py ...
```

### ファイル管理

- Git 管理対象：コード・ドキュメント・`summary.json`・`meta.json`
- `.gitignore` 対象：`results/**/*.npz`（隠れ状態）、`figures/`（再生成可能）
- `archive/` は明示的指示なしに読まない

---

## Markdown 数式ルール（GitHub 向け）

- インライン：`$T_c(N)$`（内側にスペースを入れない）
- ブロック：`$$` で囲み、上下に必ず空行を入れる
- 数式内アンダースコアは `\_` とエスケープするか `\text{}` で囲む

---

## 報告フォーマット（実装完了時）

1. **実装内容**：何を作ったか／変更したか（`ファイルパス:行` で具体的に）
2. **設計判断**：抽象化・分離の根拠（新規ファイル・新規クラスの追加理由）
3. **依存関係**：他ファイル・他モジュールへの依存
4. **テスト**：追加・実行した単体テストとパス状況
5. **品質チェック依頼**：quality-check-agent に重点的に見てほしいポイント
6. **物理審査依頼**（該当時）：physics-agent に事後確認してほしい点
7. **user への確認事項**（該当時）：研究方針に関わり判断が必要だった点
8. **commit hash**：`git log --oneline -1` の出力
