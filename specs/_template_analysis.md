---
spec_id: SPEC-YYYY-MM-DD-NNN
type: analysis
status: draft
hypothesis_refs: []
proposed: YYYY-MM-DD
finalized:
---

# [解析タイトル]

<!-- Track B（解析専用）テンプレート。
     実装を伴わない純粋な解析・探索タスクに使う。
     physics-agent 確認のみ。GATE B/C なし。実装 → quality-check → Codex 不要。 -->

---

## 1. 目的・動機（user 記述）

<!-- どの仮説（H*）または open_question（U*）を調べるか。
     何を見れば何がわかるか、1〜3行で。 -->

---

## 2. 物理的チェック【physics-agent のみ】

### 2.1 保存則・対称性の要件

<!-- 解析が暗に仮定していること（例：レプリカ交換対称性、Z2対称性の有無）を列挙 -->

### 2.2 解析結果の解釈上の注意

<!-- 有限サイズ効果・censored data・非自己平均性など、物理的に見落としやすい点 -->

### 2.3 physics-agent 判定

- **判定**: 未審査
- **審査日**:
- **コメント**:

---

## 3. 解析手順

### 3.1 入力データ

<!-- 何のファイルを使うか（summary.json / npz / metrics.csv など）、パス指定 -->

### 3.2 手順（箇条書き）

1.
2.
3.

### 3.3 使用スクリプト

<!-- 既存スクリプトをそのまま使う場合は引数を明記。
     新規スクリプトが必要なら SPEC が重すぎる可能性あり → 実装 Spec に切り出すことを検討 -->

```bash
# 実行コマンド例
python3 analysis/xxx.py --dir results/... --output figures/...
```

---

## 4. 出力仕様

| 出力ファイル | 形式 | 説明 |
|---|---|---|
| `figures/xxx/<model_slug>/yyy.png` | PNG | |
| `results/analysis/xxx/<model_slug>/yyy.csv` | CSV | |

---

## 5. 実験レジスター記入欄

<!-- 解析完了後に `research_state/experiment_register.md` に転記する内容を先に書いておく -->

- **exp_id**: EXP-NNN（レジスターで採番）
- **hypothesis_ids**: （H* または U*）
- **想定される結論**:
  - 支持される場合：
  - 棄却される場合：
  - 不確定の場合：

---

## 6. 壁打ち参照（必要な場合のみ）

| ラウンド | ファイル | 日付 | 主な決定事項 |
|---|---|---|---|
| Round 1 | specs/log/SPEC-YYYY-MM-DD-NNN/round1.md | | |

---

## 7. チェックリスト

- [ ] physics-agent: Section 2 確認済み
- [ ] 解析実行完了
- [ ] experiment_register.md に記入済み
- [ ] hypotheses.md の該当仮説の status / evidence を更新済み
