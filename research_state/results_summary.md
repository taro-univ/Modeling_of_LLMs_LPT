# Results Summary

実験で「**確実に見えた**」と判断している観測事実と、既存データの要約。

詳細な数値・図表は `docs/Modeling_idea.md`、`results/hanoi/full_sweep/`、`results/hanoi/collapse_phase/` を参照。

最終更新：2026-06-06。**Lights Out を保留**（7B が N=3 を予算内で解けず秩序相が立たない、観測 9）。SPEC-2026-06-06-003 で「手」処理を env 委譲化（Hanoi 専用前提の漏れを修正、汎用インフラとして保持）。前回（2026-06-05）：L2 秩序変数の再定式化（Track B 完了）、**recitation basin は Ω=1 の単一決定論的 attractor**、$p_\text{recit}(T)$ が真の秩序変数、H7→H7'（asymmetric melting）。

---

## ⚠️ 重大な方法論訂正：ゴールペグ・パリティ交絡（2026-06-05）

**発見**：env のゴールが peg C 固定だったため、モデルが暗記した正準ハノイ解を「Move 1 from A to C」から復唱する高温域で、**偶数 N は完全最適解が peg B に積み上がり accuracy=0 と誤判定**されていた（奇数 N は C に乗り正解）。これにより偶数 N の「崩壊相」が人工的に水増しされていた。

**決定（user, 2026-06-05）**：peg B/C は $S_3$ ペグ置換対称性で gauge 等価（physics-agent 審査・ラチファイ済み、Hanoi graph 自己同型群 = $S_3$, Park arXiv:0809.1179）。以下を採用：
1. **秩序変数を対称化**：$m = \mathbb{1}[\exists t:\ x(t) \in \{\text{full-B},\ \text{full-C}\}]$（A 以外の単一ペグに N 枚 size-ordered, first-passage）
2. **ポテンシャル対称化**：$V(x) = \lambda_d \cdot \min(D_{\to B}, D_{\to C})/(2^N-1) + \lambda_p \cdot \text{illegal}$（二重井戸、鞍点 = 初期状態のみ）
3. **暗記復唱（reasoning_tokens=0）も秩序相に含める**（基底状態到達のため）

**補正後の全データ再計算**（`research_state/symmetric_accuracy.json`、保存済み move_texts から再計算・再 sweep 不要）：
- 延べ +257 試行が正解に転化。交絡規模はモデル依存（qwen3-14b 最大：full_sweep +61, collapse +77）
- **新しい物理的特徴**：偶数 N の高温域で acc が温度とともに**増加**する「**recitation-ordered 領域**」が出現（qwen3-8b N4 collapse は T1.1→3.0 で 0→最大10、qwen3-14b N4 は T1.5 で 20/25）。低温＝推論失敗、高温＝暗記復唱成功という従来不可視だった構造
- N6 は perfect-B=0 で**真正崩壊**（63手は誦じきれない）。汚染は偶数 N の中〜高温に集中

**残作業（D-1〜D-4）**：env コードの対称化（Codex 委譲・仕様書化）、相図再生成、recitation/reasoning order の sub-classify、L2 での full-B/full-C 縮退ペア検証。

---

## 主要観測事実

### 観測 1：複雑度 $N$ 駆動の秩序崩壊（**最重要**）

- $N$ が小さい範囲ではローカル LLM でも一定精度で正解可能
- $N$ を上げるにつれて **move loop** や **no-move** が増加し正解率が低下
- これは $N$ をパラメータとした**相転移として記述できる**可能性がある

### 観測 2：温度 $T$ 駆動の遷移

- $T \approx 1.0$ を超えると **move loop が顕著**に出現
- より高温では **PM 様状態**（手をほとんど出さない）が支配的
- 低温→中温→高温で Ordered → SG → PM の遷移シーケンスが見える

### 観測 3：ボルツマン平衡の不成立（EXP-002, 2026-05-25）

$\ln(p_i/p_{PM})$ vs $1/T$ の直線性検定を deepseek-7b/14b/llama-8b の全モデル・全 $N$ で実施。**有意な直線性はほぼ確認できなかった**（deepseek-14b N=3 O/PM の r=0.559 が唯一有意）。平衡ボルツマン記述が成立しないことは非平衡 SG 理論フレームを支持する（→ H5）。

### 観測 4：$T_{c2}$ の N 非依存性（EXP-002, 2026-05-25 / 再確認 EXP-008, 2026-06-05）

> ✅ **DeepSeek について再確認・復帰（2026-06-05, EXP-008）**：対称化分類で $T_{c2}$ を再フィットした結果、DeepSeek は高温で暗記復唱しない（p_O(T≥1.8)=0.00）ためパリティ交絡の影響をほぼ受けておらず、**N 非依存性（$T_{c2}\approx 1.0$–1.2, N3-5）はそのまま確認**された（deepseek-7b: 1.13/1.10/1.05、deepseek-14b: 1.24/1.13）。詳細：`research_state/tc2_refit_symmetric.md`。
> ⚠️ **Qwen は保留**：Qwen は高温で recitation-order に転じ p_PM が非単調になるため、単純3相シグモイドで $T_{c2}$ を定義できない。recitation/reasoning の sub-classify（D-3）後に再定義が必要。

シグモイドフィットによる SG→PM 転移温度 $T_{c2}$（旧値、deepseek/llama、EXP-002）：

- **deepseek-7b**：N=2〜6 で $T_{c2} \approx 1.0$〜$1.15$（ほぼ N 非依存）
- **deepseek-14b**：N=2〜4 で $T_{c2} \approx 1.0$〜$1.2$（誤差大）
- **llama-8b**：N=3 で $T_{c2}=0.124$（deepseek 系と質的に異なる → H6、補足扱い）

$T_{c1}$（Ordered→SG）は N 増加とともに急落し、N≥4 では測定範囲内に Ordered 相が存在しない。

### 観測 5：モデル間の相図の質的差異（EXP-002/EXP-003, 2026-05-25/26）

> ⚠️ **一部降格（2026-06-05）**：偶数 N（特に N=4）の崩壊判定はパリティ交絡を含む。低温 T=0.1 の数値は影響小だが、「N=4 即崩壊」「容量崖」の主張は対称化 accuracy で再確認が必要（recitation-ordered 領域の存在を反映していない）。

| モデル | N=2 T=0.1 | N=3 T=0.1 | N=4 T=0.1 | 特徴 |
|---|---|---|---|---|
| deepseek-7b | 23/25 | 16/25 | 2/25 | N=4 に薄い秩序あり |
| deepseek-14b | 25/25 | 12/25 | 8/25 | N=4 で明確な秩序 |
| **qwen3-8b** | **23/25** | **16/25** | **0/25** | N=3 が全 T で robust、N=4 で即崩壊 |
| llama-8b | 21/25 | 4/25 | 0/25 | N=3 で既に薄い。補足扱い |

**Qwen3-8B の特異性（EXP-004, 2026-05-26）**：
- N=3 で T=0.1〜1.0 の全域にわたり acc=52〜80%（deepseek-7b は T=1.0 で 12%）
- N=2 は T=1.0 で 25/25 完璧（goal_reached のみ）
- N=4 は T=0.1 で acc=0、no_move_catchall が 72%（即 PM 崩壊）
- **N=3 → N=4 の容量崖がきわめてシャープ**

### 観測 6：llama-8B 崩壊相の内部構造（EXP-003, 2026-05-26）

collapse_phase sweep（T=1.1〜3.0）の解析：
- **N=6 T=1.1** が全 (N,T) セル中で最も SG 的：pm%=23%、qbar_inter=0.51（最大）
- **$T_{\mathrm{SG\to PM}}(N=6) \approx 1.16$**（collapse_phase 範囲内で唯一遷移を捕捉）
- N=3〜5 は T=1.1 時点で既に PM 支配（遷移は T<1.1 で起きている）
- 大きい N ほど SG 的ふるまいが高温まで持続する傾向を確認

### 観測 7：Qwen3-8B の崩壊相内部構造（EXP-005、解析 2026-06-05）

collapse_phase sweep（N=3–6, T=1.1–3.0）の run_pipeline.py 解析：
- **N=3** は T=1.5 まで acc≥0.5 を維持（ordered 判定）。$T_\text{SG→PM}(N=3)\approx1.95$
- **N=4–5**：collapse_phase 全域で paramagnetic（no_move 支配）。全面 PM 崩壊
- **N=6**：T=1.2–2.0 で move_loop_repeat 支配（SG 的）。$T_\text{SG→PM}(N=6)\approx1.86$
- Qwen3-8B は N=3 が robust で N=4 以上は即 PM という容量崖が collapse phase でも確認
- 図：`figures/collapse_phase/qwen3-8b/`

### 観測 8：L2 秩序変数の再定式化（Track B、2026-06-05）

per-trial replica pair $q_{ab}$ の正しい計算と、raw cosine（centering なし）を用いた解析：

**recitation basin の構造（Qwen3-14B）**：
- **Ω ≈ 1**（単一 basin）：全 T（T=1.3–2.0）にわたり hierarchical clustering で cluster 数 = 1
- **raw $q_{EA}$ ≈ 0.97–1.0**（T によらず一定）：basin の鋭さは温度非依存の定数
- **$p_\text{recit}(T)$ が真の秩序変数**：basin アクセス確率が T 依存、basin 自体は固定
- $\hat\xi^1$ 投影：recitation も reasoning も $m\approx0.98$（両方ゴール到達）。ξ^1 方向は両チャネルに共通。recitation 固有パターンは ξ^1 直交補空間に存在

**H3（move_loop = SG）の L2 反証**：
- per-trial pair $q_{ab}$（centering 後）：reasoning≈+0.25、recitation≈+0.9–1.0（raw）、move_loop≈0、PM≈−0.2
- per-move 時間方向 overlap：move_loop のオフダイアゴナルが全て負（同一 basin への再訪なし）
- → move_loop はエルゴーディックな遍歴（PM 的）を支持。SG 相の積極的証拠なし

**H7（inverse melting）への含意**：
- Ω=1 は Schupper-Shnerb の写像（Ω>>1 が必要）と矛盾
- H7 は再定式化が必要：「多重縮退による TS 安定化」→「単一決定論的 attractor の kinetic dominance」
- 詳細は `research_state/hypotheses.md` H7 を参照。ヒステリシス実験（一次転移性検証）実施中

**DeepSeek-7B との比較**：
- 全温度域で $q_{EA}\approx0.02$（スケール2桁差）、recitation basin 不在を確認

### 観測 9：Lights Out は 7B では秩序相が立たない → 保留（EXP-009, 2026-06-06）

Lights Out（GF(2) 一意解パズル）の DeepSeek-7B 検証で **計16 trial 全 accuracy=0**。原因は3層：

1. **測定漏れ（修正済み）**：early-stop の手数カウントが Hanoi 専用 `_MOVE_RE` で `Toggle (r,c)` を拾えず `no_move_catchall` 誤爆 → 推論途中で強制打ち切り。SPEC-2026-06-06-003 で env 委譲化して修正（commit 45c4db0、pytest 50 passed、physics PASS、Hanoi 回帰ゼロ）。L2 キャプチャも `__fallback__` から実 Toggle 位置取得に回復。
2. **予算切れ**：`num_predict=4096`（8192/10000 も）で 7B が GF(2) 9元系を立式→ガウス消去途中で切断、`</think>` を閉じきれない。
3. **能力不足**：閉じた 1 trial も誤答（64手, v=0.667）。GF(2) 手計算が 7B には不安定。
4. **未修正の採点バグ**：`extract_moves_from_text` が本文全体（思考中の試行錯誤 Toggle 含む）を採点 → `</think>` 以降の解答のみ採点すべき。Lights Out で顕在化、Hanoi では軽微。

**決定（user, 2026-06-06）**：Lights Out 保留・再考。SPEC-003 の env 委譲修正は N-puzzle/Frog Jump 用の汎用インフラとして保持。SPEC-2026-06-06-004（Algorithm C の OOP化）は draft で park。再考の選択肢：N-puzzle（SPEC-001）/ Frog Jump（SPEC-002）優先、または Lights Out を 14B で再評価。詳細：memory `finding_lights_out_held.md`。

---

## 暫定転移温度（$N=3$, deepseek-r1-distill-qwen-7B）

`docs/Modeling_idea.md` より：

| 転移 | 温度 |
|---|---|
| Ordered → SG | $T_{c1}(N=3) \approx 1.0$ |
| SG → PM | $T_{c2}(N=3) \approx 1.15$ |

---

## 既存モデリング案

`docs/Modeling_idea.md` に以下 3 案が記録済み（フィッティング未実施）：

1. **3 状態ボルツマン競合モデル** — すぐにフィット可能、$T_{c1}, T_{c2}$ の定量化に直結（**最優先**）
2. **2 秩序変数 Landau 理論** — $m = p_\text{goal}$, $q = p_\text{loop}$ を独立秩序変数として導入
3. **ランダムエネルギー模型 (REM)** — $T_c \propto K(N)^{-1/2}$ のスケーリング。$N$ 系列データが揃ってから検証

---

## データ蓄積状況

| モデル | 役割 | full_sweep | collapse_phase | hidden state npz |
|---|---|---|---|---|
| deepseek-r1-distill-qwen-7B | **主軸** | ✅ 50/50 完了 | ✅ 36/36（N3_T1_0 は低優先） | 取得済み |
| deepseek-r1-distill-qwen-14B | **主軸** | ⚠️ 47/48（N6_T0_8 クラッシュ） | ✅ 36/36 完了 | 取得済み |
| qwen3-8b | **主軸** | ✅ 50/50 完了 | ✅ 36/36 完了（EXP-005） | 取得済み |
| qwen3-14b | **主軸** | ✅ 51/52（N6_T0_6 欠損, EXP-006） | ✅ 36/36 完了（EXP-007, 2026-06-05） | 取得済み |
| llama-8b | **補足** | ✅ 完了（N≥4 は acc=0） | ✅ N3-5 完了・N6 T1.8 進行中 | 取得済み |

> **4モデル軸の Hanoi データが全て揃った（2026-06-05）**。秩序変数は B/C 対称化版に確定（EXP-008）。秩序相は reasoning-order / recitation-order にサブ分類（D-3）。14B 比較相図：`figures/phase_diagram_symmetric/compare_14b_subclass.png`（DeepSeek=真正崩壊、Qwen3=高温 recitation）。

### missing セルの詳細

| セル | 状態 | 対処 |
|---|---|---|
| 14B / full_sweep / N6_T0_8 | meta.json + npz 17本あり（クラッシュ） | 優先度中。Qwen3 完了後に再実行 |
| 7B / collapse_phase / N3_T1_0 | meta.json のみ | 優先度低（T=1.0 は full_sweep で代替可） |

---

## モデル戦略（2026-05-26 確定）

**4 モデル軸**：DeepSeek-7B / DeepSeek-14B / Qwen3-8B / Qwen3-14B

- **採用理由**：2ファミリー × 2サイズの 2×2 設計。$T_c(N, M)$ スケーリングと cross-family 比較が同時に可能
- **llama-8B の扱い**：N≥3 での Ordered 相がほぼ存在せず、スケーリング則フィッティングに使えない。補足資料（「Ordered 相を持たないモデルの例」）として残す
- **追加モデルは不要**：パズル軸（Lights Out 等）の方が普遍性主張に対する科学的価値が高い

---

## 未実施で重要なもの

- **Qwen3-8B collapse_phase 解析**（実行完了後に `run_pipeline.py`）
- **Qwen3-14B 全 sweep**（8B collapse_phase 完了後に開始）
- **14B / N6_T0_8 の補完**
- ~~**Lights Out × DeepSeek-7B の sweep**~~ → **保留**（観測 9、7B 解けず・EXP-009）
- **4 モデル × Hanoi の P(q) 横断解析**（npz は 7B/14B/llama-8B で揃っている）
- **3 モデリング案のフィッティング**（データが揃い次第）
