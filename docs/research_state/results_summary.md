# results_summary.md — 観測事実の短縮版

`hypotheses.md` の測度定義に対応する現時点の観測事実。詳細な生データは `results/hanoi/` 参照。

## 確認済み（観測事実）

- Hanoi の N-T sweep データが5モデル分存在する:
  `qwen3-8b`, `qwen3-14b`, `deepseek-r1-distill-qwen-7b`, `deepseek-r1-distill-qwen-14b`,
  `deepseek-r1-distill-llama-8b`（`results/hanoi/full_sweep/`, `results/hanoi/collapse_phase/`）。
- `analysis/plot_hanoi_nt_collapse.py` で `summary.json` から $P_{\rm success}(N,T)$ と
  dominant failure mode（move_loop / no_move / mixed / other）を N-T 平面で集計できる
  （出力: `figures/hanoi_nt_collapse/hanoi_nt_collapse_<model>.{png,csv}`）。
- **qwen3-14b は N=4, T≈1.45–1.55（各条件 n=30 試行）で正答率が 0 近傍から 0.70–0.73 へ跳ね上がる。**
  N=5 でも T≈1.3–2.0（各条件 n=25 試行）で 0.32–0.52 まで回復する。低温域（おおむね T<1.3）ではほぼ 0。
  （`results/hanoi/collapse_phase/qwen3-14b/N4_T1_45` 等、`figures/hanoi_nt_collapse/hanoi_nt_collapse_qwen3-14b.csv`）
- 同条件の **qwen3-8b は N=4,5 で全 T 域にわたり正答率 0 のまま**（跳ね上がりなし）。
- **deepseek-r1-distill-qwen-14b は N=4 で急な回復ではなく、広い T 域（0.1–1.2）にわたり
  緩やかな高原状の正答率（0.2–0.36）を示す。** qwen3-14b とは異なるパターン。

## 解釈（未検証 — 事実と混同しないこと）

- 高温での回復は「低温では届かない解法軌道が高温で開く」という temperature scaling 仮説
  （Wu, Mirhoseini, Tambe 2025, arXiv:2510.02611; `docs/0703_セミナー/hanoi_temperature_memory_related_papers.md`）
  に見た目は整合的だが、Hanoi での因果的な検証（軌道の中身を見て実際に別の解法パターンかを確認する等）は
  まだ行っていない。

## 要確認

- 上記 n=30 / n=25 という試行数が、この非単調な振る舞いを結論づけるのに十分かは要検討
  （再現性の追加検証は `todo.md` 参照）。
