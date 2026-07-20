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

## $C_{\rm eff}$ / $w_N$ 算出結果（`analysis/measure_wn_ceff.py`、qwen3-8b, qwen3-14b）

- **$C_{\rm eff}=-\log P_{\rm success}$ は問題なく計算できる。** qwen3-14b N=4 では、リバイバル点
  （T=1.45, T=1.55）だけ有限値（$C_{\rm eff}\approx0.36, 0.31$）になり、それ以外の T はほぼ $\infty$。
  「N=4 は基本的に解けないが、T=1.45–1.55 の狭い窓でだけ実効的に解ける」という言い方ができる。
- **$w_N$（単一交差点 + $\epsilon=0.1/0.9$ 境界の元の定義）は、qwen3-8b/qwen3-14b の全 N でほぼ計算不能。**
  `non_monotonic` フラグの原因は3パターンに分かれ、混同しないよう区別が必要（詳細は `hypotheses.md`）:
  1. 観測 T 域で $P=0.5$ を一度も跨がない（qwen3-8b N=2 は高止まり、N=4-6 は全域 0.00、qwen3-14b N=6 も全域 0.00）
  2. サンプリングノイズによる閾値付近の複数交差（qwen3-8b N=3; qwen3-14b N=2 は $T_{1/2}=1.38$ という
     きれいな単一交差点が出たが、$\epsilon=0.9$ 境界がノイズで2回跨いだため $w_N$ 自体は未算出）
  3. 本物の非単調（qwen3-14b N=4: `...1.4:0.00 → 1.45:0.70 → 1.55:0.73 → 1.8:0.00...`、N=3 も
     T=1.1–1.55 で 0.48–0.73 を往復しており弱い前兆に見える）
- 結論: 元の $w_N$ 定義はこのデータの形状（平坦・ノイズ・本物の非単調が混在）に対して厳しすぎる。
  再定義の方向性は `hypotheses.md` の未検証・要確認セクション参照。

## ハーネスは $S_{\rm visit}$ / $S_{\rm trap}$ / $F$ に足るデータを出しているか（確認済み）

- `runners/run_local.py`(HF)が npz に保存する `move_texts`（試行ごとの手順文字列列）は、`summary.json` の
  `moves_extracted`（ゴール判定に使った実際の手数）と**完全に一致する**ことを実データで確認した
  （`results/hanoi/` 全体 12,250 試行を走査し、fallback試行の自明な差分(0 vs 1)を除いて非自明な食い違いは0件）。
- したがって `move_texts` を `envs/hanoi_env.py` の `initial_state`/`_apply_move` で再生すれば、試行ごとの
  訪問状態列・終端状態・各円盤の凍結タイミングを厳密に再構築できる。$S_{\rm visit}$, $S_{\rm trap}$, $F$
  いずれも既存データのみで計算可能（ハーネス側の追加記録は不要）。fallback試行
  （`move_texts==["__fallback__"]`）は終端状態=`initial_state`として特別扱いする。
- **`runners/run.py`(Ollama版)は対象外。** `summary.json` に `moves_extracted` という個数しか残さず、
  手順そのものや生成テキストを保存しない。npz もない。現状の主要な N-T sweep データは全て
  `run_local.py` 経由なので実害はないが、Ollama経由データでは3指標とも再構築不可能。
