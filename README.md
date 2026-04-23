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

| 相 | 特徴 | $\text{early\_stop}$ 内訳 |
|---|---|---|
| **秩序相** (Ordered) | $m \approx 1$、正確な解手列を生成 | `goal_reached` が支配的 |
| **スピングラス相** (Spin Glass) | $m \approx 0$、ループ崩壊 | `move_loop_repeat` が支配的 |
| **常磁性相** (Paramagnetic) | $m \approx 0$、手を出力しない | `move_ceiling` / no-move が支配的 |

### 有効ハミルトニアン

実験事実を整理する理論的枠組みとして、以下の有効ハミルトニアンを提案している：

$$
\mathcal{H} =
\underbrace{-\frac{1}{2D} \sum_{\mu=1}^{K(N)} \left( \sum_t \boldsymbol{\xi}_t^\mu \cdot \mathbf{h}_t \right)^2}_{\text{(I) Hopfield 項（N 駆動の転移）}}
\underbrace{-\frac{J_p}{p \cdot D^{p-1}} \sum_{t_1 \cdots t_p} \mathbf{h}_{t_1} \cdots \mathbf{h}_{t_p}}_{\text{(II) p-spin 項（T 駆動の転移）}}
\underbrace{- h \sum_t \boldsymbol{\xi}^* \cdot \mathbf{h}_t}_{\text{(III) 外部磁場項（n-shot）}}
$$

- **(I) Hopfield 項**：正解手列パターン数 $K(N) = 2^N - 1$ が容量 $\alpha\_c D$ を超えるとスプリアスアトラクターが支配し `move_loop_repeat` 崩壊が生じる
- **(II) p-spin 項**：$p \geq 3$ で 1 段階 RSB（Replica Symmetry Breaking）が生じ、P(q) の二峰性を再現する。転移温度 $T\_{SG \to PM} \approx 1.1$–$1.3$ は **N に依存しない**（実験的に確認済み）
- **(III) 外部磁場項**：$n\text{-shot}$ が秩序相を安定化し $T\_c$ を押し上げる

### 相図の概形

```
N
6  | ░░░░░░░░░░░░░░░░░░░
5  | ▓░░░░░░░░░░░░░░░░░░
4  | ▓▓▓░░░░░░░░░░░░░░░░    ░ = 崩壊相（SG + PM）
3  | ▓▓▓▓▓▓░░░░░░░░░░░░░    ▓ = 秩序相
2  | ▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░
   └───────────────────── T
     0.2  0.6  1.0  1.5  2.0
```

相境界 $T\_c(N)$ のスケーリング則：

$$
T_c(N) = A \cdot N^{-\alpha} \quad \text{または} \quad T_c(N) = B \cdot e^{-\beta N}
$$

指数 $\alpha$（または $\beta$）が**モデルアーキテクチャによらず普遍**であることが主要な検証命題。

---

## 実験内容と現在の結果

### 使用モデル

- **DeepSeek-R1-Distill-Qwen-7B**（HuggingFace、NF4 4-bit 量子化）
- **deepseek-r1:14b**（Ollama 経由）

### 実施済み実験

| 実験名 | 内容 | 結果ディレクトリ |
|---|---|---|
| `main` | N=2,3,4 の基本精度測定（Ollama） | `results/hanoi/results_N{N}_main.json` |
| `hf` | N=2,3 の基本精度測定（HuggingFace） | `results/hanoi/results_N{N}_hf/` |
| `temp_sweep` | N=3、T=0.2–0.6 の temperature スイープ | `results/hanoi/temp_sweep/` |
| `phase_diagram` | N=2–6、T=0.2–2.0 のフルグリッド（各 10 試行） | `results/hanoi/phase_diagram/` |
| `pq_sweep` | N=3–5、選択 T で 30 試行、P(q) 解析用 | `results/hanoi/pq_sweep/` |

### 主要な観測事実

- $N\_c \approx 2.5$–$3$ 付近で低温でも秩序相が消失する（Hopfield 容量超過点）
- $T\_{SG \to PM} \approx 1.1$–$1.3$ が N=3, 4, 5 で揃っている（p-spin 項の $J\_p$ が N に依らないことを示唆）
- P(q) 分布が双峰構造を示す条件でスピングラス相を確認（1 段階 RSB と整合）
- 臨界減速（first\_move\_step の T_c 付近での増大）を `analyze_slowing.py` で確認

---

## リポジトリ構成

```
.
├── envs/                        # 実験環境（タスク定義・評価ロジック）
│   └── hanoi_env.py             # ハノイの塔の状態管理・採点
│
├── runners/                     # 実験実行
│   ├── run.py                   # Ollama API 版
│   ├── run_hf.py                # HuggingFace Transformers 版（隠れ状態キャプチャ付き）
│   └── scripts/
│       ├── run_phase_diagram.sh # フルグリッドスイープ
│       ├── run_pq_sweep.sh      # P(q) 解析用スイープ
│       ├── run_scaling_sweep.sh # モデルスケーリング実験
│       └── run_temp_sweep.sh    # Temperature スイープ
│
├── analysis/                    # 実験解析・可視化
│   ├── analyze_phase_diagram.py # 相図の描画・相境界 T_c(N) の推定
│   ├── analyze_pq.py            # P(q) overlap 分布・q_EA の計算
│   ├── analyze_slowing.py       # 臨界減速（first_move_step）の解析
│   ├── analyze_temp_sweep.py    # Temperature スイープの可視化
│   └── plot_scaling.py          # N スケーリングのプロット
│
├── db/                          # PostgreSQL データ管理
│   ├── init.sql                 # スキーマ定義（experiments / trials テーブル）
│   ├── import_existing.py       # 既存 JSON の一括取り込み
│   ├── sync_one.py              # meta.json 1件を DB に同期
│   └── sync.sh                  # results/ 以下を一括 DB 同期
│
├── docs/                        # 実験設計書・アイデア集
│   ├── experiment_design.md     # 相図実験の設計（案A/B/C）
│   ├── scaling_law_design.md    # スケーリング則実験の設計
│   └── experiment_ideas.md      # 今後の実験アイデア（LoCM・有効ハミルトニアンなど）
│
├── results/                     # 実験結果（summary.json のみ管理、npz は .gitignore）
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## セットアップ

### 前提

- Docker / Docker Compose
- NVIDIA GPU（VRAM 12GB 以上推奨）
- Ollama（WSL2 ホスト上で稼働）

### 起動

```bash
# DB + 実験コンテナを起動
docker compose up -d

# 既存 JSON を DB に取り込む（初回のみ）
python3 db/import_existing.py
```

### 実験実行（コンテナ内から）

```bash
docker compose exec hanoi-minimal bash

# Temperature スイープ
bash runners/scripts/run_temp_sweep.sh

# フルグリッドスイープ（相図）
bash runners/scripts/run_phase_diagram.sh
```

### 新規実験結果の DB 同期

`meta.json` が存在するディレクトリが自動的に同期対象になる。
`run_hf.py` は実験開始時に `meta.json` を自動生成する。

```bash
bash db/sync.sh
```

### 解析

```bash
# プロジェクトルートから実行
PYTHONPATH=. python3 analysis/analyze_phase_diagram.py
PYTHONPATH=. python3 analysis/analyze_pq.py
PYTHONPATH=. python3 analysis/analyze_slowing.py
```

---

## 今後の実験方針

### Layer 1 完了条件（現在進行中）

- [x] フルグリッドスイープ（N=2–6, T=0.2–2.0）による相図の描画
- [x] P(q) 解析によるスピングラス相の確認
- [x] 臨界減速シグナルの検出
- [ ] 有効ハミルトニアンのパラメータ推定（$J\_p$、$p$ の値）

### Layer 2: モデルスケーリング則（次フェーズ）

複数モデルで同一グリッドを測定し、スケーリング指数 $\alpha$ の普遍性を検証する。

$$
T_c(N,\ M) = A(M) \cdot N^{-\alpha}
$$

| 優先度 | モデル | 目的 |
|---|---|---|
| ★★★ | DeepSeek-R1-Distill-Qwen-14B | Qwen 系スケーリングの 3 点目 |
| ★★★ | DeepSeek-R1-Distill-Llama-8B | 異アーキテクチャでの普遍性確認 |
| ★★ | Qwen2.5-7B-Instruct | Reasoning 蒸留なしで 3 相が出るか |
| ★ | DeepSeek-R1-Distill-Qwen-1.5B | $N\_c(M)$ スケーリングの下限点 |

### Layer 3: タスク普遍性（LoCM 仮説）

ハノイ以外のパズル（蛙跳び・川渡り）で同一の相図実験を行い、
論理的複雑度 $\text{LoCM}(P) = \log_2(\text{最短手数})$ を横軸に揃えたとき
$T\_c$ のスケーリング則がタスクを超えて普遍かを検証する。

$$
\text{LoCM}(P) = \log_2\bigl(\text{最短解の手数}\bigr)
$$

**キラー実験**: 蛙跳び N=3（LoCM=3.91）と ハノイ N=4（LoCM=3.91）で $T\_c$ が一致するか。

### その他の実験アイデア

| アイデア | 概要 | 優先度 |
|---|---|---|
| n-shot を制御変数に | 外部磁場 $h$ として相図上の転移消滅を観察 | B |
| LoCM 定義の比較 | log(手数) / log(状態空間) / Kolmogorov 複雑性での $\alpha$ 安定性 | C |

---

## データ管理方針

実験結果は **PostgreSQL**（`db` コンテナ）と **Git**（`results/**/*.json`）の二重管理。

| データ種別 | 管理方法 | 理由 |
|---|---|---|
| `summary.json`（試行サマリ） | Git + DB | 軽量、解析に頻用 |
| `*.npz`（隠れ状態ベクトル） | ローカルのみ | 267MB、Git 管理対象外 |
| `figures/` | ローカルのみ | 再生成可能 |

```
実験実行 → meta.json + summary.json 自動生成
         → bash db/sync.sh で DB に取り込み
         → git add / commit / push で JSON を記録
```

---

## 関連ドキュメント

- [`docs/experiment_design.md`](docs/experiment_design.md) — 案A/B/C の詳細設計
- [`docs/scaling_law_design.md`](docs/scaling_law_design.md) — スケーリング則実験の設計
- [`docs/experiment_ideas.md`](docs/experiment_ideas.md) — LoCM・有効ハミルトニアン・n-shot 実験のアイデア集
