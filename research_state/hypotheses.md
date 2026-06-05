# 仮説（Hypotheses）

研究の作業仮説と本命仮説、および「仮説本体ではなく整理手段」として採用しているものを区別して記録する。

最終ゴール（制御モデル構築）と全体方針は `CLAUDE.md` を参照。

---

## 大方針仮説（曲げない）

スピングラス理論・Hopfield 模型・散逸構造・非平衡統計物理・レプリカ対称性の破れ (RSB) の枠組みで LLM の推論挙動はモデリング可能である。

この大方針は実験データの揺らぎや個別仮説の不成立では曲げない。各論の仮説（H3, H4 等）が反証されてもこの枠組みの中で代替仮説を立てる。

- **status**: fixed（変更しない）
- **evidence**: 枠組みの採択自体が研究の前提
- **changed**: 2026-05-22 初記録

---

## 本命仮説

### H5：SG 相は非平衡 SG 理論で記述される（平衡統計力学では不十分）

3状態ボルツマン競合モデル $p_i \propto g_i e^{-E_i/T}$ の**直線性検定**（$\ln(p_i/p_{PM})$ vs $1/T$）が全モデル・全 $N$ で非成立。これは系が平衡熱浴に接した ergodic 分布に従っていないことを示す。平衡統計力学ではなく**非平衡 SG 理論**（駆動散逸系・aging・off-equilibrium dynamics）のフレームが適切であることを示唆する。

副観察：$T_{c2}$（SG→PM 境界）が deepseek 系で $N$ にほぼ非依存（$T_{c2} \approx 1.0$〜$1.2$）。これは SG 相の消滅が問題サイズ $N$ ではなく温度ノイズだけで駆動される内部転移であることを示唆し、非平衡 SG の固定点描像と整合する。

**棲み分け（2026-06-06 確定）**：H5 の SG/非平衡 SG 枠組みは **DeepSeek 系に適用**。Qwen 系の高温挙動は H7'（asymmetric melting + 2アトラクター双安定）で別途記述。両者は大方針（SG/Hopfield/散逸構造/RSB の OR 枠組み）の異なる側面。

- **status**: active（physics-agent 確認待ち。**Tc2 証拠は DeepSeek で回復済み**、2026-06-05）
- **evidence**: EXP-002 — 直線性不成立（ゴール到達 vs 非到達の二値評価でペグ交絡の影響限定的）。副観察「$T_{c2}$ の N 非依存性」は EXP-008（2026-06-05）で**対称化分類により再フィット → DeepSeek で確認**（高温 recitation なし p_O(T≥1.8)=0.00、$T_{c2}\approx 1.0$–1.2 が N3-5 で N 非依存）。**Qwen は recitation-order により非単調化し保留**（D-3 後に再定義）。再解析：`research_state/tc2_refit_symmetric.md`, `research_state/symmetric_accuracy.json`
- **changed**: 2026-05-25 新規追加 / 2026-06-05 交絡対処後 DeepSeek で Tc2 N 非依存性を再確認、Qwen は保留
- **exp_refs**: EXP-002, EXP-008

### H6：モデル固有の相図差異（モデルアーキテクチャが相図に反映される）

モデル系列によって相図が質的に異なる。現状の観察：

**llama-8b**（補足扱い）：
- $T \to 0$ でも $p_\text{goal} < 0.2$（Ordered 相がほぼ存在しない）
- $T_{c2}$（N=3 で 0.124）が deepseek 系より大幅に低い
- 「秩序相の basin が浅い」= thinking 能力の構造的欠如が相図に現れている

**qwen3-8b**（EXP-004, 2026-05-26）：
- N=3 で T=0.1〜1.0 の全域 acc=52〜80%（deepseek-7b の T=1.0 acc=12% に対し 52%）
- N=2 は T=1.0 で 25/25 完璧（thinking が T 耐性を与えている可能性）
- N=4 で acc=0 かつ no_move_catchall=72%（低温でも即 PM）
- **N=3 → N=4 の容量崖がシャープ**：SG 的失敗モードをほぼ経由せず PM に直崩壊
- Qwen3-8B の崩壊様式は DeepSeek 系と異なる（DeepSeek は N=4 でも SG 経由で少し acc がある）

**解釈仮説（検証中）**：
- thinking モデル（DeepSeek-R1-Distill, Qwen3）は thinking なしモデル（llama-8b）より $T_c$ が高い
- Qwen3 系は「解けるか / 即崩壊か」がバイナリ → Hopfield 容量超過点が sharp
- DeepSeek 系は崩壊時に SG 相を経由 → 容量超過後も局所安定状態に落ちる

**位置づけ**：4モデル軸（DeepSeek 7B/14B + Qwen3 8B/14B）での比較が主眼。llama-8b は「Ordered 相を持たないモデルの例」として補足資料に。

**高温崩壊様式の質的差異（EXP-008 + D-3, 2026-06-05、physics-agent 審査済み）**：
- **Qwen（8B/14B）は中〜高温で推論を放棄し暗記正準解を復唱する**（recitation-order = 記憶想起チャネル）。判別子は tokens_per_move<15（move 列は一意ゆえ区別不能、計算量で分離）。相構造：reasoning-order（低温・融解）→ recitation-order（中高温 T1.3-2.0、ピーク T≈2.0）→ 全面 PM（T≳2.5）。熱駆動の「窓」（「athermal」ではない）。
- **DeepSeek（7B/14B）は recitation せず真正崩壊**（recitation 総数 7b=0, 14b≈16）。
- 機構の作業仮説：エントロピー/エネルギー競合（高温で reasoning の自由エネルギーが記憶想起を上回る）。詳細・条件は `research_state/subclass_d3.md`。→ **H7 で inverse melting として定式化（2026-06-05）**。
- **Qwen の $T_{c2}$ は降ろす**：N≥4 は「ordered 相不在」ではなく「SG↔PM 境界が不明瞭」。$T_{c2}$ N 非依存性は DeepSeek の性質（H5）。
- **訓練方式差の機構仮説（2026-06-05）**：arXiv:2601.11061（Spurious Rewards Paradox）が RLVR 訓練は中間層（L18-L20）に Anchor-Adapter 回路を作り、reasoning 経路を迂回して暗記モードへ切替えるトリガーを持つと示す。Qwen3（RL-based thinking）はこの回路を持ち高温 recitation する。DeepSeek-R1-Distill（SFT/蒸留）はこの回路を持たず真正崩壊する、という差の機構仮説。
- **L2 定量確認（2026-06-05）**：per-trial replica pair $q_{ab}$ で recitation 群の $q_{EA} \approx 0.9$（スパイク状）を確認。DeepSeek は全温度域で $q_{EA} \approx 0.02$（2桁差）。recitation basin の鋭さは Qwen に固有。

- **status**: active（physics-agent 確認待ち）
- **evidence**: EXP-002（llama-8b）、EXP-004（qwen3-8b）、EXP-008（高温 recitation のモデル差、対称化分類）、L2 解析（2026-06-05、`figures/l2_order_param/`）、arXiv:2601.11061（訓練方式差）
- **changed**: 2026-05-26 EXP-004 追記 / 2026-06-05 EXP-008 追記 + 訓練方式差機構 + L2 $q_{EA}$ 定量
- **exp_refs**: EXP-002, EXP-003, EXP-004, EXP-008

### H3：move loop ↔ ポテンシャル上の局所安定状態

LLM 推論中に観測される **move loop**（手の繰り返し）は、構築されるポテンシャル $V(h)$ 上の **局所安定状態 (local minimum / metastable basin)** として記述される。

**位置づけ**：これは「実推論中に粒子が穴に閉じ込められている」という現象論的主張ではなく、**モデリング上そう記述する**という構成的仮説。Hopfield エネルギー、SG 理論ともに局所安定状態の概念があり、両者と整合する。

**L2 再解釈（2026-06-05/06、physics-agent 審査済み）**：

per-trial replica pair $q_{ab}$（centering あり）では move_loop の $q_\text{EA}\approx0$（SG の固定点署名なし）。per-move 時間方向 overlap のオフダイアゴナルが**全て負**（連続ステップが反相関）。

この「全負」は SG 的固定点（連続ステップが正相関であるべき）と矛盾し、**非保存力（カール成分）を含む非勾配ダイナミクス**を示唆する。Helmholtz 分解 $F(h) = -\nabla V(h) + A(h)$ における $A(h)$ 成分（回転場）が循環を引き起こしている描像。

**現在の解釈（physics-agent 条件付き合格 2026-06-06）**：

move_loop は **非勾配的循環（NESS 確率カレント $J_{ss} \neq 0$ 候補）** として記述する。「周期-2 リミットサイクル」は over-claim（全負は周期-2 以外でも出る）のため保留。$J_{ss} \neq 0$ の実測（縮約空間での確率カレント推定）が判定条件。

- **status**: **active**（SG 解釈から非勾配循環へ再定義。$J_{ss}$ 実測で確定予定）
- **evidence**: EXP-001 — 旧 P(q) 双峰性（trial-mean 計算、再評価必要）。L2 解析（2026-06-05）— $q_\text{EA}\approx0$・per-move 反相関 → 非勾配循環示唆。
- **changed**: 2026-05-22 active→supported / 2026-06-05 active（SG 疑義）/ **2026-06-06 非勾配循環（NESS）へ再定義（physics-agent 審査）**
- **exp_refs**: EXP-001、L2 解析（`figures/l2_order_param/`）

### H4：制御可能性（段階的）

外力 or 外場の挿入により、SG 相に落ちた状態を秩序相へ戻せる。

達成は段階的：

1. **モデリング側**：ポテンシャル上の粒子シミュレーションで、外力挿入により秩序相領域が広がることを示す
2. **対応付け**：そのシミュレーション上の制御外力に対応する**推論時の駆動**（プロンプト介入／hidden state 介入／サンプリング介入のいずれか）を設計する
3. **実装**：上記を実 LLM 推論に適用し制御モデルを完成させる

H4 が成立しないと最終ゴール（制御モデル）に到達しないため、研究全体の load-bearing な仮説。

**間接的支持証拠（2026-06-05）**：arXiv:2503.23084（Hong et al.）が、残差ストリームの**単一線形方向**（中間層 = layer_mid が最顕著）で reasoning↔memorization を分離し、**介入で因果的に切替可能**と示した。本研究の「layer_mid の $q_{EA}$ で記憶 basin が顕在化する」描像と層位置まで一致。段階 2（hidden state 介入）の有力な実装候補。

**H_eff の形式（physics-agent 確定 2026-06-06）**：

平衡ハミルトニアン H ではなく、**非勾配 Langevin** が適切：

$$
\dot{h} = -\nabla V(h) + A(h) + \sqrt{2T}\,\xi(t)
$$

- $-\nabla V(h)$：多井戸ポテンシャル。reasoning 井戸（広く浅い、高エントロピー）+ recitation 井戸（狭く深い、Ω=1）
- $A(h)$：非勾配・回転成分。move_loop の非勾配循環（NESS 確率カレント）を生む
- $\sqrt{2T}\,\xi$：熱ノイズ。高温で reasoning 融解（H7'）と振動抑制（Oscillatory→PM）を駆動

**H4 制御の再解釈**：介入案 (i)「勾配の逆向き外力」は、この枠組みでは $A(h)$ を打ち消して reasoning basin へ流す制御外力 $-A(h)$ と解釈できる。move_loop が非勾配循環なら制御は「カール成分の除去」になり物理的に clean。

- **status**: active（未検証。H3 再評価中。ただし 2503.23084 が layer_mid 介入の feasibility を示す）
- **evidence**: 間接：arXiv:2503.23084（layer_mid 単一方向介入で reasoning↔memory 切替）；H_eff 形式は physics-agent 審査（2026-06-06）
- **changed**: 2026-05-22 初記録 / 2026-06-05 2503.23084 追記 / **2026-06-06 H_eff 非勾配 Langevin 形式を追記**
- **exp_refs**: （未割当）

### H7'：Qwen の高温 recitation は asymmetric melting（reasoning の entropic 融解）

**旧 H7（inverse melting / Schupper-Shnerb）は不合格**。Ω≈1（単一 basin）の実測により Schupper-Shnerb の核心要件（Ω>>1）が崩壊したため撤回（physics-agent 再審査 2026-06-06）。

**新定式化（H7'）**：

Qwen3 の中〜高温 recitation は **reasoning 側の entropic 融解 + Ω=1 の recitation basin の相対露出**（asymmetric melting）。

$$
\Delta F(T) = (E_r - E_m) - T(S_\text{reason} - S_\text{recit})
$$

- **$S_\text{reason} > S_\text{recit}$**：reasoning は多様な探索軌道（高エントロピー）、recitation は Ω=1 の決定論的単一軌道（$S_\text{recit}\approx0$）
- **高温**で reasoning の自由エネルギーが $T \cdot S_\text{reason}$ 分だけ不利化 → **reasoning が先に融解する**
- → 相対的に narrow-deep の recitation basin が露出（recitation が「安定化する」のではなく、reasoning が「先に壊れる」）
- **極限高温（T≳2.5）**：recitation basin 自体も noise で不安定化 → 全面 PM

一次転移性（physics-agent 審査 2026-06-06）：tpm 双峰性（gap あり）= **2アトラクター双安定 + Kramers 的選択確率のシフト**。平衡一次転移ではなく非平衡動力学的ビスタビリティ。

**DeepSeek で起きない理由**：$J_\text{mem}^{\text{Qwen}}>0$（RLVR 訓練の Anchor-Adapter 回路）、$J_\text{mem}^{\text{DeepSeek}}\approx0$（SFT/蒸留）。Qwen は recitation basin を形成する有効結合を持つ。

**N=6 消失**：経路長 $L=2^N-1$ に対し復唱成功確率 $\sim(1-\epsilon)^L$ が指数減衰。$L=63$ で窓が消滅。

**未確認条件**：$E_r > E_m$（reasoning の探索コスト > recitation 起動コスト at high T）は仮定。軌道エントロピー $S_\text{reason}$ と basin depth $E$ の実測が次の検証課題。

- **status**: active（physics-agent 条件付き合格 2026-06-06。$S$/$E$ 符号の実測と他パズルでの普遍性確認が残条件）
- **evidence**: Ω=1 確定（basin count クラスタリング）、tpm 双峰性（ヒステリシス実験 2026-06-06）、raw $q_\text{EA}\approx0.97$–$1.0$（T 非依存定数）、$J_\text{mem}$ オン/オフ（arXiv:2601.11061）
- **changed**: 2026-06-05 H7 新規 / **2026-06-06 H7' に全面改訂（asymmetric melting、Schupper-Shnerb 撤回）**
- **refs**: arXiv:2601.11061（RLVR Anchor-Adapter）; Schupper-Shnerb は撤回

---

## 外力候補

| 記号 | 内容 | 対応物理量 |
|---|---|---|
| (a) | few-shot 例示数 $n_\text{shot}$ | 外部磁場 $h$（秩序相を安定化） |
| (b) | 推論の一手に対応する**粒子の駆動力** | 解状態へ向かう非平衡駆動 |

(a) は `CLAUDE.md` の物理変数対応表に既出。(b) は本研究で新たに導入する外力概念で、推論を「答えに向かう状態遷移」として捉えた際の自然な対応物。

---

## 介入案（H4 段階 2 の候補）

| 案 | 内容 | 採否 |
|---|---|---|
| (i) | 局所安定状態に落ちた粒子に**勾配の逆向き**に外力をかける | **本命**。物理的にも介入として自然 |
| (ii) | move loop 検出時に**ポテンシャルそのものを動的変形** | **保留気味**。理由：観測量（モデリング）の変形と実推論への反映の間にギャップが大きい |

---

## 作業枠組み（仮説本体ではなく整理手段）

以下は「仮説」ではなく**可視化と整理のための暫定枠組み**として採用している。検証対象ではなくモデリングの素材。

### $(T, N)$ 平面の 3 相構造

| 相 | 早期終了ラベルとの暫定対応 |
|---|---|
| Ordered（秩序相） | `goal_reached` |
| SG（スピングラス相） | `move_loop_repeat`, `move_loop_reverse` |
| PM（常磁性相） | `no_move_catchall`, `move_ceiling`, `stagnation_after_move`, `think_budget` |

**改訂（2026-06-06、physics-agent 審査確定）**：「SG 相 = move_loop」は撤回。3相構造から **4動力学レジーム**へ更新：

| レジーム | 主な終了様式 | hidden state 特性 | モデル |
|---|---|---|---|
| Reasoning-ordered | goal_reached（推論型） | 固定点アトラクター | 両モデル |
| Recitation-ordered | goal_reached（復唱型） | 固定点アトラクター（Ω=1、狭深） | Qwen のみ |
| Oscillatory | move_loop_repeat/reverse | 非勾配循環（NESS 候補） | 両モデル（T=1.1–1.5） |
| PM | no_move_catchall / stagnation | 拡散的、構造なし | 両モデル（高温） |

これらは**熱力学的な相ではなく動力学レジーム**（双安定・確率選択・ノイズ誘起遷移を含む非平衡描像）。相図（領域分割）ではなく動力学ベクトル場 $\dot{h} = -\nabla V + A + \text{noise}$ の文脈で記述する。

### シグモイドフィットによる $T_{c1}(N)$, $T_{c2}(N)$ の実測値（EXP-002）

経験的シグモイドフィット（$p_O \sim \sigma(-k(T-T_{c1}))$、$p_{PM} \sim \sigma(+k(T-T_{c2}))$）で抽出した転移温度。p_other < 0.35 のセルのみ使用。

**$T_{c1}$（Ordered→SG）**：

| N | deepseek-7b | deepseek-14b | llama-8b |
|---|---|---|---|
| 2 | 1.195±0.127 | 1.028±0.002 | 1.083±0.050 |
| 3 | 0.417±0.055 | 0.127±0.074 | ~0（fit failed） |
| 4+ | ~0 または fit failed | ~0 または fit failed | fit failed |

→ $N$ 増加で急激に 0 へ収束（N≥4 では測定範囲に Ordered 相が存在しない）

**$T_{c2}$（SG→PM）**：

| N | deepseek-7b | deepseek-14b | llama-8b |
|---|---|---|---|
| 2 | 1.147±0.047 | 1.028±0.002 | 1.157±0.050 |
| 3 | 1.129±0.024 | 1.176±0.067 | 0.124±0.185 |
| 4 | 1.015±0.017 | 1.132±0.134 | ~0 |
| 5 | 1.037±0.077 | — | — |
| 6 | 0.977±0.531 | 1.503±0.275 | — |

→ deepseek 系は $N$ にほぼ非依存（$T_{c2} \approx 1.0$〜$1.2$）。llama-8b は大幅に低い（→ H6）

### スケーリング則 $T_c(N) = A \cdot N^{-\alpha}$

相境界温度の $N$ 依存性を冪則でフィットすることを試みる。指数 $\alpha$ のモデル普遍性は当初仮説に含めていたが、現状は棚上げ（下記）。
ただし上記 $T_{c1}(N)$ の急落は冪則に乗る可能性があり、Qwen3 系のデータが揃い次第再検討する。

---

## 棚上げ（仮説から外したもの）

### 臨界指数 $\alpha$ の抽出によるモデル普遍性の検証

**理由**：現状の試行数では臨界指数を統計的に有意に抽出できない。

**扱い**：仮説本体からは外す。データが大幅に増えた段階で復活を検討する。

- **status**: dormant（棚上げ中）
- **evidence**: 試行数不足で有意な抽出不可
- **changed**: 2026-05-22 active → dormant（棚上げ）
