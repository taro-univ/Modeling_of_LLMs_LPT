# Pancake hidden-state軌道解析 — 2026-08-27夜間実行

## 一言でいうと

成功finalのaligned cosine中央値は、6/6条件でrandom reasoning nullの99%点を上回った。したがって、最終回答時に再現性の高い領域を通る `finalization corridor` は複数条件で検討に値する。一方、final直前にleave-one-trial-out corridor距離が低下したのは1/6条件であり、一様な吸引過程やattractorまでは支持しない。全条件共有PCAは50成分でも累積74.9%で、90%へ未到達だった。 PC1–3の図だけで高次元構造全体を代表させず、最大50成分の距離・類似度を併記する。

## 対象

- Drive上の `N=3,4,5 × min_moves=3,4,5` を9マスとして確認した。
- 実在する6条件を各100 trial、合計600 trial解析した。
- `N3/mm4`, `N3/mm5`, `N4/mm5` はデータ欠損ではなく、その最短距離の状態が存在しない空セルである。
- 元の48層hiddenは1 cellずつ取得し、layer 48だけを派生cacheへ縮約・再検証してからlocal原本を削除した。

![全条件の概要](../../results/pancake_2026-08-27_overnight/figures/01_dataset_overview.png)

| condition | trials | success | median tokens | Flip entropy | PC1–3 | PC≤50 |
| --- | --- | --- | --- | --- | --- | --- |
| N3_mm3 | 100 | 100% | 1072 | 0.97 | 38.0% | 75.4% |
| N4_mm3 | 100 | 86% | 2132 | 0.94 | 38.2% | 76.0% |
| N4_mm4 | 100 | 92% | 2300 | 0.97 | 39.2% | 76.8% |
| N5_mm3 | 100 | 76% | 3490 | 0.86 | 38.3% | 75.8% |
| N5_mm4 | 100 | 38% | 6662 | 0.94 | 38.1% | 75.8% |
| N5_mm5 | 100 | 38% | 5444 | 0.96 | 38.6% | 75.9% |

## PCAをどう読んだか

各trialから同数の32時点を時間全体から等間隔に取り、長い生成だけがPCA基底を支配しないようにした。条件内PCAに加え、全条件、同一N、同一min_movesごとに共有PCAを別々にfitした。最大50成分まで計算し、累積説明分散90%へ届かなければ未達と明記した。大規模行列にはrandomized PCAを用いた。

![PCA説明分散](../../results/pancake_2026-08-27_overnight/figures/02_pca_explained_variance.png)

| basis | cells | PC1–3 | PC1–50 | selected | 90% |
| --- | --- | --- | --- | --- | --- |
| cell_N3_mm3 | N3_mm3 | 38.0% | 75.4% | 50 | not reached |
| cell_N4_mm3 | N4_mm3 | 38.2% | 76.0% | 50 | not reached |
| cell_N4_mm4 | N4_mm4 | 39.2% | 76.8% | 50 | not reached |
| cell_N5_mm3 | N5_mm3 | 38.3% | 75.8% | 50 | not reached |
| cell_N5_mm4 | N5_mm4 | 38.1% | 75.8% | 50 | not reached |
| cell_N5_mm5 | N5_mm5 | 38.6% | 75.9% | 50 | not reached |
| global | N3_mm3;N4_mm3;N4_mm4;N5_mm3;N5_mm4;N5_mm5 | 38.1% | 74.9% | 50 | not reached |
| shared_N4 | N4_mm3;N4_mm4 | 38.6% | 76.1% | 50 | not reached |
| shared_N5 | N5_mm3;N5_mm4;N5_mm5 | 38.3% | 75.4% | 50 | not reached |
| shared_mm3 | N3_mm3;N4_mm3;N5_mm3 | 37.9% | 74.7% | 50 | not reached |
| shared_mm4 | N4_mm4;N5_mm4 | 38.5% | 75.7% | 50 | not reached |

PC1–3は見るための地図であり、距離・Fréchet・CKAは比較用基底の選択成分すべてを使った。

![条件内PC1–3](../../results/pancake_2026-08-27_overnight/figures/03_within_condition_pc123.png)

![全条件共有PC1–3](../../results/pancake_2026-08-27_overnight/figures/04_global_shared_pc123.png)

## 「軌道が一致する」をどう確認したか

1. 既存notebookを踏襲し、同じ長さのfinal blockをrelative rowで揃え、元の5120次元でaligned mean cosineを計算した。
2. 別trialのrandom reasoning windowを同じ長さで5000組作り、final同士の値がnullのどこに位置するか確認した。
3. 長さが違う曲線には、点の順序を保ったまま比較できる離散Fréchet距離を使った。
4. 同じ長さの代表曲線ではlinear CKAも補助的に示した。長さが違う比較は無理にCKAへ揃えず欠測とした。
5. 成功finalをleave-one-trial-out参照軌道にし、final前256 tokenでその領域への距離が下がるか確認した。

![final類似度](../../results/pancake_2026-08-27_overnight/figures/05_final_similarity_heatmaps.png)

| condition | cohort | final cosine | null 99% | distance drop |
| --- | --- | --- | --- | --- |
| N3_mm3 | success_final | 0.934 | 0.470 | -0.072 |
| N4_mm3 | success_final | 0.915 | 0.480 | -0.003 |
| N4_mm4 | success_final | 0.917 | 0.466 | -0.016 |
| N5_mm3 | success_final | 0.903 | 0.492 | +0.003 |
| N5_mm4 | success_final | 0.897 | 0.468 | -0.002 |
| N5_mm5 | success_final | 0.900 | 0.456 | -0.038 |

`distance drop` が正ならfinal直前に近づき、負なら少なくともこの定義では近づいていない。

![corridorへの接近](../../results/pancake_2026-08-27_overnight/figures/06_corridor_approach.png)

![finalとreasoning null](../../results/pancake_2026-08-27_overnight/figures/07_final_vs_reasoning_null.png)

## N・min_moves・探索複雑度との比較

複雑度は次を分けた。

- 全状態数: `N!`、情報量は `log2(N!)` bit。
- 1手の選択肢: `N-1`。
- 最短手数ぶんの名目的手順数: `(N-1)^min_moves`。
- その距離殻に実在する状態数: dataset生成時の厳密BFS値。
- 経験的生成エントロピー: debug中にLLMが生成した `Flip k` のShannon entropy。モデルlogitが保存されていないため、token-level predictive entropyとは呼ばない。
- 訪問状態entropyとrepeated-state比率: debug replayから算出。

6条件しかないため、相関は傾向の可視化であり検定的な結論には使わない。

![複雑度との関係](../../results/pancake_2026-08-27_overnight/figures/08_complexity_relationships.png)

![同一N・同一mm比較](../../results/pancake_2026-08-27_overnight/figures/09_group_specific_similarity.png)

## 解釈

成功finalのaligned cosine中央値は、6/6条件でrandom reasoning nullの99%点を上回った。したがって、最終回答時に再現性の高い領域を通る `finalization corridor` は複数条件で検討に値する。一方、final直前にleave-one-trial-out corridor距離が低下したのは1/6条件であり、一様な吸引過程やattractorまでは支持しない。全条件共有PCAは50成分でも累積74.9%で、90%へ未到達だった。 PC1–3の図だけで高次元構造全体を代表させず、最大50成分の距離・類似度を併記する。

安全な表現は「成功finalで共通corridorが再現する可能性がある」である。「attractor」「復元力」「必ずfinal前から吸い寄せられる」とはまだ言わない。

## 留意事項

- 主解析はlayer 48。全48層比較ではない。
- PCA fitは全trialを等重みで含む時間標本を使った。全tokenは派生top-layer cacheに保持され、代表全軌道、全final、debug event、corridor接近の計算に使った。
- aligned cosineは同じ長さのfinalだけ比較できる。異長比較はFréchetへ分けた。
- finalタグ、定型文、共通Flip語彙の寄与は完全には除けていない。random reasoning nullは長さを統制するが、token列を厳密には一致させていない。
- CKAは対応する時間点がある場合の補助指標。異長軌道を見かけ上合わせるための補間はしていない。
- 出力先は `results/pancake` の所有権が別ユーザーで書込不可だったため、`results/pancake_2026-08-27_overnight/` に置いた。

## 再現物

- 清書済みnotebook: `notebooks/pancake/pca_trajectory_analysis_2026-08-27.ipynb`
- 集計表: `results/pancake_2026-08-27_overnight/tables/`
- PCA基底: `results/pancake_2026-08-27_overnight/pca/`
- layer 48派生cache: `results/pancake_2026-08-27_overnight/derived/top_layer/`
- 実行script: `results/pancake_2026-08-27_overnight/scripts/`

## 参考文献

- Shannon, *A Mathematical Theory of Communication* (1948): [entropyとlogarithmic information](https://people.math.harvard.edu/~ctm/home/text/others/shannon/entropy/entropy.pdf)
- Gates & Papadimitriou, *Bounds for Sorting by Prefix Reversal* (1979): [prefix reversalによるPancake Sorting](https://doi.org/10.1016/0012-365X(79)90068-2)
- Eiter & Mannila, *Computing Discrete Fréchet Distance* (1994): [順序を保つ曲線距離](https://www.kr.tuwien.ac.at/staff/eiter/et-archive/files/cdtr9464.pdf)
- Kornblith et al., *Similarity of Neural Network Representations Revisited* (2019): [CKAによる表現類似度](https://arxiv.org/abs/1905.00414)
- Halko, Martinsson & Tropp, *Finding Structure with Randomness* (2011): [randomized low-rank decomposition](https://doi.org/10.1137/090771806)
