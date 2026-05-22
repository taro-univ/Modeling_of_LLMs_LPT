# Experiment Register

実験ごとに「どの仮説を検証したか・結果はどうだったか・仮説への影響」を記録する。
実験完了後、必ずここに1行追記する。

**status 凡例**: `pending`（実行待ち）/ `running`（実行中）/ `done`（完了・解析済み）/ `failed`（失敗・中断）

---

## レジスター

| exp_id | date | spec_id | hypothesis_ids | model | sweep_type | 結果サマリ | 仮説への影響 | status |
|--------|------|---------|----------------|-------|------------|-----------|------------|--------|
| EXP-001 | 2026-05-22 | SPEC-2026-05-22-001 | U2, H3 | deepseek-r1-distill-qwen-7b | full_sweep + collapse_phase | N=2: 全域 Ordered / N=3: 低T Ordered・高T SG / N=4-6: SG 支配（PM は高T側に確認）/ 総86セル | H3 supported — SG 相でのmove loop固着がP(q)双峰として観測。詳細は figures/pq_phase_classifier/ 参照 | done |

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
