# SPEC-2026-05-21-001 Round 2 — 2026-05-22

## このラウンドの確認事項

- `stagnation_sweep` が完了しているか
- `stagnation_after_move` が P(q) 分布として判定可能な頻度で出ているか
- Q3（`stagnation_after_move` の相帰属）を後続 SPEC にどう渡すか

## 議論の要約

`hanoi-minimal` 内の実験プロセスは終了しており、`results/hanoi/stagnation_sweep/deepseek-r1-distill-qwen-7b/`
配下に `N=3,4,5`、`T=0.4..0.9` の全18セルで `summary.json` が生成済みだった。
各セルは25 trials、合計450 trials。

early_stop 全体内訳は `goal_reached=31`, `move_loop_repeat=92`, `no_move_catchall=215`,
`move_ceiling=8`, `stagnation_after_move=10`, `none=94`。
`stagnation_after_move` は 10/450 = 2.2% と少なく、同一セル内で2件以上あったのは
`N=5,T=0.4` と `N=5,T=0.6` の2セルのみだった。

3層（`layer_top`, `layer_mid`, `layer_low`）で診断スクリプトを実行したところ、
観測可能だった stagnation ペアの q は no_move より move_loop に近かった。
ただし、各セルの stagnation ペア数は1であり、分布形状を比較するには統計不足。

## 決定事項

- Q3 の暫定判断: `stagnation_after_move` は SG 寄りの補助シグナルとして扱う。
- ただし、P(q) ベース分類の主判定ラベルには使わない。
- 後続の P(q) moments ベース分類では、`stagnation_after_move` は補助特徴または
  `transitional/undetermined` 判定の参考情報として扱う。
- PM 主シグナルは `no_move_catchall` と `move_ceiling` に限定する。

## 次ラウンドへの持ち越し

- SPEC-2026-05-22-001 として P(q) moments ベース分類のドラフトを作成する。
- 等方化（centering + whitening）を物理的要件に入れる。
- `think_budget` は censored data として扱う仕様にする。
