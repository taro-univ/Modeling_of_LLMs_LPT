# docs/reports/

presentation-agent が生成する資料の置き場。

## ファイル命名規則

```
YYYYMMDD_progress.md        ← 中間報告スライドの Markdown ソース
YYYYMMDD_progress.pptx      ← pandoc 変換済み pptx
YYYYMMDD_<spec_id>.md       ← 実験レポートの Markdown ソース
YYYYMMDD_<spec_id>.pptx     ← pandoc 変換済み pptx
YYYYMMDD_*_figures/         ← 挿入した図のコピー
```

## 編集ワークフロー

1. `*.md` を直接編集（数式は `$...$` で記述）
2. pandoc で再変換：
   ```bash
   pandoc <stem>.md --from markdown+tex_math_dollars --to pptx \
     --reference-doc /tmp/reference.pptx -o <stem>.pptx
   ```
3. PowerPoint で仕上げ編集（数式は OMML として編集可能）

## 関連ファイル

- `docs/design_system.yml` — 記号定義・配色・テンプレートの権威
- `.claude/agents/presentation-agent.md` — 生成エージェントの仕様
