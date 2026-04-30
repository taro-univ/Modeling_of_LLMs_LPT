# 実験アイデア集

思いついた実験・拡張の候補をためておくファイル。
優先度・実装コスト・期待される主張を整理する。

---

## Idea 1: マルチパズル普遍性 × LoCM

### 概要

ハノイの塔以外のパズル（蛙跳び・川渡りなど）で同一の phase diagram 実験を行い、
**論理的複雑度 LoCM を横軸に揃えることで T_c のスケーリング則がタスクを超えて普遍か**を検証する。

### 動機

現状の普遍性主張は「モデルサイズを変えても α が同じ」（モデル普遍性）。
パズル種を変えても α が同じなら**タスク普遍性**が示せ、主張が格段に強くなる。

Ising モデルと液体-気体転移が同じ臨界指数を持つ（普遍クラス）のと同型の主張。

### LoCM の定義

$$\text{LoCM}(P) = \log_2\bigl(\text{最短解の手数}\bigr)$$

| パズル | パラメータ | 最短手数 | LoCM |
|--------|-----------|---------|------|
| Hanoi  | N=2 | 3  | 1.58 |
| Hanoi  | N=3 | 7  | 2.81 |
| Hanoi  | N=4 | 15 | 3.91 |
| **Frog Jump** | **N=3** | **15** | **3.91** ← Hanoi N=4 と一致 |
| Hanoi  | N=5 | 31 | 4.95 |
| River Crossing (3,3) | — | 11 | 3.46 |

LoCM が同じ値のとき T_c も一致するか → **Frog N=3 vs Hanoi N=4 がキラー実験**。

### キラー実験の構造

```
Frog Jump N=3  (LoCM = 3.91)  →  T_c = ?
Hanoi     N=4  (LoCM = 3.91)  →  T_c = ?

両者が一致すれば「T_c は LoCM のみで決まる」= タスク普遍性の直接証拠
```

### 候補パズルと実装コスト

| パズル | 環境実装 | LoCM の解析表現 | 優先度 |
|--------|---------|----------------|--------|
| 蛙跳び (Frog Jump) | 易 | $N^2 + 2N$ | ★★★ |
| 川渡り (River Crossing, N人 vs N人) | 中 | BFS で求まる | ★★ |
| Missionaries & Cannibals | 中 | 既知（小さい） | ★★ |
| Lights Out | 難 | GF(2) 線形代数 | ★ |

**最初の実装ターゲット: 蛙跳び**
- 実装がシンプル（状態 = リスト、合法手 = 隣接空白へのジャンプ）
- LoCM が Hanoi と綺麗に重なる
- `hanoi_env.py` と同じインターフェースで書ける

### 懸念点・注意事項

- **LoCM の正当化**: log₂(手数) は直感的だが、Shannon 情報量・Kolmogorov 複雑性との接続を議論すると強くなる
- **プロンプト設計の統一**: パズルごとにフォーマットが変わると T_c の差がタスク複雑度由来か指示形式由来か分離できない。フォーマットを揃える設計が必要
- **川渡りは状態空間が小さい**: M&C(3,3) は LoCM=3.46 と低め。N人 vs N人 にスケールする必要あり

### 実装メモ（未着手）

```python
# 必要なファイル
frog_env.py          # FrogJumpEnv クラス（hanoi_env.py と同インターフェース）
river_env.py         # RiverCrossingEnv クラス

# run_hf.py の変更
--env frog / hanoi / river  # 環境切り替えフラグを追加
```

---

## Idea 2: スケーリング則の抽出（モデル普遍性）

→ `docs/scaling_law_design.md` に詳細あり。

複数モデル（14B, Llama-8B, 1.5B など）で同一グリッドを測定し、
$T_c(N, M) = A(M) \cdot N^{-\alpha}$ の指数 $\alpha$ がモデルによらず一定かを検証する。

---

## Idea 3: LoCM の代替定義の比較

### 概要

LoCM の定義が結論に影響しないかを確認するため、複数の定義でスケーリング則を比較する。

| 定義名 | 式 | 特徴 |
|--------|---|------|
| LoCM-L | $\log_2(\text{最短手数})$ | 最もシンプル |
| LoCM-S | $\log_2(\|\text{状態空間}\|)$ | 探索的難しさを反映 |
| LoCM-B | $\log_2(\text{分岐数} \times \text{深さ})$ | BFS 複雑度に対応 |
| LoCM-K | Kolmogorov 複雑性の近似 | 理論的に最も厳密だが計算困難 |

どの定義でも α が変わらなければ、LoCM の定義に対する**頑健性**の主張になる。

---

## Idea 4: n-shot を制御変数にした実験

### 概要

現状 n-shot は固定パラメータ（外部磁場）として除外しているが、
これを変化させると「外部磁場強度 h に対する相図」が描ける。

$$m(N, T, h) \quad h = n\text{-shot}$$

スピン系では外部磁場 h > 0 で相転移が消える（クロスオーバーになる）。
n-shot を増やすと T_c が上昇するか？崩壊が起きなくなるか？

### 設計メモ

```
N = 4（14B で境界付近）
T = 0.2, 0.4, ..., 1.5
n-shot = 0, 1, 2, 3, 4
trials = 20
```

---

## Idea 5: 隠れ状態の臨界減速（Critical Slowing Down）

### 概要

相転移点付近では**臨界減速**が現れる：

$$\tau_{\text{relax}} \sim |T - T_c|^{-z\nu}$$

LLM では「最初の Move が出るまでのトークン数（first_move_step）」が
緩和時間 $\tau$ に対応する可能性がある。

T_c 付近で first_move_step が発散するか → 早期警戒指標としての応用。

### 必要データ

`pq_sweep` の npz から `move_steps[0]`（最初の Move のトークン位置）を集計するだけで検証可能。**追加実験不要**。

---

## Idea 6: 有効ハミルトニアンによる系の記述

### 概要

phase_diagram と pq_sweep の結果（特に P(q) の二峰性・T_{SG→PM} の N 非依存性）を踏まえ、
LLM の推論軌跡を統計力学的に記述する有効ハミルトニアンを提案する。

推論軌跡 $\{\mathbf{h}_t\}_{t=1}^{L}$（各ステップの隠れ状態ベクトル）を系のスピン配位とみなす。

### 提案ハミルトニアン

$$\mathcal{H} =
\underbrace{-\frac{1}{2D} \sum_{\mu=1}^{K(N)} \left( \sum_t \boldsymbol{\xi}_t^\mu \cdot \mathbf{h}_t \right)^2}_{\text{(I) Hopfield 項}}
\underbrace{-\frac{J_p}{p \cdot D^{p-1}} \sum_{t_1 \cdots t_p} \mathbf{h}_{t_1} \cdots \mathbf{h}_{t_p}}_{\text{(II) p-spin 項}}
\underbrace{- h \sum_t \boldsymbol{\xi}^* \cdot \mathbf{h}_t}_{\text{(III) 外部磁場項}}$$

### 各項と実験観測の対応

#### (I) Hopfield 項 — N 駆動の転移

- $\boldsymbol{\xi}^\mu$：ハノイの正解手列パターン（記憶パターン）
- $K(N) = 2^N - 1$：N に対して指数的に増加
- Hopfield 容量 $\alpha_c \approx 0.138$ を超えると（$K(N) > \alpha_c D$）スプリアスアトラクターが支配的になる
- `move_loop_repeat` の正体 = スプリアスアトラクターへの凍結
- $N_c \approx 2.5$ はこの容量超過点に対応

#### (II) p-spin 項 — T 駆動の転移（p ≥ 3 で一段階 RSB）

- P(q) の二峰性を再現する（p ≥ 3 で RSB が生じる）
- $J_p$ はモデルの学習済み重みで決まり、N に依存しない
- **実験的根拠**：T_{SG→PM} ≈ 1.1–1.3 が N=3,4,5 で揃っている（N 非依存）
- T 駆動転移はタスク難度ではなくモデル内部の性質

#### (III) 外部磁場項 — n-shot の効果

- $h > 0$ が秩序相を安定化し $T_c$ を押し上げる
- n-shot = 0 で磁場なし → 相転移がシャープ
- n-shot を増やすと転移がクロスオーバーに変わる（Idea 4 で検証可能）

### 実験から読み取れる制約の整理

| 観測事実 | ハミルトニアンへの制約 |
|---------|----------------------|
| $N_c \approx 2.5$ で秩序→崩壊 | (I) の容量超過点 |
| T_{SG→PM} ≈ 1.1–1.3 が N 非依存 | (II) の $J_p$ が N に依らない |
| P(q) の二峰性（RSB） | (II) の p ≥ 3 が必要 |
| n-shot が秩序相を安定化 | (III) の外部磁場 |
| `move_loop_repeat` = 異アトラクター | (I) のスプリアスアトラクター |

### 相図との対応

```
         T
  高 │  paramagnetic  （p-spin 項が支配、Hopfield 項は熱で消える）
     │
T_c  │- - - - - - - - (II) の転移線（N 非依存、T≈1.1–1.3）
     │  spin glass
     │  （Hopfield スプリアスアトラクター + p-spin RSB）
  低 │_____________________ ordered
          N=2   N_c≈2.5   N=3,4,5
                 (I) の容量超過点
```

### Idea 1 との接続（重要）

p-spin 結合 $J_p$ はモデルの重みで固定されるため、
**異なるパズルでも同じモデルを使えば T_{SG→PM} は同じ値になるはず**。

> LoCM が変わっても T の転移点が変わらなければ、(II) の p-spin 普遍性の直接証拠。

これが Idea 1（マルチパズル × LoCM）の理論的根拠になる。

### 今後の検証実験

| 検証内容 | 方法 | 優先度 |
|---------|------|--------|
| $J_p$ の推定（転移温度から逆算） | p-spin モデルの $T_c = \sqrt{p J_p^2 / 2}$ に当てはめ | ★★★ |
| p の値の推定（P(q) の形状から） | RSB の構造（連続 vs 一段階）を解析 | ★★ |
| n-shot による $T_c$ シフトの定量化 | Idea 4 の実験（$h$ vs $\Delta T_c$） | ★★ |
| 異パズルで T_{SG→PM} が保存されるか | Idea 1 の実験（Frog Jump vs Hanoi） | ★★★ |

---

## アイデアの優先度まとめ

| Idea | 新規性 | 実装コスト | 優先度 |
|------|--------|-----------|--------|
| 1: マルチパズル × LoCM | ★★★ 高 | 中（env 実装） | **A** |
| 2: モデルスケーリング則 | ★★ 中 | 低（スクリプトあり） | **A** |
| 6: 有効ハミルトニアン | ★★★ 高 | 低（理論整理） | **A** |
| 5: 臨界減速 | ★★ 中 | 低（既存 npz で可） | **B** |
| 4: n-shot 制御変数 | ★★ 中 | 低（$J_p$ 検証につながる） | **B** |
| 3: LoCM 定義の比較 | ★ 低 | 低 | **C** |

---

## 実装候補（コード改善）

### Algorithm E: 最終手からの停滞アーリーストップ + Algorithm D 閾値改訂

#### 解消対象ボトルネック

データ探索（`phase_diagram`, `pq_sweep`）から、実験を長引かせている原因が 4 つ特定された。

| # | ボトルネック | 代表例 | 損失時間 |
|---|---|---|---|
| B1 | moves=1 後の長時間停滞 | N4_T1_5 trial9 (883s), pq_sweep N4_T1_2 trial19 (556s) | 200〜880s |
| B2 | Algorithm D の `no_move_ratio=0.50` が高すぎて PM 相全体が遅い | N4_T2_0 全試行 163〜177s, N5_T2_0 全試行 155〜183s | 160〜210s/trial |
| B3 | moves≥2 後の停滞（Algorithm E の対象だが moves=1 限定の記述になっていた） | N5_T1_2 trial8 (moves=4, 198s), trial7 (moves=15, 157s) | 100〜200s |
| B4 | `len(text)/3.5` による文字数近似のズレ（reasoning=0 試行で特に大きい） | T=2.0 で発動 total_tokens が 1500〜1640 とばらつく | B2 対策で緩和 |

---

#### Algorithm E の設計（B1・B3 を解消）

> **最後の手が出てから `stagnation_ratio × num_predict` トークン分、新たな手が出なければ打ち切る。**
> moves=1 に限定せず、`last_move_token_pos` を基点とした moves≥1 全般を対象とする。

```python
# EarlyStopConfig に追加するパラメータ
stagnation_ratio: float = 0.20   # num_predict × 0.20 tok 無手で打ち切り
enable_stagnation: bool = True
```

`check_early_stop` の呼び出し側で現在の累積トークン位置（`current_token_pos`）と
最後に手が抽出された位置（`last_move_token_pos`）を管理し、次の条件で発動する。

```python
if last_move_token_pos is not None:
    gap = current_token_pos - last_move_token_pos
    if gap > num_predict * stagnation_ratio:
        return "stagnation_after_move"
```

`last_move_token_pos` はストリーミングループ内で `moves = _MOVE_RE.findall(accumulated)` の
件数が増えるたびに `current_token_pos` で更新する。

**誤発動しないことを確認済みのケース:**

- 秩序相（acc=1）: 全手が平均 534 tok・最大 1621 tok 以内に完成 → stagnation 閾値 (4096×0.20=819 tok) を超えない
- SG 相（`move_loop_repeat`）: Algorithm C が先に発動するため Algorithm E と衝突しない
- moves 数は正しいが不正解（e.g., moves=7 で acc=0）: 手が途切れずに完了するため停滞なし

**N が大きい場合の注意:**

- N が増えると手と手の間の推論時間も伸びる可能性がある
- `stagnation_ratio × num_predict` を固定比率にすることで N=6 (num_predict=8192) でも自動スケールする
- N=6 以上のデータが揃い次第 ratio を再検証すること（現時点の根拠は N=3〜5）

---

#### Algorithm D 閾値改訂（B2・B4 を緩和）

**変更内容:** `no_move_ratio` を `0.50` → `0.25` に引き下げる。

```python
# EarlyStopConfig の変更
no_move_ratio: float = 0.25   # 旧: 0.50
```

**根拠:**

- PM 相（T≥1.5）では moves=0 の試行が `no_move_ratio=0.50` (≈ 2048 est_tok) まで待つことで
  1 試行あたり 160〜210s かかっていた
- `no_move_ratio=0.25` (≈ 1024 est_tok) にすれば発動を約半分の時点に前倒しでき、
  **1 試行あたり 80〜100s 節約**できる

**誤発動リスクの確認:**

- 秩序相（T<1.0）の最初の手は N=3〜5 いずれも 500 tok 以内に出現しており、
  閾値 1024 est_tok ≈ 3584 chars を超える前に手が抽出される → 誤発動しない
- 境界付近（T≈1.0）の試行は moves=0 でも reasoning が長く続くが、
  Algorithm A（think_budget）が先に発動するケースが多く、D との干渉は軽微

**B4（文字数近似のズレ）について:**

`no_move_ratio` を 0.25 に引き下げることで発動の絶対位置が前倒しになり、
ズレの影響（±20%）が小さくなる。`eval_count` ベースへの切り替えは将来課題とする。

---

#### 実装優先順序

1. `no_move_ratio` を 0.25 に変更（1 行の変更、即効性が高い）
2. `EarlyStopConfig` に `stagnation_ratio` / `enable_stagnation` を追加
3. `query_ollama` のストリーミングループに `last_move_token_pos` 更新ロジックを追加
4. `check_early_stop` に `stagnation_after_move` 条件を追加（または呼び出し側で処理）
5. Collapse-Phase Sweep 実験を実施して閾値を再検証

---

## 実験 "Collapse-Phase Sweep"（T≥1.0 領域の精密解析）

### 位置づけ

メインスイープ（`full_sweep`）は T=0.1〜1.0 の秩序相〜相境界を対象とする。
T≥1.0 は全 N で acc≈0（崩壊相）であり、相図の描画には不要。
しかし崩壊相の**内部構造**（SG vs PM の境界・崩壊モードの温度依存性）は
別実験として精密に解析する価値がある。

### 前提条件

- **Algorithm E の実装完了後**に実施（T≥1.0 は低速試行が多発するため必須）
- `--sweep-type collapse_phase` として `full_sweep` とは独立したディレクトリに保存

### パラメータ案

```
T      = 1.0, 1.1, 1.2, 1.3, 1.5, 1.8, 2.0, 2.5, 3.0
N      = 3, 4, 5   （N=2 は T=1.0 で既に崩壊済みのためスキップ）
trials = 30        （P(q) 解析に十分な統計量）
```

### 解析対象指標

- P(q) 分布の双峰性（SG相）vs q≈0 集中（PM相）
- fallback rate（no_move_catchall 比率）の T 依存性
- q_EA の T 依存性 → SG→PM 転移温度 $T_{SG→PM}(N)$ の推定

### スクリプト案（Algorithm E 実装後）

```bash
bash runners/scripts/run_full_sweep.sh \
  --ts "1.0 1.1 1.2 1.3 1.5 1.8 2.0 2.5 3.0" \
  --ns "3 4 5" \
  --trials 30 \
  --analyze
```
