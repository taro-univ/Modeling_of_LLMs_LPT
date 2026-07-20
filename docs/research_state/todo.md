# todo.md — 次にやること

## 進行中: 実装・ドキュメントのリファクタリング（2026-07-20〜）

過剰な共通化（BaseAnalyzer フレームワーク）と、`hanoi_entropy_complexity_slides.md` に対応しない
別系統の仮説（SG/PM分類・4-regime・critical dynamics 等）を削除し、`hypotheses.md` を唯一の仮説源として
再構築する作業。

- [x] SG/PM系解析コード一式を削除（`spin_glass.py`, `pq_metrics.py`, `pq_phase_classifier.py`,
      `isotropy.py`, `cosine_sim_phase.py`, `analyze_pq.py`, `configs/thresholds.default.json`,
      `analysis/pq_output/`, `analysis/adhoc/*`, 関連テスト）
- [x] BaseAnalyzer共通化フレームワークを解体（`base_analyzer.py`, `run_pipeline.py`,
      `analyze_phase_diagram.py`, `analyze_slowing.py`, `critical_dynamics.py`, `phase_transition.py`）
- [x] `stagnation_diagnostic.py` / `io_utils.py` を削除（同じくP(q)診断ロジック、かつ既にImportErrorで破損）
- [x] `CLAUDE.md` の壊れた参照（`run_pipeline.py --analyzers ...`, `configs/thresholds.default.json`）を修正
- [x] `docs/research_state/{hypotheses,results_summary,experiment_register,todo}.md` を新設
- [ ] 上記の削除・新設をコミットする（現状 `git rm` 済みでステージングのみ、コミットは未指示）

## 次の実験・実装タスク

- [ ] `plot_hanoi_nt_collapse.py` の出力CSVから $w_N$（遷移幅）と $C_{\rm eff}=-\log P_{\rm success}$ を
      $N$ ごとに算出する追加スクリプトを設計する（BaseAnalyzer非依存、単純スクリプトとして）。
- [ ] $w_N$ の定義を、qwen3-14b で観測された非単調な $P_{\rm success}(N,\lambda)$（`results_summary.md`）
      にどう対応させるか決める（単調減少を仮定した元の定義のままでは破綻する）。
- [ ] `run_local.py` / `run.py` が $S_{\rm visit}$（訪問状態エントロピー）・$S_{\rm trap}$（失敗終端状態の
      多様性）・$F$（凍結度）を後段で計算するのに十分なデータを出力しているか確認する。
      不足があればお手本コードとして提示する。
- [ ] qwen3-14b の N=4 (T≈1.45–1.55) / N=5 (T≈1.3–2.2) の高温回復を、trial数を増やして再現性確認する。
- [ ] Frog Jump を `hypotheses.md` の測度計画に接続するか、対象外として明示するかを決める
      （現状 `experiment_register.md` に書いた通り未接続）。

## 学習（写経、実験・実装とは別日で進める）

- [ ] `docs/study_hanoi_oop_checklist.md` の Phase 1（`__init__` と状態表現）へ進む。
