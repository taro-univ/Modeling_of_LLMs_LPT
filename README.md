# Modeling of LLMs — Phase Transition in Logical Problem-solving Tasks (LPT)

LLM の推論崩壊を**統計力学的相転移**として定量的に記述する実験リポジトリ。
ハノイの塔を推論タスクとして用い、生成温度 $T$ と問題複雑度 $N$ の 2 変数空間で
秩序相（正常推論）から無秩序相（崩壊）への相転移を実験・理論の両面から解析する。

---

## 物理的背景

### LLM 推論と統計力学の対応

LLM の自己回帰生成は、高次元確率空間上のランダムウォークとして捉えられる。
生成温度 $T$ はサンプリングの「熱ゆらぎ」を制御し、
タスク複雑度 $N$（ハノイの円盤数）は越えるべきエネルギー障壁の高さに対応する。

| LLM の変数 | 統計力学での対応 |
|---|---|
| 生成温度 $T$ | 熱浴温度・ノイズ強度 |
| 複雑度 $N$（円盤数） | システムサイズ・エネルギー障壁 |
| 精度 $m = \text{accuracy}$ | 秩序変数（磁化） |
| $n\text{-shot}$ | 外部磁場（秩序を安定化） |

秩序変数 $m(N, T)$ は以下の形で相転移を示すことが仮説として設定される：

$$
m(N,\ T) \approx \begin{cases} 1 & (N,\ T) \in \text{秩序相（正常推論）} \\ 0 & (N,\ T) \in \text{無秩序相（推論崩壊）} \end{cases}
$$

### 3 相構造と崩壊モード

実験から、以下の 3 相が観測されている：

| 相 | 特徴 | `early_stop` 内訳 |
|---|---|---|
| **秩序相** (Ordered) | $m \approx 1$、正確な解手列を生成 | `goal_reached` が支配的 |
| **スピングラス相** (Spin Glass) | $m \approx 0$、ループ崩壊 | `move_loop_repeat` が支配的 |
| **常磁性相** (Paramagnetic) | $m \approx 0$、手を出力しない | `move_ceiling` / `no_move_catchall` が支配的 |

### 有効ハミルトニアン

実験事実を整理する理論的枠組みとして、以下の有効ハミルトニアンを提案している：

$$
\mathcal{H} =
\underbrace{-\frac{1}{2D} \sum_{\mu=1}^{K(N)} \left( \sum_t \boldsymbol{\xi}_t^\mu \cdot \mathbf{h}_t \right)^2}_{\text{(I) Hopfield 項（N 駆動の転移）}}
\underbrace{-\frac{J_p}{p \cdot D^{p-1}} \sum_{t_1 \cdots t_p} \mathbf{h}_{t_1} \cdots \mathbf{h}_{t_p}}_{\text{(II) p-spin 項（T 駆動の転移）}}
\underbrace{- h \sum_t \boldsymbol{\xi}^* \cdot \mathbf{h}_t}_{\text{(III) 外部磁場項（n-shot）}}
$$

- **(I) Hopfield 項**：正解手列パターン数 $K(N) = 2^N - 1$ が容量 $\alpha_c D$ を超えるとスプリアスアトラクターが支配し `move_loop_repeat` 崩壊が生じる
- **(II) p-spin 項**：$p \geq 3$ で 1 段階 RSB が生じ、P(q) の二峰性を再現する。転移温度 $T_{SG \to PM}$ は **N に依存しない**（実験的に確認予定）
- **(III) 外部磁場項**：$n\text{-shot}$ が秩序相を安定化し $T_c$ を押し上げる

### 相図の概形

```
N
6  | ░░░░░░░░░░░░
5  | ▓░░░░░░░░░░░
4  | ▓▓▓░░░░░░░░░    ░ = 崩壊相（SG + PM）
3  | ▓▓▓▓▓▓░░░░░░    ▓ = 秩序相
2  | ▓▓▓▓▓▓▓▓▓░░░
   └──────────── T
     0.1  0.5  1.0
```

相境界 $T_c(N)$ のスケーリング則：

$$
T_c(N) = A \cdot N^{-\alpha} \quad \text{または} \quad T_c(N) = B \cdot e^{-\beta N}
$$

指数 $\alpha$（または $\beta$）が**モデルアーキテクチャによらず普遍**であることが主要な検証命題。

---

## 実験の現在地

### 使用モデル（全モデル動作確認済み）

| モデル | サイズ | think モード | VRAM |
|---|---|---|---|
| DeepSeek-R1-Distill-Qwen-7B | 7B | prefill | ~5 GB |
| DeepSeek-R1-Distill-Qwen-14B | 14B | prefill | ~10 GB |
| DeepSeek-R1-Distill-Llama-8B | 8B | prefill | ~6 GB |
| Qwen3-8B | 8B | chat\_template | ~6 GB |
| Qwen3-14B | 14B | chat\_template | ~10 GB |

### 実験パラメータ（メインスイープ）

```
モデル  : DeepSeek-R1-Distill-Qwen-7B（フェーズ 1）
N       : 2, 3, 4, 5, 6
T       : 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0  （0.1 刻み）
n-shot  : 0  （外部磁場なし、h = 0 の素の相転移を観測）
trials  : 25 / セル
総試行数: 5 × 10 × 25 = 1250
```

> **設計方針**：T ≥ 1.0 は全 N で崩壊相に入り試行が低速化するため、
> 崩壊相内部（SG vs PM）の精密解析は Algorithm E 実装後に別実験として実施する。
> 詳細は [`docs/experiment_ideas.md`](docs/experiment_ideas.md) を参照。

---

## リポジトリ構成

```
.
├── envs/
│   └── hanoi_env.py             # ハノイの塔の状態管理・採点
│
├── runners/
│   ├── run.py                   # 共通ユーティリティ（EarlyStopConfig など）
│   ├── run_local.py             # HuggingFace Transformers 版（NF4 量子化・隠れ状態キャプチャ付き）
│   ├── test_model_architecture.py  # 新モデル追加時の動作確認テスト
│   └── scripts/
│       ├── run_full_sweep.sh    # メインスイープ（相図 + P(q) + モデルスイープ対応）
│       └── run_scaling_sweep.sh # モデルスケーリング実験（VRAM 事前検証付き）
│
├── analysis/
│   ├── analyze_phase_diagram.py # 相図の描画・相境界 T_c(N) の推定
│   ├── analyze_pq.py            # P(q) 分布・q_EA・自己相関の計算
│   ├── analyze_slowing.py       # 臨界減速（first_move_step）の解析
│   └── plot_scaling.py          # N スケーリングのプロット
│
├── db/
│   ├── init.sql                 # スキーマ定義
│   ├── sync_one.py              # meta.json 1件を DB に同期
│   └── sync.sh                  # results/ 以下を一括 DB 同期
│
├── docs/
│   ├── experiment_design.md     # 相図実験の設計（案A/B/C）
│   ├── experiment_ideas.md      # 実験アイデア・実装候補（LoCM・有効ハミルトニアン・Algorithm E など）
│   ├── scaling_law_design.md    # スケーリング則実験の設計
│   ├── test_model_architecture_runbook.md  # 新モデル追加時の検証手順
│   └── Programming_Guide/       # Docker / Git / Python / SQL / Shell の学習ドキュメント
│
├── archive/                     # 旧スクリプト・設計書（参照用・実験からは除外）
├── results/                     # 実験結果（summary.json / meta.json を Git 管理）
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## セットアップ

### 前提

- Docker / Docker Compose
- NVIDIA GPU（VRAM 12 GB 以上推奨、RTX 5070 で動作確認済み）

### 起動

```bash
# コンテナをビルド & 起動
docker compose up -d --build

# コンテナに入る
docker compose exec hanoi-minimal bash
```

### 新モデルの動作確認（実験前に必ず実行）

```bash
# GPU なしで設定確認のみ
PYTHONPATH=/app python3 runners/test_model_architecture.py \
    --model-id <model_id> --no-gpu-tests

# 全テスト（T0〜T5）
PYTHONPATH=/app python3 runners/test_model_architecture.py \
    --model-id <model_id>
```

詳細は [`docs/test_model_architecture_runbook.md`](docs/test_model_architecture_runbook.md) を参照。

### 実験実行

```bash
# メインスイープ（デフォルト: 7B, N=2〜6, T=0.1〜1.0, 25試行, n-shot=0）
bash runners/scripts/run_full_sweep.sh --analyze

# 複数モデルをまとめてスイープ
bash runners/scripts/run_full_sweep.sh \
  --models "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B Qwen/Qwen3-8B" \
  --trials 25 --analyze

# 内容確認のみ（実行なし）
bash runners/scripts/run_full_sweep.sh --dry-run
```

### 解析

```bash
# 相図の描画（2相・3相）
python3 analysis/analyze_phase_diagram.py \
    --dir results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/

# P(q) 分布・q_EA（SG 判別）
python3 analysis/analyze_pq.py \
    --dir results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/

# 臨界減速
python3 analysis/analyze_slowing.py
```

### 実験結果の DB 同期

```bash
bash db/sync.sh
```

---

## 今後の実験方針

### フェーズ 1（現在進行中）：7B 単体での相図確立

- [x] 全 5 モデルの動作確認（T0〜T5 全通過）
- [x] N=2 フルグリッド完了（T=0.1〜1.0, 25試行）
- [ ] N=3〜6 スイープ完了
- [ ] 相図・P(q) 解析・相境界 $T_c(N)$ の推定
- [ ] 有効ハミルトニアンのパラメータ推定（$J_p$、$p$ の値）

### フェーズ 2：モデルスケーリング則

複数モデルで同一グリッドを測定し、スケーリング指数 $\alpha$ の普遍性を検証する。

$$
T_c(N,\ M) = A(M) \cdot N^{-\alpha}
$$

| 優先度 | モデル | 目的 |
|---|---|---|
| ★★★ | DeepSeek-R1-Distill-Qwen-14B | Qwen 系スケーリングの追加点 |
| ★★★ | DeepSeek-R1-Distill-Llama-8B | 異アーキテクチャでの普遍性確認 |
| ★★ | Qwen3-8B / Qwen3-14B | Reasoning 蒸留なし系列との比較 |

### フェーズ 3：タスク普遍性（LoCM 仮説）

ハノイ以外のパズル（蛙跳び・川渡り）で同一の相図実験を行い、
論理的複雑度 $\text{LoCM}(P) = \log_2(\text{最短手数})$ を横軸に揃えたとき
$T_c$ のスケーリング則がタスクを超えて普遍かを検証する。

**キラー実験**：蛙跳び $N=3$（LoCM = 3.91）とハノイ $N=4$（LoCM = 3.91）で $T_c$ が一致するか。

### 実装候補（コード改善）

| アイデア | 概要 | 前提条件 |
|---|---|---|
| Algorithm E | 最終手からの停滞アーリーストップ（T≥1.0 低速問題の解消） | N=3〜5 データ揃い次第 |
| Collapse-Phase Sweep | T=1.0〜3.0 の崩壊相内部を精密解析（SG vs PM 境界） | Algorithm E 実装後 |
| n-shot を制御変数に | 外部磁場 $h$ として相図上の転移消滅を観察 | フェーズ 1 完了後 |

詳細は [`docs/experiment_ideas.md`](docs/experiment_ideas.md) を参照。

---

## データ管理方針

実験結果は **PostgreSQL**（`db` コンテナ）と **Git**（`results/**/*.json`）の二重管理。

| データ種別 | 管理方法 | 備考 |
|---|---|---|
| `summary.json`・`meta.json` | Git + DB | 軽量、解析に頻用 |
| `*.npz`（隠れ状態ベクトル） | ローカルのみ | 大容量のため `.gitignore` 対象 |
| `figures/` | ローカルのみ | 再生成可能 |

---

## 関連ドキュメント

- [`docs/experiment_design.md`](docs/experiment_design.md) — 案A/B/C の詳細設計
- [`docs/scaling_law_design.md`](docs/scaling_law_design.md) — スケーリング則実験の設計
- [`docs/experiment_ideas.md`](docs/experiment_ideas.md) — LoCM・有効ハミルトニアン・Algorithm E などのアイデア集
- [`docs/test_model_architecture_runbook.md`](docs/test_model_architecture_runbook.md) — 新モデル追加時の検証手順
