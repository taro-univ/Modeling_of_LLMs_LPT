# experiment_register.md — 実験台帳

SPEC番号・EXP番号による実験管理は廃止した。かわりに「何が・どこにあるか」だけを軽量に記録する台帳。
実施日はディレクトリの mtime が一括操作で上書きされている箇所があり不正確なため、原則記載しない
（要確認が必要な場合は都度 `find <dir> -printf '%T+'` 等で個別確認する）。

## Hanoi — N-T sweep

| 内容 | モデル | N range | T range | 出力先 |
|---|---|---|---|---|
| full sweep | qwen3-8b, qwen3-14b, deepseek-r1-distill-qwen-7b/14b, deepseek-r1-distill-llama-8b | 2–6 | 0.1–2.0 | `results/hanoi/full_sweep/<model>/` |
| collapse phase（高温域の精密化） | 上記5モデル | 2–6 | 1.1–3.0（一部 full sweep と重複・上書き） | `results/hanoi/collapse_phase/<model>/` |
| stagnation sweep | deepseek-r1-distill-qwen-7b | 要確認 | 要確認 | `results/hanoi/stagnation_sweep/deepseek-r1-distill-qwen-7b/` |

集計は `analysis/plot_hanoi_nt_collapse.py --input-dir results/hanoi/full_sweep --input-dir results/hanoi/collapse_phase`
で行う（後者が同一 (N,T) セルを上書き）。出力: `figures/hanoi_nt_collapse/`。

## Frog Jump（探索的、Hanoi ほど整理されていない）

| 内容 | モデル | 出力先 |
|---|---|---|
| probe / probe_es / probe_v2 / smoke_* | qwen3-8b, qwen3-14b | `results/frog_jump/<run_name>/<model>/` |

Frog Jump は `hypotheses.md` の測度計画にまだ接続されていない。現状は生データの置き場のみ。

## 台帳への追記ルール

- 新しい sweep を実行したら、内容・モデル・N/T range・出力先の1行をこの表に追加する。
- 「何を検証するための実験か」は `hypotheses.md` の該当仮説番号を書く（例: 仮説3）。
  検証目的が `hypotheses.md` に無い実験は、先に `hypotheses.md` に仮説を追記してから実行する。
