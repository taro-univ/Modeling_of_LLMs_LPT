# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
`PYTHONPATH=/app` が設定済みなので `python runners/run_local.py` のように直接実行できる。

> メインの実験エントリポイントは **`runners/run_local.py`**（HuggingFace 版・NF4 量子化・隠れ状態キャプチャ付き）。
> `runners/run.py` は早期終了ロジック (`EarlyStopConfig`, `check_early_stop`, アルゴリズム A〜E) を提供する**共通ライブラリ**であり、同時に Ollama API 経由のランナーでもある。
> `run_local.py` は `run.py` から `EarlyStopConfig` などをインポートしている。

---

## よく使うコマンド（コンテナ内 `/app` から）

### 1. 単体テスト

```bash
# 早期終了アルゴリズム D / E の単体テスト（実験前に PASS 確認）
python3 -m pytest tests/test_early_stop.py -v

# 個別テストクラス／メソッド指定
python3 -m pytest tests/test_early_stop.py::TestAlgorithmD -v
python3 -m pytest tests/test_early_stop.py::TestAlgorithmE::test_e1_fires_after_moves1_stagnation -v
```

### 2. 新モデル追加時の事前検証

```bash
# GPU 不要（設定確認のみ）
PYTHONPATH=/app python3 runners/test_model_architecture.py \
    --model-id <hf_model_id> --no-gpu-tests

# 全テスト（T0〜T5、ロード〜生成まで）
PYTHONPATH=/app python3 runners/test_model_architecture.py --model-id <hf_model_id>
```

詳細は `docs/test_model_architecture_runbook.md` 参照。

### 3. 単発実験

```bash
python3 runners/run_local.py --N 3 --trials 5 --temperature 0.6
python3 runners/run_local.py --N 5 --trials 10 --no-early-stop --device cuda:0
```

`--output` 省略時は `results/hanoi/<slug>/N{N}/` 配下に `summary.json` と `trial_*.npz` が保存され、
`meta.json` は実験開始直後に書き出される（途中クラッシュしても `sync.sh` が "waiting" として検知できる設計）。

### 4. スイープ

```bash
# メインスイープ（相図 + P(q)、デフォルト 7B / N=2-6 / T=0.2-2.0 / 25 trials）
bash runners/scripts/run_full_sweep.sh --analyze

# 崩壊相内部の精密スイープ（T=1.1-3.0、SG↔PM 境界の決定用）
bash runners/scripts/run_collapse_phase_sweep.sh --analyze

# 内容確認のみ（コマンドを表示するだけで実行しない）
bash runners/scripts/run_full_sweep.sh --dry-run

# 複数モデルをまとめて
bash runners/scripts/run_full_sweep.sh \
    --models "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B Qwen/Qwen3-8B" \
    --trials 25 --analyze
```

スイープ結果は `results/hanoi/full_sweep/<slug>/N{N}_T{T}/` に格納される（`T` は `.` を `_` に置換）。
既存セルは `summary.json` の trial 数が `--trials` 以上ならスキップ（冪等）。

### 5. 解析

```bash
# 統合解析パイプライン（相図 + P(q) + 臨界減速）
python3 analysis/run_pipeline.py \
    --data-dir results/hanoi/full_sweep/<slug>/ \
    --out-dir figures/full_sweep/<slug>/ \
    --title "<model name>" \
    --analyzers phase_transition spin_glass critical_dynamics

# YAML config から実行
python3 analysis/run_pipeline.py --config analysis/configs/template.yaml
```

### 6. DB 同期

```bash
bash db/sync.sh
```

`meta.json` が存在するディレクトリを再帰的に検出して PostgreSQL に取り込む。
`summary.json` がまだないディレクトリは `waiting` 扱いでスキップ。
スキーマは `db/init.sql`（`experiments` × `trials` の 2 テーブル）。

---

## 実験ループの流れ

```
run_local.py 実行
    │
    ├─ 実験開始直後に meta.json を自動生成（summary.json と同ディレクトリ）
    │       meta.json: environment / model / N / temperature / sweep_type
    │
    ├─ 各試行ごとに LLM を呼び出し → moves を評価 → accuracy を記録
    │       Move 完了ステップで隠れ状態を npz に追記（layer_top / layer_mid / layer_low の 3 層）
    │
    └─ 全試行完了後に summary.json を保存
            summary.json: 各試行の accuracy / early_stop / 手数 などの配列

bash db/sync.sh
    │
    └─ meta.json が存在するディレクトリを再帰的に検出し PostgreSQL に取り込む
            （既に同 (env, model, N, T, sweep_type) が DB にあればスキップ＝冪等）

analysis/*.py
    └─ summary.json / npz を読み込み、相図・P(q)・スケーリング則を解析・描画
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

| 値 | アルゴリズム | 暫定的な相対応 |
|---|---|---|
| `goal_reached` | run_local.py | 秩序相 (Ordered) |
| `move_loop_repeat` / `move_loop_reverse` | C | スピングラス相 (SG) |
| `no_move_catchall` | D | 常磁性相 (PM) |
| `move_ceiling` | B | 常磁性相 (PM) |
| `stagnation_after_move` | E | **未確定**（SG / PM 両解釈あり、SPEC-2026-05-21-001 で調査中） |
| `think_budget` | A | **相分類から除外**（測定上の打ち切り。censored data として扱う） |

> 相対応の詳細・問題点は `docs/phase_classification_review.md` を参照。
> 現行の分類アルゴリズムは physics-agent 審査で**不合格（要再設計）**と判定されており、P(q) ベース再設計を進行中。

---

## コード構成のキーポイント

ファイル一覧から自明でない構造的なポイント：

- **`runners/run.py` ↔ `runners/run_local.py` の関係**：
  `run.py` は早期終了の共通ライブラリ（`EarlyStopConfig`, `check_early_stop`, `_MOVE_RE`, `calc_*`）を提供しつつ Ollama 用ランナーを兼ねる。
  `run_local.py` はそこから `import` して HF Transformers 用のカスタム生成ループを実装し、Move 直後に隠れ状態を npz へ書き出す。
  早期終了ロジックを変更する際は `run.py` を編集すれば両ランナーに反映される。
- **Move 抽出の二層構造**：`run.py._MOVE_RE` は `(src, dst)` のみを抽出してループ判定に使用。
  `run_local.py._MOVE_RE_WITH_DISK` はディスク番号込みの 3-tuple を抽出して、正解手列内の同ペグ間異ディスク移動が誤ってループ判定されるのを防ぐ。
  ループ検出時は両方で再判定する。
- **モデル毎の think 起動方式**は `ModelProfile.think_mode` で抽象化：DeepSeek-R1-Distill 系は `prefill`（`<think>\n` をプロンプト末尾に追記）、Qwen3 系は `chat_template`（`apply_chat_template(..., enable_thinking=True)`）。
  `resolve_model_profile()` が model_id プレフィックスから自動選択する。
- **`make_capture_layers(num_hidden_layers)`** が `layer_top`/`layer_mid`/`layer_low` を負インデックスで返すため、レイヤ数の異なるモデルでも 100% / 50% / 25% 深度で隠れ状態を取得できる。
- **`envs/hanoi_env.py`** は単一ファイルの自己完結 env（`BaseEnv` 抽象基底 + `TowerOfHanoiEnv`）。
  `evaluate_state()` が推論ポテンシャル $V(x) = \lambda_d \hat D + \lambda_p \cdot \text{illegal}$ を返す（$V=0$ がゴール、$V=1$ が初期状態、$V>1$ は違法手）。
- **DB スキーマ**は `experiments`（条件セット）と `trials`（試行）の 2 テーブル。`(environment, model, N, sweep_type, temperature)` の組で重複検出するため、同条件の再実行は DB 上は 1 行に保たれる（`db/sync_one.py` の `CHECK_DUPLICATE`）。
- **静的/動的ファイルの分離**：Git 管理対象はコード・ドキュメント・`summary.json`・`meta.json` のみ。
  - `.gitignore` 対象：`results/**/*.npz`（隠れ状態）、`figures/`（再生成可能）
  - 参照資料（PDF 等）は `assets/` に格納する。
- **figures の構造**：`figures/<sweep_type>/<model-slug>/<図名>.png` に統一。
  旧命名・モデル名なしの png は `figures/legacy/` に退避済み。
- **旧形式 results の所在**：`archive/results_legacy/` に移行済み（`phase_diagram/`, `pq_sweep/`, `temp_sweep/`, `results_N*_hf/`, 初期単発 JSON）。
  物理ファイルは Docker 所有のため `results/hanoi/` 内に残存するが `.gitignore` で除外済み。

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

相境界のスケーリング則 $T_c(N) = A \cdot N^{-\alpha}$ は暫定的な作業枠組み（`research_state/hypotheses.md` 参照）。

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

---

## 研究の最終ゴールと全体方針

### 最終ゴール

統計力学的にモデリングした LLM 推論挙動から **推論精度を定量評価** し、推論が行き詰まった際に**ゴール方向へ介入する制御モデル**を構築する。

相図の現象論的記述・ハミルトニアン構築・スケーリング則は **手段** であり、目的は制御モデル。

### 達成段階

1. ポテンシャル上の粒子シミュレーションで「外力挿入により秩序相が広がる」を成功させる
2. その制御外力に対応する**推論時の駆動**を設計する
3. 制御モデル完成

### 理論基盤（曲げない大方針）

スピングラス理論／Hopfield 模型／散逸構造／非平衡統計物理／レプリカ対称性の破れ (RSB)。

### モデリング対象の自由度

**L2（LLM の隠れ状態空間 $h \in \mathbb{R}^d$）が本命**。`run_local.py` が npz に layer_top/mid/low を保存済み。
次元の高さは未解決の課題（次元縮約方針は `open_questions.md` 参照）。

### パズル設計の必須制約

- **解は一意であること**（成功・失敗を明確に判定するため）
- それ以外（branching factor, 状態空間の連続性, ポテンシャル地形, 報酬の deceptive さ）は **制約なし**。多様に試す

### 対象モデル（5 種）

- `deepseek-ai/DeepSeek-R1-Distill-Qwen-7B`
- `deepseek-ai/DeepSeek-R1-Distill-Qwen-14B`
- `meta-llama/Meta-Llama-3-8B`（系列）
- `Qwen/Qwen3-7B`
- `Qwen/Qwen3-14B`

> 各モデルの sweep 進捗は `research_state/results_summary.md` を参照（ここには書かない）。

### 計算資源

- **RTX 5070, 12 GB VRAM, 1 枚**（CUDA 13.1）
- 14B 級は **NF4 量子化必須**。RTX 5070 12GB でのロード・生成は**実機確認済み**（`open_questions.md` U7 解消）

### 締切

- **2026-06-30** モデリング完了
- **2026-07** ハミルトニアン構築 + シミュレーション成功で**中間報告**

外部要因による締切ではなく自主目標。共著者・指導教員は実質なし（研究室の教員は形式のみ、定例報告なし）。

---

## エージェントチームの設計思想と運用ルール

### 役割分担 (Hybrid Architecture)

| エージェント | 責務 | 担当ツール/モデル |
|---|---|---|
| **オーケストレーション** | プロジェクトの指揮、仕様書の作成・更新、結果の評価。**直接コードの編集（Edit/Write）は原則行わない。** | Claude Code（Opus/Sonnet をタスクにより選択） |
| **フィジックスエージェント** | 理論的整合性を**厳しく**審査。ハミルトニアン・ポテンシャル・外力の物理的妥当性を検証（役割定義は `.claude/agents/physics-agent.md`） | Claude Code（Sonnet） |
| **実装エージェント** | コーディング担当。仕様書（`specs/final/`）を読み込みコードを書き換える。**OOP で機能別に綺麗に分離した設計を徹底。** | **Codex CLI（GPT-5.5）** |
| **品質チェックエージェント** | コード品質審査。実装後に差分をチェックする。実装エージェントとは独立（`.claude/agents/quality-check-agent.md`） | Claude Code（Sonnet） |
| **リサーチエージェント** | 文献調査の単一窓口。user・フィジックス・実装チームへ参考文献を供給する潤滑油役（`.claude/agents/research-agent.md`） | Claude Code（Sonnet） |
| **パイプラインオーケストレーター** | GATE C 通過後の「スイープ実行 → DB 同期 → 進捗更新」を自動化する裏方（役割定義は `.claude/agents/pipeline-orchestrator.md`） | Claude Code（Sonnet サブエージェント） |

### Codex（実装エージェント）の呼び出しルール

オーケストレーション（Claude Code）は、仕様書が `specs/final/` に移動して「Stage 4: 実装」フェーズに入った際、**自分でファイル編集を行わず、必ず以下の Bash コマンドを実行して Codex に実装を委譲すること。**

```bash
# Codex への実装委譲コマンド（spec_id を実際の ID に置き換える）
cat specs/final/SPEC-YYYY-MM-DD-NNN.md | \
  codex exec \
    -s danger-full-access \
    -m gpt-5.5 \
    -o /tmp/codex_SPEC-YYYY-MM-DD-NNN_output.md \
    - > /tmp/codex_SPEC-YYYY-MM-DD-NNN.log 2>&1
```

> **完了後の必須手順**：Codex の実行ログと `git diff` を確認し、Stage 5（品質チェック → physics 事後確認）へ進むこと。
> Codex が途中で詰まった場合（exit non-zero / diff が空）は、エラーログを user に報告して指示を仰ぐ。

### 判断権の所在

- **研究方針の判断は user の専権事項**：仮説の決定、実装するパズル、解析スクリプトの選定、モデル選定、モデリング案の採否などは**必ず user に確認**
- **手段は委任**：プログラミング、論文選定、要件定義から実装までの過程は user の許可不要。要件定義の質に応じて自律的に進める
- **物理的厳密性 > スピード**：フィジックスエージェントが「怪しい」と判断したら止めて理論を詰める。暫定フィットで先に進めることは原則しない

### リサーチエージェントの運用

- 何か怪しい状況（フィジックス／オーケストレーションが疑問を提示）が起きたら、リサーチエージェントが文献を拾う
- 提案先は user だけでなく**他エージェントにも横展開**する（実装チームに「この理論があるからこう書ける」と教える、フィジックスに参考文献を渡す）
- **各エージェント内で個別に文献調査をしない**（重複と品質ばらつきを避ける）

### パイプラインオーケストレーターの呼び出しルール

オーケストレーション（Claude Code）は GATE C 通過後、**自分でスイープスクリプトを叩かず**、必ず Pipeline Orchestrator サブエージェントを起動する。

**起動条件**：
1. ユーザーが「実験GO」を明示した（GATE C 通過）
2. 実験対象モデル・パラメータが確定している

**起動方法**（Claude Code の `Agent` ツールを使用）：
```
subagent_type: "general-purpose"
prompt: ".claude/agents/pipeline-orchestrator.md の指示に従い、以下のパラメータで実行:
  model_list: [...]
  sweep_type: full_sweep or collapse_phase_sweep
  trials: 25
  run_pq_classify: true"
```

**完了後の必須手順**：Pipeline Orchestrator の完了レポートを確認し、エラーがあればユーザーに報告する。

**例外（直接実行してよいケース）**：
- 単発実験（1 条件だけ確認したい場合）
- デバッグ目的のドライラン（`--dry-run`）
- GPU メモリチェック（`runners/scripts/check_gpu_memory.sh`）

### サブエージェントへの Bash コマンド生成ルール

**全サブエージェント（特に implementation-agent）へのプロンプトに必ず以下の一文を含めること：**

> 「Bash コマンドの中で複数行の `python3 -c "..."` にコメント（`#`）を含めないこと。
> 代わりに Write ツールで `/tmp/script_<用途>.py` に書き出してから `python3 /tmp/script_<用途>.py` で実行すること。」

**背景**：Claude Code のセキュリティ機構「Newline followed by # inside a quoted argument」は、
引数内の改行＋`#` のパターンをコマンドインジェクションの可能性として検出し、
allowlist に登録済みのコマンドであっても**強制的にブロック**する（security override）。
この制約はプロジェクト設定では回避できないため、コード生成側で対処する必要がある。

**OK な書き方**（ファイル経由）：
```bash
# Write ツールで /tmp/check_env.py を作成してから：
python3 /tmp/check_env.py
```

**NG な書き方**（インライン複数行 + コメント）：
```bash
# これはセキュリティ override でブロックされる
python3 -c "
import sys  # check version
print(sys.version)
"
```

**Agent prompt 内の `#` 見出しも同様にブロックされる（追記 2026-05-24）**：

Agent ツールの `prompt` パラメータに改行 + `#`（Markdown 見出し `##` `###` 等）が含まれると、
同じ security override が発動して Agent ツール呼び出し自体がブロックされる。

Agent への prompt では `#` 見出しを使わず、以下の代替表記を使うこと：
- `===` や `---` の ASCII アンダーライン区切り
- `**太字**` でのセクション名
- 番号付きリスト

---

## 研究状態ファイル

研究の現状は以下のファイルに分けて管理する。会話の冒頭で参照する。

- `research_state/hypotheses.md` — 仮説（大方針・本命・作業枠組み・棚上げ）
- `research_state/results_summary.md` — 観測事実と既存データの要約
- `todo.md` — 優先度付きタスク
- `open_questions.md` — 未解決の論点（未定項目は未定として明示）

---

## 研究フロー（アイデア → 実装 → 実行）

**詳細は [`docs/research_flow.md`](docs/research_flow.md) を参照。**

アイデアを実験・モデリング実装に落とし込む標準ワークフロー：

```
Stage 1: User（アイデア）→ ドラフト仕様書作成（各エージェント並行）
         │
Stage 2: 壁打ち（保存則・アルゴリズム詳細を詰める）
         │
         ⛔ GATE A ─ ユーザーが「壁打ち終了」を宣言するまで specs/final/ に移動しない
         │           Claude は壁打ち中に自律的に final に昇格させない
         │
Stage 3: 仕様書清書・確定（specs/final/ へ移動）
         │
         ⛔ GATE B ─ final 仕様書をユーザーに提示し、目視確認の承認を得る
         │           「この仕様書で Codex を起動してよいですか？」を必ず聞く
         │           承認なしに codex コマンドを実行しない
         │
Stage 4: 実装（Codex CLI に委譲）
         │
Stage 5: 検証（quality-check-agent → physics-agent 事後確認）
         │  ↑ Stage 4〜5 は一気通貫で自律実行。Claude/Codex が自由に進める
         │
         ⛔ GATE C ─ 実験実行前に必ずユーザーの GO サインを待つ
         │           pytest PASS + 検証レポートをまとめてユーザーに提示してから止まる
         │           承認なしに run_local.py / sweep スクリプトを実行しない
         │
Stage 6: 実験実行（run_local.py / sweep）
```

### ゲートの運用ルール

| ゲート | 停止条件 | Claude が提示するもの | 次に進む条件 |
|---|---|---|---|
| **GATE A** | Stage 2 終了後 | 壁打ちの論点まとめ・未解決事項 | ユーザーが「final に移してOK」と明示 |
| **GATE B** | final 仕様書作成後 | `specs/final/<spec_id>.md` の全文 | ユーザーが「Codex 起動OK」と明示 |
| **GATE C** | Stage 5 完了後 | pytest 結果・quality-check 報告・physics 審査結果 | ユーザーが「実験実行GO」と明示 |

> **Stage 4 の鉄則**：仕様書が `specs/final/` にあるときは、オーケストレーションは Edit/Write を使わず
> 必ず `codex --task-file ... --auto-approve` で Codex に委譲する。
> 完了後は `git diff` と Codex ログを確認してから Stage 5 へ進む。

### 解析タスクの軽量トラック（Track B）

実装を伴わない純粋な解析・探索は **`specs/_template_analysis.md`** を使い、
**physics-agent 確認のみ** で GATE B/C なしに実行可能とする。
Codex への委譲・quality-check-agent レビューは不要。

```
Track A（実装あり）: アイデア → Spec(_template.md) → GATE A → GATE B → Codex → quality-check → GATE C → 実行
Track B（解析のみ）: アイデア → Brief(_template_analysis.md) → physics-agent確認 → 実行
                                                                  ↓
                                                      experiment_register.md に記入
                                                      hypotheses.md の status を更新
```

**Track B を使う判断基準**：
- 新規コードファイルを作成しない（既存スクリプトのみ）
- 実験（LLM 推論）を伴わない（解析・可視化のみ）
- pytest 対象のロジック変更がない

完了後は **必ず** `research_state/experiment_register.md` に記入し、
対応する仮説の `status` / `evidence` を `research_state/hypotheses.md` に更新すること。

---

### 仕様書の置き場

```
specs/
  _template.md          ← Track A（実装）テンプレート
  _template_analysis.md ← Track B（解析）テンプレート
  draft/                ← 壁打ち中（status: draft / review）
  final/                ← 確定済み（status: final / implemented）
  log/                  ← 壁打ち議事録（<spec_id>/round*.md）
```

spec_id 命名: `SPEC-YYYY-MM-DD-NNN`（例: `SPEC-2026-05-21-001`）

### 各エージェントの仕様書における役割

| エージェント | モデル | 担当 Section | タイミング |
|---|---|---|---|
| physics-agent | Claude Code（Sonnet） | Section 2（物理的要件） | Stage 1（ドラフト作成時） |
| research-agent | Claude Code（Sonnet） | Section 3（関連文献） | Stage 1（ドラフト作成時） |
| implementation-agent | **Codex CLI（GPT-5.5）** | Section 4（アルゴリズム仕様） | Stage 1（設計案）、**Stage 4（実装委譲）** |
| quality-check-agent | Claude Code（Sonnet） | 仕様書との照合審査 | Stage 5（実装後レビュー） |
