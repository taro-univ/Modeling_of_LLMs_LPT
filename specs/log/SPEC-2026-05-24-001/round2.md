# SPEC-2026-05-24-001 壁打ち Round 2

**日付**: 2026-05-24  
**参加者**: physics-agent, implementation-agent, orchestration  
**議題**: ① LightsOutEnv V(x) 定義の物理審査 ② Section 4.5 設計確認

---

## physics-agent 審査結果

**判定**: 条件付き合格

### 確定事項

| 内容 | 根拠 |
|---|---|
| $V(x)$ の位置づけを「進捗指標 (progress metric)」に変更。「推論ポテンシャル」とは呼ばない | Lights Out に局所最小値・鞍点がなく地形を持たないため |
| $V > 1.0$ が合法手のみで発生しうることを SPEC に明記 | GF(2) affine 空間上で $D(s_t) > D(s_0)$ が発生しうる |
| H3 falsifiable test の構造（landscape あり vs なし）を SPEC に明示 | Lights Out は landscape なし → コントロール実験として有効 |
| Algorithm C 不適用の理由を「involution があるため SG シグナルとして無効」と明記 | トグルは involution（同セル 2 連打 = 元に戻る）。正規表現非対応は表層的理由にすぎない |
| P(q) は hidden state 空間 or move sequence 空間で定義する方針を明記 | puzzle 空間が flat なため puzzle 空間での $P(q)$ 双峰性検出が困難 |

### user 判断待ち事項

| # | 判断内容 | physics-agent の推奨 |
|---|---|---|
| ① | V の正規化分母（$k_0$ or $N^2$） | 案 A（$N^2$）推奨：$V \in [0,1]$ が厳密保証、全初期配置で正規化定数共通 |
| ② | 一意性制約の範囲（解ベクトル or 最小解手数） | 緩和（最小解手数一意）で十分。$N \geq 4$ も使用可能になる |
| ③ | 実験対象 $N$ の範囲 | $N=3$ で H3 falsifiable test は可能。$N \geq 4$ は研究スコープ次第 |

### research-agent への依頼事項

1. 各 $N$ の隣接行列 $A$ の $\dim \ker A$ 一覧（$N=3,4,5,6,7$）の文献確認
2. GF(2) Lights Out の最小解 $k_0$ の分布（典型値・最大値）の既知結果
3. 「局所 flat な状態空間でランダムウォークが metastable な振る舞いを示す」既知結果（SG 相検出感度の評価に必要）
4. Lights Out / GF(2) パズルを LLM タスクとして使った先行研究の有無

---

## implementation-agent 設計確認結果

### 高優先度（H）懸念事項

| # | 箇所 | 内容 |
|---|---|---|
| 1 | 4.2 | `_simulate_states` 内 `_state_to_key` → `state_to_key` リネーム漏れ（サイレント `AttributeError`）。grep で確認必須 |
| 2 | 4.2 | abstract property 化に伴うバッキングストア変更（`_initial_state` / `_goal_state`）。`__init__` での直接代入が `AttributeError` になる |
| 3 | 4.3 | $V > 1.0$ の発生（physics-agent 指摘と整合）。分母確定は user 判断①依存 |
| 4 | 4.3 | 一意解再試行の無限ループリスク（$N \geq 4$）。逆算方式（解ベクトル → 初期状態）への変更を推奨 |

### 中優先度（M）懸念事項

- GF(2) 最小ハミング重み解の計算量（$\dim \ker A > 0$ 時は全列挙）
- `make_sub_env` の seed 設計（few-shot 例題の再現性）

### user 判断追加事項（実装前確認）

- `galois` ライブラリ依存追加の可否（ない場合は自前 GF(2) ソルバー実装が必要）

### 実装順序（全員合意）

```
Step 1: base_env.py 新規作成
Step 2: hanoi_env.py リファクタリング → test_early_stop.py PASS
Step 3: test_hanoi_env.py PASS → git commit（中間コミット）
Step 4: lights_out_env.py 新規作成（GF(2) コアから）
Step 5: test_lights_out_env.py PASS
Step 6: test_base_env.py PASS
```

---

## SPEC-2026-05-24-002 への波及

physics-agent 指摘：Section 2 の「Algorithm C 不適用」の理由を以下に修正予定：

- **Before**: 正規表現が "Toggle (i,j)" に対応しない
- **After**: Lights Out のトグルは involution であるため、同セル 2 連打が「物理的に意味ある操作」かつ「文法的ループ」を同時に満たし、SG シグナルとして使用不可

→ SPEC-B の壁打ちで正式に反映する。

---

## user 判断結果（2026-05-24 確定）

| # | 内容 | 決定 |
|---|---|---|
| ① | V 正規化分母 | **$N^2$ 採用**（$V \in [0,1]$ 厳密保証） |
| ② | 一意性制約 | **最小解手数一意（緩和）**（$N=4,5$ 使用可能） |
| ③ | 実験対象 $N$ | **$N=3,4,5$** |
| ④ | galois ライブラリ | **使用する** |

## 次のアクション

1. **research-agent**：各 $N$ の $\dim \ker A$ 文献確認・GF(2) 最小解分布（orchestration が別途依頼）
2. **orchestration**：research-agent 結果を受けて Section 3 を補完し、GATE A（壁打ち終了宣言）へ

---

## 変更履歴

| 日付 | 変更内容 | 担当 |
|---|---|---|
| 2026-05-24 | Round 2 議事録作成。V(x) 物理審査・Section 4.5 記入完了 | orchestration |
