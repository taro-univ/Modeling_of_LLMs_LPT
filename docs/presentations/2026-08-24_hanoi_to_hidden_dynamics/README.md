# 大規模言語モデルの物理モデリング — サマーインターン発表資料

2026-08-25の社内発表用資料。PowerPoint内へ記入された修正指示を反映した本編14枚。

## ファイル構成

```text
2026-08-24_hanoi_to_hidden_dynamics/
├── README.md
├── source/
│   └── build_deck.py
├── figures/
│   ├── shojaee_2025_figure6.png
│   ├── shojaee_2025_figure7.png
│   ├── zhu_2026_figure2.png
│   ├── carson_2025_icml_page.png
│   └── hanoi_deepseek_14b_accuracy.png
└── output/
    └── hanoi_to_hidden_dynamics_2026-08-24.pptx
```

`output/*.pptx` が発表・編集用の正本。

## スライド構成

1. 表紙
2. 目次
3. 研究のモチベーション：複雑度に伴う推論崩壊
4. 研究のモチベーション：推論量の反転
5. 研究のモチベーション：出力から内部状態へ
6. 先行研究：Shojaee et al. (2025)
7. 先行研究：Zhu et al. (2026)
8. 先行研究：Carson (2025)
9. 仮説
10. 現状の共有：Hanoi実験の設計
11. 現状の共有：HanoiのN–T相図
12. 現状の共有：Pancake Sortingの実験設計
13. 現状の共有：Nとmin_movesによる難易度分解
14. 展望

## 表記・レイアウト

- 章タイトルは目次の文言を基準とし、詳細はコロン以降へ記載。
- 横バー位置はスライド2・3の `y=1.146 inch` に統一。
- 日本語フォントは `Meiryo UI`。
- 本文は原則として体言止め。
- 論文由来の主張には原図または公式ページ画像を使用。

## 図の出典

- Shojaee et al. (2025), *The Illusion of Thinking*, Figures 6 and 7, arXiv:2506.06941v3, CC BY 4.0
- Zhu et al. (2026), *Dissecting Failure Dynamics in LLM Reasoning*, Figure 2, ACL Anthology
- Carson (2025), *A Statistical Physics of Language Model Reasoning*, official ICML page
- `figures/hanoi_nt_collapse/hanoi_nt_collapse_deepseek-r1-distill-qwen-14b.{png,csv}`
- `docs/research_state/results_summary.md`

## 再生成

リポジトリルートから実行。

```bash
python3 docs/presentations/2026-08-24_hanoi_to_hidden_dynamics/source/build_deck.py
```

必要パッケージは `python-pptx` と `Pillow`。
