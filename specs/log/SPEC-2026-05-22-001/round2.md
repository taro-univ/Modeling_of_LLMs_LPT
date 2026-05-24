# SPEC-2026-05-22-001 Round 2 — 2026-05-22

## このラウンドの確認事項

- implementation-agent による Section 4 設計確認（ファイル分割・API・CLI・出力仕様）
- 閾値の扱い（固定値 vs データ駆動）のユーザー確認
- physics-agent による Section 2 正式審査（進行中）

## 議論の要約

**閾値の扱い（user 確定）**

`acc_ordered_min` など分類閾値は「固定値として CLI/JSON 外出し＋感度解析」方式に確定。
現ドラフトの Section 4.3 の方針そのまま。初期値は全て `null` とし、感度解析後に埋める。

**implementation-agent 設計確認（総合判断：要修正→修正完了）**

以下の 4 点を仕様書に反映済み：

1. **`--topk` 外出し**：`remove_topk(k=3)` の `k` をマジックナンバーから解放。
   Section 4.1 擬似コードの入力引数に `topk` を追加。

2. **`thresholds.default.json` スキーマ**：閾値キー名・型・デフォルト値を
   `configs/thresholds.default.json` で管理する方針を Section 4.3 に明記。

3. **`stagnation_rate` → `stagnation_after_move_rate`**：他の `*_rate` 列との命名規則統一。
   Section 4.4 のカラム定義を修正済み。

4. **`analyze_pq.py::classify_phase` の deprecated 化**：
   新分類器リリース後に旧関数を deprecated にする計画を Section 6 に記録。

**`pq_metrics.py` の責務（implementation-agent 推奨）**

- 担当：等方化後の overlap moments（`q_var`, `q_tail_mass`, `q_bimodality` など、既存にない計算）のみ
- `_cosine` / `compute_pq` / `compute_qea` は `analyze_integrated.py` から import（重複コード禁止）
- `_cosine` の非公開関数 import には TODO コメントを必ず添付（将来の公開化を担保）

**`load_condition` のシグネチャ注意点**

`analyze_pq.py` 版（単一 dir）と `analyze_integrated.py` 版（複数 dirs リスト）でシグネチャが異なる。
新分類器は後者（複数 dirs 対応）を使うことをコード内コメントで明示すること。

## 決定事項

- 閾値：固定値 CLI/JSON 外出し＋感度解析（user 確認済み）
- Section 4 修正 4 点を仕様書に反映済み
- `pq_metrics.py` 責務範囲：新規 moments 計算のみ
- `analyze_pq.py::classify_phase` は新分類器リリース後に deprecated 化

## physics-agent 審査結果（Round 2 中に完了）

**判定: 条件付き合格 → 全条件解消済み**

主な指摘と対応：
- (C2.1-c) `q_abs_mean` の Z2 根拠 → research R1 調査完了。根拠なし → 探索的記録に格下げ（user 確定）
- (C2.2-a) μ 推定範囲 → 全条件 union に確定（user 確定）
- (C2.2-d) default layer → layer_mid に確定（user 確定）
- (C2.3-c) q_bimodality → Sarle's BC + Hartigan's dip の両方を計算（Pfister 2013 準拠）
- (C2.4-b/c) Ordered/SG 判定条件 → Section 2.4・4.3 を整合化（q_var 上限・q_bimodality 追加）
- (C2.4-d) pm_rate → 補助シグナルに格下げ、PM 主判定は q_mean + q_var ベースに変更（user 確定）

推奨事項として反映済み：
- self-overlap は off-diagonal のみと明記（Section 2.1）
- q^{αβ} = q^{βα} の対称性を要件として明記（Section 2.1）
- T_α step 数依存性の mitigation（短試行除外ルールを Section 2.3 に追記）
- Hopfield/AGS 相図との対応を Section 2.4 に追加
- 有限サイズ効果の注意書きを Section 2.4 に追加
- bootstrap CI を metrics 出力仕様に追加（Section 2.3/4.4）

## research-agent 調査結果（R1〜R4、Round 2 中に完了）

- **R1**: LLM 埋め込みに Z2 対称性の文献的根拠なし。isotropy ≠ 原点対称。→ `q_abs_mean` 探索的に格下げ
- **R2**: AGS 相図確認。Retrieval/SG/PM の P(q) 特徴を Section 2.4 に反映
- **R3**: Sarle's BC は SG 文献で前例なし。Pfister 2013 が BC + dip 併用を推奨 → 両方計算に変更
- **R4**: trials=25（pairs=300）は 1〜2 次 moment には十分だが 4 次（kurtosis）は bootstrap CI 必須

## 次ラウンドへの持ち越し

なし。**physics-agent 条件 4 件がすべて解消された。**

→ **GATE A 準備完了**：ユーザーが壁打ち終了を宣言すれば `specs/final/` へ移行できる状態。
