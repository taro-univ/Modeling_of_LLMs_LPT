# Experiment Register

実験ごとに「どの仮説を検証したか・結果はどうだったか・仮説への影響」を記録する。
実験完了後、必ずここに1行追記する。

**status 凡例**: `pending`（実行待ち）/ `running`（実行中）/ `done`（完了・解析済み）/ `failed`（失敗・中断）

---

## レジスター

| exp_id | date | spec_id | hypothesis_ids | model | sweep_type | 結果サマリ | 仮説への影響 | status |
|--------|------|---------|----------------|-------|------------|-----------|------------|--------|
| EXP-001 | 2026-05-22 | SPEC-2026-05-22-001 | U2, H3 | deepseek-r1-distill-qwen-7b | full_sweep + collapse_phase | N=2: 全域 Ordered / N=3: 低T Ordered・高T SG / N=4-6: SG 支配（PM は高T側に確認）/ 総86セル | H3 supported — SG 相でのmove loop固着がP(q)双峰として観測。詳細は figures/pq_phase_classifier/ 参照 | done |
| EXP-002 | 2026-05-25 | ad-hoc | H5（新規）, H6（新規） | deepseek-7b / deepseek-14b / llama-8b | full_sweep + collapse_phase（解析のみ） | ボルツマン直線性不成立（全モデル全N）。Tc1 は N 増加で急落（N≥4 でほぼ 0）。Tc2 は deepseek 系で N 非依存（≈1.0〜1.2）、llama-8b は大幅に低い（N=3 で 0.124） | H5 active — 平衡ボルツマン不成立 → 非平衡SG理論フレームを示唆。H6 active — モデル間で相図が質的に異なる | done |
| EXP-003 | 2026-05-26 | ad-hoc | H6 | deepseek-r1-distill-llama-8b | collapse_phase（N3-6, T1.1-3.0） | N6 T=1.1 が全セル中で最も SG 的（pm%=23%, qbar_inter=0.51）。T_SG→PM(N=6)≈1.16。N3-5 は T=1.1 時点で既に PM 支配。N が大きいほど SG が高温まで持続 | H6 追記 — llama の崩壊相内部も特異。N=6 でのみ collapse range 内に SG→PM 遷移を捕捉 | done（N6 T1.8 データあり・解析は低優先度） |
| EXP-004 | 2026-05-26 | ad-hoc | H6 | qwen3-8b | full_sweep（N2-6, T0.1-1.0） | N=2: 全T で acc=72-100%（T=1.0 で25/25完璧）。N=3: 全T で acc=52-80%（deepseek-7b の T=1.0 acc=12% に対し 52%）。N=4 T=0.1: acc=0（no_move_catchall 72%、即PM崩壊）。N=3→N=4 の容量崖が非常にシャープ | H6 追記 — Qwen3-8B は N=3 で thinking robust、N=4 で即崩壊という独自パターン。DeepSeek 系とは崩壊様式が異なる | done（50/50 完了 2026-05-28） |
| EXP-005 | 2026-05-28 | ad-hoc | H6 | qwen3-8b | collapse_phase（N3-6, T1.1-3.0） | 36/36 完了（2026-06-05）。結果サマリは解析待ち | H6 — 解析後に更新予定 | done（36/36 完了 2026-06-05） |
| EXP-006 | 2026-06-02 | ad-hoc | H6 | qwen3-14b | full_sweep（N2-6, T0.1-1.0） | 51/52 完了。N6_T0_6 のみ欠損 | H6 — 14B サイズでの相図・Tc スケーリング確認 | done（51/52、N6_T0_6 欠損） |
| EXP-007 | 2026-06-05 | ad-hoc | H6 | qwen3-14b | collapse_phase（N3-6, T1.1-3.0） | 実行中（2026-06-05 開始）。36セル × 25試行 | H6 — Qwen3-14B の崩壊相内部構造。Qwen3-8B / DeepSeek-14B との比較 | running |
| EXP-008 | 2026-06-05 | ad-hoc（Track B, physics ラチファイ済み） | H5, H6 | 全4モデル + llama-8b | full_sweep + collapse_phase（再解析のみ） | ゴールペグ・パリティ交絡を発見・補正。対称化 accuracy で全432セル再計算（`symmetric_accuracy.json`、延べ +257 正解化）。相図再生成（`figures/phase_diagram_symmetric/`）。Tc2 再フィット（`tc2_refit_symmetric.md`）：**DeepSeek で N 非依存性を再確認**（高温 recitation なし）、Qwen は recitation-order で非単調化し保留。env 対称化を Codex 実装（commit 9137c23、43テスト pass、物理不変量検証済み） | **H5 — Tc2 N非依存性を DeepSeek で回復・確認（証拠復帰）**。H6 強化 — 高温崩壊様式のモデル差（Qwen=暗記復唱、DeepSeek=真正崩壊）。秩序変数・V(x) 対称化を正式採用・実装済み | done |

---

## 記入ガイド

### 新規実験を追加するとき

```
exp_id  : EXP-NNN（連番）
date    : 実験開始日（YYYY-MM-DD）
spec_id : 対応するSPEC ID（なければ「ad-hoc」）
hypothesis_ids : 検証対象の仮説ID（複数可、カンマ区切り）
model   : 使用モデルのslug
sweep_type : full_sweep / collapse_phase / stagnation_sweep / single
結果サマリ : 1〜2行で完了時に記入。ネガティブ結果も正直に書く
仮説への影響 : supported / falsified / inconclusive + 理由1行
status  : 上記凡例から選択
```

### 仮説への影響の書き方

- `H3 supported` — P(q)双峰がN=4,T=0.6で確認
- `H3 inconclusive` — 試行数不足、N≥5のデータ待ち
- `H3 falsified` — 全条件でP(q)が単峰（SG相の証拠なし）

---

## 完了実験のリンク集

実験完了後に結果ファイルへのパスを追記する。

| exp_id | results パス | figures パス |
|--------|------------|------------|
| EXP-001 | results/analysis/pq_phase_classifier/deepseek-r1-distill-qwen-7b/ | figures/pq_phase_classifier/deepseek-r1-distill-qwen-7b/ |
| EXP-002 | /tmp/sigmoid_fit_results.csv | figures/analysis/boltzmann_preflight/ |
