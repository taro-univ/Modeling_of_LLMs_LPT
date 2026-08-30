# CLAUDE.md

LLM の「推論崩壊」をパズル環境で誘発し、統計物理・複雑系の観点から解析するリポジトリ。
2026年9月末発表に向けた当面の研究計画は
`docs/research_state/roadmap_2026_09_conference.md` を参照する。
研究ノート運用とセッション開始フローは
`docs/research_state/research_note_workflow.md` を参照する。

## 協働方針（最優先・既定動作を上書き）

- **コードと notebook は、user が依頼した範囲で Codex/Claude が直接編集してよい。**
  コピペや写経を既定とせず、実装力向上のために手書きする場合は user がその都度明示する。

- user がお手本コードや写経を希望した場合は、「何を・なぜ」を添え、手入力しやすい粒度で示す。
- **現行のファイルのみを参照する。** git 履歴・削除済みファイル・過去の経緯を参照しない。
  また「過去は参照しません」等の言及・表示もしない。
- インターン先の coding 環境に揃える方針。指示にない勝手な変更・追加をしない。

## 実行（HuggingFace 中心）

リポジトリルートから実行する（`envs` / `runners` をパッケージ import するため）。

コマンドは `python3`（この環境に `python` エイリアスは無い）。HF 実行には `torch` /
`transformers` / `bitsandbytes` と GPU が必要（`requirements.txt`）。

```bash
# ローカル実験（HF Transformers, NF4 4bit）。Move 出力位置で隠れ状態を保存
python3 runners/run_local.py --N 3
python3 runners/run_local.py --N 5 --trials 10 --model-id deepseek-ai/DeepSeek-R1-Distill-Qwen-7B
python3 runners/run_local.py --N 5 --no-early-stop --device cuda:0 --output-dir results/...
```

主な引数: `--N`（円盤数, 必須）, `--trials`, `--model-id`, `--device`(default `cuda:0`),
`--num_predict`, `--output`(JSON), `--output-dir`(隠れ状態 npz), `--no-save-hidden`,
`--no-early-stop`, `--no-loop-detection`, `--es-*`（早期終了パラメータ）, `--seed`。

参考: `runners/run.py` は Ollama API 版（`OLLAMA_BASE_URL`、`--model`）。run_local.py は
そこから `EarlyStopConfig` / `calc_*` / `check_early_stop` を流用する。

## 解析

現行の仮説は `docs/research_state/hypotheses.md`（`hanoi_entropy_complexity_slides.md` から再構築）を正本とする。
9月末発表向けの hidden-state dynamics 研究計画は
`docs/research_state/roadmap_2026_09_conference.md` を参照する。
日々の研究ノート運用とセッション開始/終了フローは
`docs/research_state/research_note_workflow.md` を参照する。
SPEC番号・EXP番号・4-regime・SG/PM等の旧ナンバリング仮説とその解析器は廃止済み。

```bash
python3 analysis/plot_hanoi_nt_collapse.py \
  --input-dir results/hanoi/full_sweep --input-dir results/hanoi/collapse_phase
```

`summary.json` から N-T 平面の accuracy と collapse mode（move_loop / no_move 等）を直接集計する。
BaseAnalyzer 的な共通化フレームワークは持たない — 1スクリプト1目的。

## テスト

```bash
python3 -m pytest tests/        # 単体テスト（tests/ 配下, 50 件）
python3 -m pytest tests/test_hanoi_env.py -q
```

`tests/` を明示する。ルート直下で `pytest` を走らせると、ランナーである
`runners/test_model_architecture.py`（`test_` 始まりだが torch 依存のスクリプト）を
収集してしまい、torch 未導入だと収集エラーになる。

## ディレクトリ構成

| パス | 役割 |
|---|---|
| `envs/` | パズル環境。`base_env.py`(`BaseEnv` 抽象基底) / `hanoi_env.py` / `lights_out_env.py` |
| `runners/` | 実験ドライバ。`run_local.py`(HF) / `run.py`(Ollama) / `scripts/`(スイープ shell) |
| `analysis/` | N-T 平面の集計・可視化スクリプト（1スクリプト1目的、共通基底クラスなし） |
| `results/` | 実験・解析の出力 |
| `docs/research_state/` | 仮説・観測事実・実験台帳・todo・9月末発表ロードマップ・研究ノート運用の正本（`hypotheses.md` / `results_summary.md` / `experiment_register.md` / `todo.md` / `roadmap_2026_09_conference.md` / `research_note_workflow.md`） |
| `tests/` | pytest |
| `archive/` | 旧ドキュメント・ログ（参照用、原則触らない） |

## 規約

- 新しいパズルは `BaseEnv` を継承し、進捗指標 `evaluate_state`（V(x)）と
  `goal_reached` / `extract_moves_from_text` / `solve` 等を実装する。
- docstring・コメントは日本語、NumPy スタイル（既存コードに合わせる）。
