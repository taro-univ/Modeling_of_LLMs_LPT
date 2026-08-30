# 修正版スライド 08・09・13

元の14枚資料を変更せず、差し替え対象の8・9・13枚目だけを独立したPowerPointとして作成する。

## 出力

```text
output/slides_08_09_13_revision_2026-08-25.pptx
```

PowerPoint内の並びは元資料の8、9、13ページ。フッターのページ番号も `08`、`09`、`13` を維持する。

## 修正内容

- 8ページ相当: *Hidden Markov Modeling of Reasoning Dynamics in Large Language Models*への差し替え。
- 9ページ相当: Carsonの枠をHHMM論文の「成功・失敗軌道の早期分岐」へ変更。
- 13ページ相当: Google Drive上の600 trialsから集計したfinal accuracyへ変更。

## 600 trialsのaccuracy

accuracyは `labels_v1.json` の `observable_flags.final_reached_goal`、および
`outcome == success_final` の一致を確認して集計した。

| N | min_moves | success / trials | accuracy |
|---:|---:|---:|---:|
| 3 | 3 | 100 / 100 | 1.00 |
| 4 | 3 | 86 / 100 | 0.86 |
| 4 | 4 | 92 / 100 | 0.92 |
| 5 | 3 | 76 / 100 | 0.76 |
| 5 | 4 | 38 / 100 | 0.38 |
| 5 | 5 | 38 / 100 | 0.38 |

取得元:

```text
pancake-drive:LLM_LPT/full_hidden_distribution_v1
```

集計値は `data/pancake_accuracy_600.csv`、作図結果は
`figures/pancake_accuracy_600_heatmap.png` に保存する。Driveから取得した個別ラベルは
一時領域だけで扱い、リポジトリには保存しない。

## 再生成

リポジトリルートから実行。

```bash
python3 docs/presentations/2026-08-25_slides_08_09_13_revision/source/build_slides.py
```
