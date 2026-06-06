# D-3: 秩序相のサブ分類（recitation-order vs reasoning-order）— 2026-06-05

ゴールペグ・パリティ交絡対処（EXP-008）の後続。対称化で秩序相に算入された試行群を、推論駆動（reasoning-order）と暗記想起（recitation-order）に分離する。physics-agent 審査済み（2026-06-05、条件付き合格＋下記の論理的修正1点）。

## 判別子

- **`reasoning_tokens` は使えない**（正しく populate されず。qwen3-14b で全2075試行中63しか非ゼロ）。
- **`move` 列構造（正準解との一致）も使えない**：ハノイの最適解は一意なので、推論で正解した試行も暗記復唱した試行も**同一の最適 move 列**を出力する（deepseek-7b は復唱しないのに move==canonical が 330/354）。出力では両者を区別不能。
- **採用：tokens_per_move = total_tokens / num_moves**。recitation/reasoning の差は出力（手）ではなく**計算量（思考トークン）**にあるため、これが原理的に正しい唯一の判別子。Qwen で強い二峰性（8-12 tok/move に recitation 集中、48+ に reasoning、12-48 は疎）。閾値 **tpm < 15**。
- 検証：tpm<15 群は qwen3-14b で 100%（197/197）が正準最適解。
- **tpm は recitation 同定にのみ使用し、相判定の軸には昇格させない**（physics-agent 条件2の趣旨を遵守）。SG/PM 判定は early_stop 構造に置く。

## recitation の相構造（physics-agent 条件1：「athermal」撤回）

recitation は **熱駆動**（T≤0.8 でゼロ、温度とともに連続増加）。「athermal」は撤回。正しくは「**reasoning channel が熱的に壊れる中〜高温域で開く第二アトラクタ群（記憶想起チャネル）**」。

qwen3-14b の温度依存（ORDERED = recit+reason）：

| 温度域 | 挙動 |
|---|---|
| 低温 T≲1.2 | reasoning-order 支配（T とともに融解） |
| 中〜高温 T≈1.3-2.0 | reasoning 融解 → recitation-order が代替（ピーク T≈2.0） |
| 極限高温 T≳2.5 | recitation も失敗 → 全面 PM（T3.0 で ORDERED=0, pm≈0.9） |

onset は sigmoid ではなく「窓」（立ち上がり T≈1.2-1.4・ほぼ N 非依存 → ピーク T≈2.0 → 崩壊）。N6 では recitation=0（63手は復唱しきれない）。**M-1 アーティファクト（T3.0 の低下）は真正と確認**（全面 PM 崩壊であり tpm 誤分類ではない）。

## 機構の作業仮説（physics-agent 条件4）

**エントロピー/エネルギー競合（H-2 ii）**：高温では reasoning 軌道のエントロピーが増大し正解到達確率が低下する一方、記憶想起は短い決定論的1本道。中〜高温で記憶想起の自由エネルギーが reasoning を上回る。低温で recitation が出ないのは reasoning が安く正解できるため。高温記憶想起が標準 Hopfield/AGS（retrieval=低温）と符号が逆に見える点は、reasoning channel と memorization channel が別の有効自由度であることで解釈（決着は L2 検証後）。

## モデル間差異（H6 強化）

| モデル | recitation 総数 | 高温崩壊様式 |
|---|---|---|
| qwen3-14b | ≈175 | 記憶想起フォールバック（recitation-order） |
| qwen3-8b | ≈29 | 同上（弱い） |
| deepseek-7b | **0** | 真正崩壊（推論継続→loop/no-move） |
| deepseek-14b | ≈16 | ほぼ真正崩壊 |

## 結論と未決事項

1. **Qwen の $T_{c2}$ 主張は降ろす**（physics-agent 条件3）。N≥4 は「ordered 相不在」ではなく「**SG↔PM 境界が不明瞭**」と記述（M-3、真因＝統計不足／$T_{c1}$ 測定窓外／SG が低温まで広い、は未分離）。3相枠組みは全面改訂せず「ordered が N で測定窓から消える」精緻化に留める（L-1）。
2. **$T_{c2}$ の N 非依存性は DeepSeek ファミリーの性質**（H5、recitation 交絡なしで確認済み）。Qwen は別の崩壊様式（recitation フォールバック）を持つ（H6）。
3. **記憶 basin の H_eff 組み込み前提条件＝L2 $P(q)$ 検証は PASS**（2026-06-05、下記）。

## L2 $P(q)$ 検証結果（条件5・D-2 ゲート）→ PASS

recitation 群 / reasoning 群 / SG 群で、layer_mid 隠れ状態の試行平均ベクトル間 overlap $q$ を群内 pairwise に計算（per-cell で算出しプール）。

**生 cosine**（qwen3-14b）：recitation $q=0.999\pm0.001$（デルタ的）、reasoning $0.967\pm0.019$、SG $0.963\pm0.019$。recitation の分散が約20分の1。

**平均中心化**（共通成分＝異方性を除去、proper な $P(q)$）：

| 群 | $q_\text{mean}$ | median | 解釈 |
|---|---|---|---|
| **recitation** | **+0.527** | **+0.795** | レプリカ整列、有限 $q_{EA}$ ＝**構造化された記憶 basin** |
| reasoning | −0.002 | −0.057 | overlap≈0、凍結共通方向なし |
| SG | −0.022 | −0.044 | 同上 |

**結論**：recitation-order は隠れ状態空間で**鋭い記憶アトラクタ（想起された記憶パターン、$q_{EA}\approx0.53$）**として実在し、reasoning/SG（$q\approx0$）と明確に分離。スピングラス/Hopfield の retrieval 相署名。**多井戸描像（full-B/full-C 縮退基底 + 高温で顕在化する記憶 basin）が L2 で直接裏付けられた → H_eff への記憶 basin 組み込みのゲートを通過**。

未決：SG が trial-mean レベルで $q\approx0$（per-move の細かい解像度では構造が出る可能性、別途）。reasoning channel と memorization channel の有効温度分離（高温記憶想起の符号問題、H-2）は理論側で要詰め。

データ：`research_state/subclass_d3.json`（335セル）。図：`figures/recitation_order/<model>/`（recitation_fraction.png, pq_centered.png）。
