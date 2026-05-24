# SPEC-2026-05-22-001 Round 1 — 2026-05-22

## このラウンドの確認事項

- 現行分類器を P(q) moments ベースへ全面再設計する前提を仕様化する
- 等方化を分類器の必須前処理に含める
- `stagnation_after_move` と `think_budget` の扱いを明確化する

## 議論の要約

`SPEC-2026-05-21-001` の診断により、`stagnation_after_move` は出現頻度が低く、
P(q) 分布として強い判定材料にはならなかった。一方、観測できたペアでは no_move より
move_loop に近い overlap を示したため、SG 寄りの補助シグナルとして扱うのが妥当とした。

現行の相分類は early_stop ラベル率と q_EA と称する時間自己相関に依存している。
これは SG 理論の overlap 分布 $P(q)$ ではないため、分類器を hidden state レプリカ間の
P(q) moments ベースへ置き換える必要がある。

## 決定事項

- 新 SPEC は `SPEC-2026-05-22-001` とする。
- 分類対象は `ordered`, `spin_glass`, `paramagnetic`, `transitional`, `undetermined` とする。
- `think_budget` は censored data として相判定の分母から除外する。
- `stagnation_after_move` は主判定ラベルではなく補助特徴として記録する。
- hidden state の等方化を必須前処理として設計に入れる。

## 次ラウンドへの持ち越し

- physics-agent に Section 2 の正式判定を依頼する。
- implementation-agent に Section 4 のファイル分割・API 設計を詰めてもらう。
- 閾値を固定値にするか、データ駆動で推定するかを user と確認する。
