# SPEC-2026-05-24-001 壁打ち Round 1

**日付**: 2026-05-24  
**参加者**: user, physics-agent, implementation-agent, quality-check-agent, orchestration

---

## 発端

`puzzle/lights-out` ブランチで Lights Out を実装するにあたり、  
`BaseEnv` の拡張耐性に問題があることが判明。三者並列審査を実施した。

## 主な決定事項

### 1. `_compute_V` を BaseEnv から削除（user 確定）

physics-agent の指摘：「$V(x)$ の定義はパズル間で物理的に非同型。  
ハノイの $V \in [0,1]$ 正規化を全パズルに強制すると、比較不能なスケールが混在し  
研究の根幹（スケーリング則・制御モデル）を汚染する」

user 判断：削除で。

### 2. SPEC を A/B 2 枚に分割（user 確定）

- SPEC-A（本 SPEC）：`base_env.py` 分離 + `lights_out_env.py` 実装
- SPEC-B（SPEC-2026-05-24-002）：`run_local.py` の env 非依存化

理由：後から見返すときの可読性、LightsOutEnv 設計に user 確認事項が残るため。

### 3. Pancake Sorting を候補から除外（user 確定）

理由：最短反転数 NP-hard → `_min_moves_from` の厳密最短契約を満たせない。  
`puzzle_roadmap.md` の 非推薦セクションに移動済み。

### 4. 実装順序：Option 1（A → B）（全エージェント推奨）

base_env.py を先に確定させ、その契約に基づいて run_local.py を改修する。  
中間コミット（A 完了時点）でハノイが動作継続することを確認してから B に進む。

## 未解決事項（次回壁打ち / physics-agent 追加確認）

- LightsOutEnv の $V(x) = D_{\mathrm{GF2}} / \text{min\_moves}$ の物理的正当性
  （physics-agent の追加確認が必要）
- Algorithm C（ループ検出）が Lights Out に適用されないことの物理的影響  
  → SG 相のシグナル欠落リスク（SPEC-B Section 2 に記載）

## エージェント間の合意事項まとめ

| 変更 | physics | impl | quality |
|---|---|---|---|
| `_compute_V` 削除 | ✅ 強く推奨 | ✅ | ✅ |
| `min_moves` abstract property 化 | ✅ | ✅ | ✅ H-2 |
| `extract_moves_from_text` abstract 化 | — | ✅ | ✅ M-1 |
| `_state_to_key` → abstract `state_to_key` | ✅ | ✅ | ✅ H-1 |
| `get_bad_move` を abstract から除去 | — | — | ✅ M-4 |
| `make_sub_env(N)` 追加 | — | ✅（few-shot） | — |
| Option 1（A→B）実装順序 | — | ✅ | — |
