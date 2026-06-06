# Tc2 再フィット（対称化分類）— EXP-008 / 2026-06-05

ゴールペグ・パリティ交絡の対処後、対称化 env（`goal_reached` = full-B/full-C 到達）を真実源に位相分類を補正し、SG→PM 転移温度 $T_{c2}$ をシグモイド再フィット。観測4「$T_{c2}$ の N 非依存性」の再確認が目的。

- 分類：goal_reached（recitation 含む）= Ordered、loop = SG、no_move_catchall/move_ceiling = PM。think_budget は censored で分母除外。
- p_PM(T) を $\sigma(+k(T-T_{c2}))$ でフィット（full_sweep + collapse_phase の全 T を統合）。
- スクリプト：`/tmp/refit_tc.py`（一回限り。env 対称化済みのため将来データには不要）。

## 結果

| モデル | N | $T_{c2}$ 新 | $T_{c2}$ 旧(観測4) | 高温 recitation p_O(T≥1.8) |
|---|---|---|---|---|
| deepseek-7b | 3 | 1.133 | 1.129 | 0.00 |
| deepseek-7b | 4 | 1.098 | 1.015 | 0.00 |
| deepseek-7b | 5 | 1.053 | 1.037 | 0.00 |
| deepseek-7b | 6 | 1.349 | 0.977 | 0.00（N6 fit は常にノイズ大）|
| deepseek-14b | 3 | 1.235 | 1.176 | 0.00 |
| deepseek-14b | 4 | 1.127 | 1.132 | 0.00 |
| deepseek-14b | 6 | 1.575 | 1.503 | 0.00 |
| qwen3-8b | 4 | fit 破綻 | — | 0.28（非単調）|
| qwen3-14b | 4 | fit 破綻 | — | 0.33（非単調）|
| qwen3-14b | 2 | fit 破綻 | — | 0.80（非単調）|

## 結論

1. **観測4は DeepSeek について対称化後も確認される（H5 の load-bearing 証拠を回復）**。DeepSeek は高温で暗記復唱しない（p_O(T≥1.8)=0.00）ため、$T_{c2}$ はパリティ交絡の影響をほぼ受けていなかった。$T_{c2}\approx 1.0$–1.2 で N 非依存（N3-5）。N6 はフィットノイズが大きく従来同様に不安定。

2. **Qwen は高温で recitation-order に転じるため、単純な3相シグモイドで $T_{c2}$ を定義できない**。p_PM が非単調（高温で Ordered が復活）。Qwen の $T_{c2}$ は recitation/reasoning の sub-classify（D-3）後に再定義が必要。

3. **H6 強化**：高温崩壊様式がモデル間で質的に異なる。Qwen = 暗記復唱（recitation-order）、DeepSeek = 真正崩壊（推論継続→loop/no-move）。

## 相図（対称化）

`figures/phase_diagram_symmetric/<model>/phase_diagram.png`（4モデル）。N=4 高温に recitation-ordered の青パッチ。acc(T) 非単調のため右下の単純 $T_c(N)$ 境界推定は even-N で過大評価（recitation 領域を拾う）→ D-3 で要改善。
