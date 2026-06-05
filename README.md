# Modeling of LLMs — Phase Transition in Logical Problem-solving Tasks (LPT)

LLM の推論崩壊を**統計力学的相転移**として定量的に記述する実験・理論リポジトリ。
生成温度 $T$（ノイズ強度）とタスク複雑度 $N$ の 2 変数空間で、推論が秩序状態から崩壊状態へ転移する現象を実験・隠れ状態解析・理論モデリングの三本柱で研究する。

---

## 主要な発見（2026-06-06 時点）

### 1. 4 つの動力学レジーム

当初の「3 相（秩序・SG・PM）」仮説を精緻化し、LLM の推論崩壊には**4 つの動力学レジーム**が存在することを L2 隠れ状態解析から実証した。

| レジーム | 行動的特徴 | 隠れ状態 ($q_{EA}$) | 出現条件 |
|---|---|---|---|
| **Reasoning-ordered** | 正確な解を生成 | 固定点アトラクター | 低温 × 低複雑度 |
| **Recitation-ordered** | 解を暗記復唱（短 token） | Ω=1 の単一鋭 basin | 中〜高温（Qwen3 系のみ） |
| **Oscillatory** | 同じ手を繰り返す | 非勾配循環（NESS 候補） | 中間温度 × 高複雑度 |
| **PM** | 手を出力しない | 拡散的、構造なし | 高温 |

### 2. Asymmetric Melting（Qwen vs DeepSeek の違い）

RLVR 訓練（Qwen3 系）は中〜高温で「**推論が先に崩壊し、記憶想起チャネルが相対的に露出する**」窓（recitation-ordered）を形成する。SFT/蒸留訓練（DeepSeek-R1-Distill 系）はこの窓を持たず、推論崩壊が直接 PM に向かう。

$$
\Delta F(T) = (E_\text{reason} - E_\text{recit}) - T(\underbrace{S_\text{reason}}_{\text{大（多様な探索軌道）}} - \underbrace{S_\text{recit}}_{\approx 0\ (\Omega=1)})
$$

高温で reasoning の $-TS_\text{reason}$ が不利化 → recitation basin が相対露出（*asymmetric melting*）。

### 3. 非勾配 Langevin による H_eff 定式化

従来の平衡ハミルトニアン H から、**非勾配 Langevin**（散逸構造・NESS）へ更新：

$$
\dot{h} = -\underbrace{\nabla V(h)}_{\text{多井戸ポテンシャル}} + \underbrace{A(h)}_{\text{非保存力（循環）}} + \sqrt{2T}\,\xi(t)
$$

- $-\nabla V$：reasoning 井戸（広く浅い）+ recitation 井戸（Ω=1、狭く深い）
- $A(h)$：Oscillatory レジームを生む回転成分（NESS 確率カレント候補）
- 制御モデル（最終目標）は「$A(h)$ を打ち消す外力を加えて reasoning basin へ誘導する」として再解釈

---

## 物理的背景

### LLM 推論と統計力学の対応

| LLM の変数 | 統計力学での対応 |
|---|---|
| 生成温度 $T$ | 熱浴温度・ノイズ強度 |
| 複雑度 $N$（円盤数） | システムサイズ・エネルギー障壁 |
| 対称化 accuracy $m$ | 秩序変数（B/C ゴールペグの gauge 等価性を考慮） |
| $p_\text{recit}(T)$ | recitation basin のアクセス確率（順序変数） |
| $n\text{-shot}$ | 外部磁場（秩序を安定化） |

### 相図の現在地（B/C 対称化 accuracy 使用）

```
  N
  6 | ░░░░░░░░░░░░░
  5 | ▓░░░░░░░░░░░░     ▓ = Reasoning-ordered
  4 | ▓▓░░░░░░░░░░░     ░ = Oscillatory + PM（崩壊）
  3 | ▓▓▓▓▓▓░░░░░░░     ◇ = Recitation-ordered（Qwen のみ）
  2 | ▓▓▓▓▓▓▓▓▓◇◇░     
    └──────────────── T
      0.1  0.5  1.0  2.0
```

$T_{c2}$（SG→PM 境界）は DeepSeek 系で $N$ に非依存（$T_{c2}\approx1.0$–$1.2$）— H5（非平衡 SG）の定量的根拠。

---

## 実験の現在地

### 完了した実験（Tower of Hanoi）

4 モデル軸 × (full_sweep + collapse_phase) の全データが揃った（2026-06-05）。

| モデル | 訓練方式 | full_sweep | collapse_phase | Recitation |
|---|---|---|---|---|
| DeepSeek-R1-Distill-Qwen-7B | SFT 蒸留 | ✅ 50/50 | ✅ 36/36 | なし（0件） |
| DeepSeek-R1-Distill-Qwen-14B | SFT 蒸留 | ✅ 51/52 | ✅ 36/36 | ほぼなし（≈16件） |
| Qwen3-8B | RLVR | ✅ 50/50 | ✅ 36/36 | 少量（≈29件） |
| Qwen3-14B | RLVR | ✅ 51/52 | ✅ 36/36 | 多量（≈175件） |

> **注意**：ゴールペグ B/C の gauge 等価性を考慮した対称化 accuracy を使用（`research_state/symmetric_accuracy.json`）。

### 進行中の実験

- **Lights Out パズル**（DeepSeek-7B + Qwen3-8B）：Hanoi 以外のパズルで recitation が出るかを検証中

---

## リポジトリ構成

```
.
├── envs/
│   ├── hanoi_env.py          # Tower of Hanoi（B/C 対称化済み）
│   └── lights_out_env.py     # Lights Out パズル
│
├── runners/
│   ├── run.py                # 共通ライブラリ（早期終了・EarlyStopConfig）
│   ├── run_local.py          # HuggingFace Transformers 版（NF4 量子化・隠れ状態 npz 保存）
│   └── scripts/
│       ├── run_full_sweep.sh          # メインスイープ（T=0.1〜1.0）
│       ├── run_collapse_phase_sweep.sh # 崩壊相精密スキャン（T=1.1〜3.0）
│       ├── run_lights_out_sweep.sh    # Lights Out フルスイープ
│       └── ...
│
├── analysis/
│   ├── run_pipeline.py       # 統合解析パイプライン（相図・P(q)・臨界減速）
│   ├── phase_transition.py   # 相図・T_c 推定
│   ├── spin_glass.py         # P(q) 分布・q_EA・qbar
│   ├── critical_dynamics.py  # 臨界減速解析
│   └── adhoc/                # セッション別の探索的解析スクリプト
│
├── research_state/
│   ├── hypotheses.md         # 仮説（H3〜H7'）と証拠の記録
│   ├── results_summary.md    # 確認済み観測事実
│   ├── experiment_register.md # 実験台帳（EXP-001〜008）
│   └── symmetric_accuracy.json # B/C 対称化 accuracy（全 432 セル）
│
├── specs/
│   ├── draft/                # 壁打ち中の仕様書
│   └── final/                # 確定済み仕様書
│
├── results/
│   ├── hanoi/full_sweep/     # 各モデルの summary.json・meta.json
│   ├── hanoi/collapse_phase/ # 崩壊相スキャン結果
│   └── lights_out/           # Lights Out 実験結果（進行中）
│
├── db/
│   ├── init.sql              # PostgreSQL スキーマ
│   └── sync.sh               # results/ → DB 一括同期
│
├── tests/
│   └── test_early_stop.py    # Algorithm C/D/E の単体テスト
│
├── Dockerfile
├── docker-compose.yml
└── watch_experiments.py      # 実験進捗モニタリングツール
```

---

## セットアップ

### 前提

- Docker / Docker Compose
- NVIDIA GPU（VRAM 12 GB 以上推奨、RTX 5070 / CUDA 13.1 で動作確認済み）
- HuggingFace Hub アクセス（各モデルのダウンロード権限）

### 起動

```bash
docker compose up -d --build
docker compose exec hanoi-minimal bash
```

コンテナ内では `/app` がプロジェクトルート、`PYTHONPATH=/app` が設定済み。

### 実験実行（コンテナ内）

```bash
# Tower of Hanoi フルスイープ（T=0.1〜1.0）
bash runners/scripts/run_full_sweep.sh \
    --models "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B" \
    --trials 25 --analyze

# 崩壊相精密スキャン（T=1.1〜3.0）
bash runners/scripts/run_collapse_phase_sweep.sh \
    --models "Qwen/Qwen3-14B" --trials 25

# Lights Out パズル
bash runners/scripts/run_lights_out_sweep.sh \
    --models "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B Qwen/Qwen3-8B"
```

### 解析

```bash
# 統合解析パイプライン（相図・P(q)・臨界減速）
python3 analysis/run_pipeline.py \
    --data-dir results/hanoi/full_sweep/qwen3-8b/ \
    --out-dir figures/full_sweep/qwen3-8b/ \
    --title "Qwen3-8B" \
    --analyzers phase_transition spin_glass
```

---

## 今後の方針

### 現在の最優先課題

1. **Lights Out 実験の解析**：DeepSeek vs Qwen の recitation 有無を確認 → 次パズルの採択を決定
2. **次パズルの実装**（以下のいずれか）：
   - **N-puzzle（スライドパズル）**：seed varying で recitation を排除 → 普遍 H_eff の fitting 用
   - **Frog Jump**：$K(N) = N(N+2)$（多項式）→ H7' の L スケーリング則の検証用
3. **H_eff の構築**：非勾配 Langevin $\dot{h} = -\nabla V + A + \sqrt{2T}\xi$ のパラメータを実験データからフィット
4. **制御モデル**：$A(h)$ を打ち消す外力設計 → 推論が詰まった状態を秩序相へ戻す介入

### 締切

- **2026-06-30**：モデリング完了（H_eff パラメータフィット）
- **2026-07**：中間報告（ハミルトニアン構築 + シミュレーション成功）

---

## データ管理

| データ種別 | 管理方法 | 備考 |
|---|---|---|
| `summary.json` / `meta.json` | Git + PostgreSQL | 全実験ログ（432 セル） |
| `*.npz`（隠れ状態ベクトル） | ローカルのみ | 大容量のため `.gitignore` 対象 |
| `figures/` | ローカルのみ | 再生成可能 |

---

## 関連ドキュメント

- [`research_state/hypotheses.md`](research_state/hypotheses.md) — 仮説（H3〜H7'）の詳細と証拠
- [`research_state/results_summary.md`](research_state/results_summary.md) — 確認済み観測事実
- [`docs/phase_classification_review.md`](docs/phase_classification_review.md) — 相分類の精緻化経緯
- [`CLAUDE.md`](CLAUDE.md) — Claude Code 向けの詳細な実験・コード仕様
