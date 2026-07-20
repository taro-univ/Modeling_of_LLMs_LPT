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

- [x] `plot_hanoi_nt_collapse.py` の出力CSVから $w_N$（遷移幅）と $C_{\rm eff}=-\log P_{\rm success}$ を
      $N$ ごとに算出する `analysis/measure_wn_ceff.py` を作成（BaseAnalyzer非依存、単純スクリプト）。
      $C_{\rm eff}$ は問題なく動作。$w_N$ は qwen3-8b/14b の全Nでほぼ`non_monotonic`判定になり、
      元の定義がデータ形状に合わないことが判明（`results_summary.md` 参照）。
- [ ] $w_N$ の定義を再設計する。`non_monotonic`判定の3原因（① T域内で0.5を一度も跨がない、②閾値付近の
      サンプリングノイズ、③本物の非単調）を区別できる形にする。案:
      - $\epsilon=0.1/0.9$ 境界の要件を外し、$T_{1/2}$ の存在だけで簡易版 $w_N$ を出す
      - 交差点の振れ幅（accuracy の変化量）でノイズ由来(②)と本物(③)を閾値分離する
      - ①（平坦）は $w_N$ 対象外として明示的に除外する
- [ ] measure_wn_ceff.py にテストを書く（現状テストなし）。
- [x] `run_local.py` / `run.py` が $S_{\rm visit}$・$S_{\rm trap}$・$F$ に足るデータを出しているか確認した。
      `run_local.py`(HF)は npz の `move_texts` を再生すれば3指標とも計算可能（`results_summary.md` 参照、
      12,250試行で忠実性を実データ検証済み）。`run.py`(Ollama)は手順を保存しておらず対象外。
- [ ] 上記の再生ロジック（npz `move_texts` → `envs/hanoi_env.py` で状態列再構築）を使って
      $S_{\rm visit}$ / $S_{\rm trap}$ / $F$ を計算する新規スクリプトを設計する（BaseAnalyzer非依存）。
- [ ] qwen3-14b の N=4 (T≈1.45–1.55) / N=5 (T≈1.3–2.2) の高温回復を、trial数を増やして再現性確認する。
- [ ] Frog Jump を `hypotheses.md` の測度計画に接続するか、対象外として明示するかを決める
      （現状 `experiment_register.md` に書いた通り未接続）。

## 学習（写経、実験・実装とは別日で進める）

- [ ] `docs/study_hanoi_oop_checklist.md` の Phase 1（`__init__` と状態表現）へ進む。
