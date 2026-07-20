# hypotheses.md — 仮説の正本

出典: `docs/0703_セミナー/hanoi_entropy_complexity_slides.md`（2026-07-03 セミナー資料）。
仮説はこの1文書から再構築する。ここに書かれていない仮説（SPEC番号・EXP番号・4-regime・SG/PM分類等）は
2026-07-20 に実装ごと廃止済みなので、参照しない。

## 測度定義（5つ）

| 記号 | 意味 |
|---|---|
| $P_{\rm success}(N,\lambda)$ | サイズ $N$・制御パラメータ $\lambda$（温度 $T$ 等）での成功率 |
| $w_N$ | 遷移幅。$\dfrac{\lambda_{1-\epsilon}(N)-\lambda_\epsilon(N)}{\lambda_{1/2}(N)}$。$N\to\infty$ で0に行けば sharp、行かなければ coarse |
| $S_{\rm visit}$ | モデルが実際に訪問した状態のエントロピー $-\sum_x p(x)\log p(x)$ |
| $C_{\rm eff}(N,\lambda)$ | 実効困難性。$-\log P_{\rm success}(N,\lambda)$ |
| $S_{\rm trap}$ | 失敗終端状態の多様性。$-\sum_{z\in Z} p(z)\log p(z)$ |
| $F$ | 凍結度。$\#\{$以後ほぼ変更されないサブゴール$\}/N$ |

## 理論的背景（確立済みの数学的事実 — Hanoi graph固有）

- 状態数: $|V(H_N)|=3^N$、標準解長: $L^*(N)=2^N-1$。
- 全域木エントロピー: $h_{\rm tree}=\frac14\log 15\approx0.677$（Zhang et al. 2015, arXiv:1510.07949）。
  実験値ではなく理論ベースラインとして背景に置く。
- これらはHanoi graphの性質そのものであり、LLM実験の結果によって否定されうる「仮説」ではない。

## 仮説（要検証、スライド Section 7 準拠）

1. **難しさは NP完全性ではなく閾値の鋭さ・粗さ（$w_N$）で測るべき。**
   出典: Istrate 2000 (arXiv:cs/0005032) からの類推。Hanoi 実験での検証は未実施。
2. **困難性は解空間の「クラスタ化」よりも「凍結・閉じ込め」に強く関係する。**
   出典: Krzakala & Zdeborova 2007 (arXiv:0711.0110) からの類推。$S_{\rm trap}$, $F$ で代理測定する方針。
   Hanoi 実験での検証は未実施。
3. **Hanoi/LLM 実験では $P_{\rm success}$, $w_N$, $S_{\rm visit}$, $S_{\rm trap}$, $F$ を $N$ ごとに追うべき。**
   これは検証対象というより実験方針。実装状況は `todo.md` 参照。

## 廃止した仮説・ナンバリング（参照しない）

`SPEC-2026-*`, `EXP-XXX`, `D-3`, `H7'`, `4-regime`, SG/PM(spin glass/paramagnetic)分類、
`q_EA`, `chi_SG`, Binder cumulant 等。

理由: 上記の5measure計画に対応しない別トラックの仮説群のため、関連解析コード
（`base_analyzer.py`, `spin_glass.py`, `pq_metrics.py`, `pq_phase_classifier.py`, `isotropy.py`,
`cosine_sim_phase.py`, `critical_dynamics.py`, `phase_transition.py`, `stagnation_diagnostic.py` 等）
とともに 2026-07-20 に削除した。

## 未検証・要確認（次に詰めるべき論点）

- **$w_N$ の元の定義（単一交差点 + $\epsilon=0.1/0.9$ 境界）はこのデータセットの形状に合わない。**
  `analysis/measure_wn_ceff.py` で qwen3-8b / qwen3-14b の全 N に適用したところ、ほぼ全 N が
  `non_monotonic` と判定された。原因は3パターンに分かれる（詳細は `results_summary.md`）:
  1. 観測 T 域内で一度も $P=0.5$ を跨がない（平坦に高い/低いだけ。qwen3-8b N=2, N=4-6, qwen3-14b N=6）
  2. 閾値付近のサンプリングノイズによる複数交差（n=20〜25試行では $\pm0.1$ 程度は普通に揺れる。qwen3-8b N=3,
     qwen3-14b N=2 の $\epsilon=0.9$ 境界）
  3. 本物の非単調（qwen3-14b N=4 の高温リバイバル。交差点が2つで、かつ振れ幅がノイズより明確に大きい）
  → $w_N$ の再定義（$\epsilon$ 境界の要件を緩める／交差点数そのものを指標にする等）が必要。$T_{1/2}$ 単体は
  パターン2のケースでも有効な値が出ている（例: qwen3-14b N=2 で $T_{1/2}=1.38$）ので、$w_N$ が計算できない
  場合でも捨てずに残す価値がある。
- $S_{\rm visit}$, $S_{\rm trap}$, $F$ は「どのデータから何を集計すれば計算できるか」を確認済み（`results_summary.md`
  参照）。`run_local.py`(HF)出力の npz `move_texts` を `envs/hanoi_env.py` の `initial_state`/`_apply_move` で
  再生すれば、訪問状態列・終端状態・凍結度いずれも再構築できる。計算スクリプト自体は未実装。
  `runners/run.py`(Ollama版)出力は手順そのものを保存していないため対象外。
