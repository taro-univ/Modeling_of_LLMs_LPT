# 相分類アルゴリズム 問題点レポート

調査日：2026-05-21  
調査対象：`analysis/analyze_integrated.py`, `analysis/analyze_pq.py`, `analysis/analyze_phase_diagram.py`  
physics-agent 判定：**不合格（要再設計）**

---

## サマリー

現行の相分類アルゴリズム（`classify_phase`）は、早期終了ラベル率とスカラー q_EA の閾値判定によって
秩序相 / SG 相 / PM 相を分類している。physics-agent 審査の結果、以下の 4 点を主な理由として
**スピングラス理論との整合性が成立しない**と判定された：

1. `q_EA` と称している量がエドワーズ–アンダーソン秩序変数ではない
2. SG 相判定に P(q) の分布特性を使っていない
3. 同一概念の実装が 3 ファイルに分散し閾値が不一致
4. LLM hidden state の等方性問題（コサイン類似度のベースラインが 0.7–0.9 付近）

**対処方針（2026-05-21 壁打ちで確定）**：P(q) moments ベースへの全面再設計（A案）で進める。
先行して診断スクリプト（SPEC-2026-05-21-001）を実装・実行し、stagnation_after_move の帰属を確認してから再設計仕様書を作成する。

---

## 現行アルゴリズムの構造

### `analyze_integrated.py:185–194`

```python
def classify_phase(cond, q_ea=None):
    acc = mean(cond["accuracy"])
    if acc > 0.4:           return "ordered"         # ① 秩序相
    if pm_rate > 0.5:       return "paramagnetic"     # ② PM 相
    if sg_rate > 0.3 or
       q_ea > 0.70:         return "spin_glass"       # ③ SG 相
    return "mixed"                                    # ④ 残余
```

```python
pm_rate = rate({"no_move_catchall", "move_ceiling"})
sg_rate = rate({"move_loop_repeat", "move_loop_reverse"})
```

```python
# compute_qea — analyze_integrated.py:146–157
# 試行内の異ステップ間コサイン類似度の平均（q_EA と称しているが別物）
vals.append(_cosine(H[i], H[j]))  # 同一試行、異ステップ
```

---

## 問題点一覧

### 🔴 Critical（ハミルトニアン fitting・モデリング進行のブロッカー）

#### C1. `q_EA` の定義が Edwards-Anderson 秩序変数ではない

**現行実装**：試行内の異なるステップ間コサイン類似度の平均（時間自己相関に近い量）

**Edwards-Anderson 秩序変数の正定義**：同一 quenched disorder を持つ独立レプリカ間の overlap の典型値

$$q_{EA} = \lim_{t \to \infty}\overline{\langle \sigma_i(0)\sigma_i(t) \rangle_J}
\quad \text{または} \quad
q_{EA} = \overline{\langle \sigma_i^a \sigma_i^b \rangle}\ (\text{2 replica 間})$$

一方、`compute_pq`（試行間の時間平均 hidden state コサイン類似度）のほうが P(q) 構造に近い。
**コードラベルが逆である可能性が高い。**

**影響**：`q_EA > 0.70` という SG 判定基準が物理的根拠を持たない。

---

#### C2. SG 相判定に P(q) の分布特性を使っていない

SG 相の本質的特徴：

- P(q) の双峰性（ordered overlap と near-zero overlap の 2 峰）
- 有限の分布幅（非自己平均性：$\Delta_q = \overline{\langle q^2 \rangle} - \overline{\langle q \rangle}^2 > 0$）
- Binder cumulant の有限サイズスケーリング
- 超計量性（ultrametricity）

現行は「早期終了ラベル比率 + スカラー q_EA」だけで判定しており、上記を一切使っていない。
H3・H4 の定量的検証に使えない。

---

#### C3. hidden state コサイン類似度のベースライン問題

LLM hidden state $h \in \mathbb{R}^{4096}$ は強い共通方向（平均ベクトル $\mu$）を持つ：

$$h = \mu + \delta, \quad \|\mu\| \gg \|\delta\|$$

$$\Rightarrow \cos(h_a, h_b) \approx 1 - O\!\left(\frac{\|\delta\|^2}{\|\mu\|^2}\right)$$

結果として、どの相のどの試行ペアでもコサイン類似度が 0.7–0.9 付近に集中する。
`q_EA > 0.70` という閾値は、無相関な random hidden state ペアのベースラインと区別できない可能性がある。

**解決策**：centering（$h' = h - \mu$）+ whitening（等方化）によりスピングラス理論のスピン（平均 0）との対応を成立させる（Q4：等方化を入れる方向で確定）。

---

#### C4. 同一概念の実装が 3 ファイルに分散し閾値が不一致

| ファイル | PM 閾値 | SG 判定条件 | Tc 閾値 |
|---|---|---|---|
| `analyze_integrated.py:185` | `pm_rate > 0.5` | `sg_rate > 0.3` **OR** `q_EA > 0.70` | `_find_tc`: 0.15 |
| `analyze_pq.py:224` | `pm_rate > 0.6` | `q_EA > 0.70` のみ（sg_rate チェックなし） | — |
| `analyze_phase_diagram.py:30` | — | — | `BOUNDARY_THRESHOLD = 0.5` |

同じデータから **3 通りの異なる相図が生成されうる状態**にある。

---

### 🟠 High（早急に対処すべき問題）

#### H1. `stagnation_after_move` と `think_budget` が pm_rate に未算入

`hypotheses.md` の PM 定義：`{no_move_catchall, move_ceiling, stagnation_after_move, think_budget}`

`pm_rate` の実計算（`analyze_integrated.py:120` および `analyze_pq.py:112`）：
`{no_move_catchall, move_ceiling}` のみ → 2 ラベル分欠落。

さらに `stagnation_after_move` は SG 的解釈も成立しうる（Algorithm E の動作：手を ≥1 個出した後に停止）。
**コードと仮説定義が乖離しており、どちらに帰属させるかが未確定。**

→ SPEC-2026-05-21-001 の診断スクリプトで実証的に判定する。

---

#### H2. 判定優先順位の問題

```
ordered(acc > 0.4) → PM → SG → mixed
```

`acc > 0.4` を先に判定するため、**「時々正解に当たるが本質は凍結 SG 状態」のセルが ordered に誤分類される**可能性がある。

観測データ（N=3, 7B, T=0.1–0.6）では acc 0.36–0.68 と未飽和。低温域で SG が残存していても
accuracy 単独では Ordered と SG を区別できない。

物理的に正しい優先順位の提案：
1. P(q) の分布特性（非自己平均性）で SG を最優先判定
2. accuracy で Ordered を判定
3. PM は残余

---

#### H3. `think_budget` の相分類への参入問題

`think_budget`（思考トークンが予算上限に達して終了）は**推論崩壊の観測ではなく計測上の打ち切り**。
相の物理的シグナルとして使うべきではない。

→ 相分類の計算から除外し、**censored data** として扱うべき（打ち切り分を除いた実効試行数で正規化）。

---

#### H4. 閾値がすべて根拠不明のマジックナンバー

| 閾値 | 用途 | 物理的根拠 |
|---|---|---|
| `acc > 0.4` | ordered 判定 | なし（ランダムベースラインとの有意差ではない） |
| `pm_rate > 0.5` | PM 判定 | なし（経験則） |
| `pm_rate > 0.6` | PM 判定（pq 版） | なし（integrated 版と不一致） |
| `sg_rate > 0.3` | SG 判定 | なし（PM と非対称） |
| `q_EA > 0.70` | SG 補助判定 | なし（hidden state ベースライン問題と矛盾） |
| `BOUNDARY_THRESHOLD = 0.5` | Tc 推定（phase_diagram） | なし |
| `_find_tc threshold = 0.15` | Tc 推定（integrated） | なし、かつ 0.5 と不一致 |

P(q) 解析によって SG/PM 転移温度を決定したうえで、閾値を逆算する設計に変更すべき。

---

### 🟡 Medium（設計改善として対処）

#### M1. `mixed` カテゴリの物理的解釈が未定義

ordered/PM/SG のいずれの条件も満たさないセルを `"mixed"` と呼んでいるが、以下の 3 通りの可能性を区別できていない：

- 測定データ不足（サンプリング不足の誤分類）
- 相境界（転移点付近の fluctuation が大きい領域）
- 真の相共存（1 次相転移のコイステンス領域）

再設計では `undetermined`（データ不足）と `transitional`（境界域）に分割することを検討。

---

#### M2. 閾値感度解析がない

4 つの閾値（0.4, 0.5, 0.3, 0.70）をそれぞれ ±0.1 揺らがせたときに相図がどう変わるかが未検証。
物理的相転移なら相図はロバストであるべき（Tc 位置が閾値選択によらず安定）。
再設計後に感度解析を実施する。

---

## 調査で判明した追加問題：`compute_pq` の正体

`compute_pq`（試行間の時間平均 hidden state コサイン類似度）は、標準的な P(q) 構成に近い構造を持つ：

$$q^{\alpha\beta} = \cos\!\left(\bar{h}^{(\alpha)}, \bar{h}^{(\beta)}\right)$$

これは SG 理論の replica overlap $q^{\alpha\beta} = \frac{1}{N}\sum_i \langle \sigma_i \rangle^\alpha \langle \sigma_i \rangle^\beta$ と
構造的に対応している（等方化後）。

つまり **`compute_pq` が P(q) であり、`compute_qea` は別の量（時間自己相関の代理）**。
現行コードでのラベルの使われ方が逆転している可能性がある。

---

## 決定済み事項（2026-05-21 壁打ち）

| 問い | 決定内容 |
|---|---|
| Q1: レプリカ定義 | 同一プロンプト・同一 N・同一 T・異なる乱数シードの試行 ✅ |
| Q2: 判定基準 | P(q) moments ベースへの全面再設計（A案）✅ |
| Q3: stagnation 帰属 | **未定**（SPEC-2026-05-21-001 の診断結果で決定） |
| Q4: 等方化 | centering + whitening を入れる方向で確定。診断スクリプトは raw で先行実施 ✅ |

---

## 次のステップ

```
Step 1（現在）: SPEC-2026-05-21-001 を実装・実行
  → stagnation_after_move の P(q) 分布を move_loop / no_move と比較
  → Q3 の帰属を決定

Step 2: SPEC-2026-05-21-002（P(q) ベース相分類の再設計仕様書）
  → 等方化（centering + whitening）の実装
  → P(q) moments（mean, Δq, Binder cumulant）による判定基準の設計
  → stagnation 帰属の確定後に実装

Step 3: 再設計後の相図の検証
  → 7B・14B の既存データで新旧相図を比較
  → 閾値感度解析（M2 対処）
  → モデリング案（Landau / REM）への接続
```

---

## 関連ファイル

| ファイル | 内容 |
|---|---|
| `analysis/analyze_integrated.py:173–194` | 現行 `classify_phase` の本体 |
| `analysis/analyze_integrated.py:140–157` | `compute_pq` と `compute_qea`（ラベル逆転問題） |
| `analysis/analyze_pq.py:224–236` | 別実装の `classify_phase`（PM 閾値 0.6）|
| `analysis/analyze_phase_diagram.py:30` | `BOUNDARY_THRESHOLD = 0.5`（別の Tc 定義） |
| `analysis/analyze_integrated.py:302` | `_find_tc threshold = 0.15`（さらに別の Tc 定義） |
| `research_state/hypotheses.md` | PM ラベル定義（stagnation/think_budget 含む）|
| `open_questions.md` U2 | SG 相の判定基準（本レポートと直結） |
| `specs/draft/SPEC-2026-05-21-001.md` | 診断スクリプト仕様書 |
| `docs/Modeling_idea.md` | Landau / REM フィット案（本問題解消後に着手） |
