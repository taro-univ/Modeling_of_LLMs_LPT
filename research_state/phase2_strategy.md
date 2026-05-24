# Phase 2 戦略（Post-Hanoi）

Tower of Hanoi スイープ完了後の研究方針をまとめる。
**方針の判断は user 専権事項**。このファイルは決定済み方針の記録。

最終ゴールと全体方針は `CLAUDE.md` を参照。

---

## Phase 2 の位置づけ

```
Phase 1（現在）  : Tower of Hanoi × 5 モデル → P(q) 相図 → H3 支持の確認
                    ↓
Phase 2（次）    : 複数パズル × 複数モデル → 普遍性検証 + Hamiltonian 候補への fitting
                    ↓
Phase 3（6月末） : モデリング完了 → 制御外力シミュレーション（H4 段階 1）
                    ↓
Phase 4（7月）   : 中間報告（Hamiltonian + シミュレーション成功）
```

---

## 方針決定済み事項

### 1. 閾値（thresholds）の扱い

**決定**：現行の `configs/thresholds.default.json` を **プレースホルダーとして据え置く**。

**理由**：
- 現状は 7B と 14B の 2 モデルサイズのみ → モデルサイズ間のスケールを閾値に反映させるのは時期尚早
- 複数パズル × 複数モデルのデータが揃った段階で、データ駆動的に確定する
- 現行の閾値での相分類は「探索的・暫定」として扱う

**次アクション**：多モデル・多パズルデータ取得後に感度解析 → 閾値確定アルゴリズムを提案（Track B で実施）

---

### 2. 複雑度の定量化

**決定**：**パズルごとに定量化、相図を見てから汎用化を検討**。

- Tower of Hanoi：$K(N) = 2^N - 1$（最短解手数）
- 他パズルも同様に $K(N)$ を解析的に定義できるものを優先
- $K(N)$ が解析的に書けないパズル（Rush Hour 等）は採用しない

縦軸（複雑度）の普遍的な定量化は、複数パズルの相図が揃ってから検討する。

---

### 3. Hamiltonian 選定アーキテクチャ

**決定**：**データ収集後に一気に比較できるアーキテクチャを設計する**。

先に実装しない理由：
- 現状のデータ（1 モデル × 1 パズル）ではフィッティングの信頼性が低い
- 複数モデル × 複数パズルのデータが揃うと「一度に比較」できる

**イメージ**：
```
実験データ (summary.json × npz)
    ↓
物理量算出スクリプト（.sh で一括）
    ↓
候補 Hamiltonian への fitting（複数案を並列比較）
    ↓
フィジックスエージェントが整合性審査
```

**next step**：Hamiltonian 候補リスト（現行案：3 状態ボルツマン、2 秩序変数 Landau）は `open_questions.md` 参照。

---

### 4. 普遍性検証の進め方

**決定**：**好奇心ベースでパズルを選ぶ**。理詰めしすぎない。

- Frog Jump + River Crossing は確定
- 追加パズル（Lights Out, 8-puzzle, Pancake Sorting 等）は `research_state/puzzle_roadmap.md` 参照
- 相図の形状がパズル間で共通するかどうか → H3 の普遍性の判断材料

**臨界指数 α の抽出は棚上げ**：現状の試行数では統計的に有意な抽出不可（`hypotheses.md` 参照）。

---

## 優先読了論文

| 優先度 | 論文 | 理由 |
|---|---|---|
| ⭐⭐⭐ 最優先 | Almeida, Thouless, Sommers 1987 (AGS) | 相図の理論的基盤。SPEC-2026-05-22-001 の参照文献 |
| ⭐⭐⭐ 優先 | "Reasoning-Memorization Interplay mediated by a single direction" (arxiv:2503.23084) | hidden state の「推論方向」が Hopfield アトラクター対応 → H3 直結。isotropy.py の `remove_topk` が除去している主成分方向との関係を要確認 |
| ⭐⭐ | Hopfield 1982 (original) | Hopfield エネルギー関数の原典 |
| ⭐⭐ | Parisi 1979, 1983 (RSB) | レプリカ対称性の破れの原典 |

---

## Phase 2 移行チェックリスト

以下が揃ったら Phase 2 開始。

- [ ] Tower of Hanoi × 5 モデル の full_sweep 完了
- [ ] 5 モデル全ての P(q) 相図生成
- [ ] 相図の比較（モデル間での AGS 構造の一致・差異を確認）
- [ ] Frog Jump の実装・テスト完了
- [ ] River Crossing の実装・テスト完了
- [ ] AGS 1987 読了
- [ ] arxiv:2503.23084 読了

---

## メモ（議論から）

- **「スケールを閾値で決めちゃうのは怖い」**（user）→ 閾値決定の先送りを確定
- **「好奇心は大事にしたい」**（user）→ パズル選定に過度な理詰め不要
- **Ising SG の相図とそっくり**（user、qwen-7b 相図を見て）→ H3 の強力な supporting evidence
- **llama-8B は thinking model でないから正答率低い**（user）→ モデルの推論能力とパラメータ数の分離が必要。Qwen3 系（thinking on/off）と比較する価値あり
