# Reading Log

論文・書籍の読書進捗を追跡する。report-bot が毎朝読み込む。

最終更新：2026-06-05

---

## 読書中

### Apple GSM-Symbolic 論文

- **タイトル**: "GSM-Symbolic: Understanding the Limitations of Mathematical Reasoning in Large Language Models"
- **関連仮説**: H6（モデル固有の崩壊様式）
- **状況**: 読み始めた（2026-05-28〜）
- **メモ**: 推論崩壊の現象論的記述。本研究の相図・SG 相との接続を考えながら読む

### arxiv:2503.23084 — Reasoning-Memorization Interplay（Hong 2025）

- **タイトル**: "The Reasoning-Memorization Interplay Is Mediated by a Single Direction"
- **著者**: Hong et al. (2025)
- **関連仮説**: H4（介入設計）、H6（モデル差異）、H7（inverse melting）
- **状況**: 内容確認済み（2026-06-05、research-agent 経由）
- **要点**:
  - 残差ストリームの**単一線形方向**（difference-in-means）で reasoning↔memory を分離
  - **中間層（layer_mid 相当）が最顕著**、介入で因果的に切替可能
  - 本研究の「layer_mid の $q_{EA}$ で記憶 basin が顕在化」と層位置まで一致
  - 温度・$q_{EA}$ などの物理量化はなし（＝本研究の novelty）
- **URL**: https://arxiv.org/abs/2503.23084

### スピングラス理論（Spin-Glass Theory for Pedestrians）

- **著者**: J. Aspelmeier ほか（LNP/review 系）
- **用途**: 理論の参考書として随時参照
- **状況**: 読み進め中（参照用）
- **メモ**: RSB・replica 計算・Parisi の形式論の導入として活用

---

## 次に読む（⭐ 最優先、2026-06-05 追加）

### Schupper-Shnerb 2004/2005 — inverse melting

- **タイトル**: "Spin Model for Inverse Melting and Inverse Glass Transition" / "Inverse melting and inverse freezing: a spin model"
- **著者**: Schupper & Shnerb
- **DOI**: 10.1103/PhysRevLett.93.037202 / 10.1103/PhysRevE.72.046107
- **arXiv**: cond-mat/0403674 / cond-mat/0502033
- **関連仮説**: H7（inverse melting 機構）
- **優先度**: ⭐⭐ 最優先
- **メモ**: 機構の核心「相互作用状態の縮退度 $\Omega$ が大きいと $TS$ 項で高温秩序化」。本研究の recitation 窓の理論的基盤。Schupper-Shnerb の縮退度パラメータを LLM 量に対応付けるために精読必須。完全版（PRE 2005）を読む。

### arXiv:2601.11061 — Spurious Rewards Paradox（RLVR Memorization）

- **著者**: 2026年
- **関連仮説**: H6（訓練方式差）、H7（inverse melting 機構の LLM 側根拠）
- **優先度**: ⭐ 高
- **メモ**: RLVR 訓練が中間層 L18-L20 の Anchor-Adapter 回路を通じて暗記モードへのトリガーを作る。Qwen（RL）vs DeepSeek（SFT）の recitation 差の直接的機構仮説。査読状況未確認。
- **URL**: https://arxiv.org/abs/2601.11061

---

## 積読・未着手（優先度順）

### Cugliandolo-Kurchan 1993 — off-equilibrium dynamics

- **タイトル**: "Analytical Solution of the Off-Equilibrium Dynamics of a Long-Range Spin-Glass Model"
- **著者**: Cugliandolo & Kurchan (1993)
- **関連論点**: U10（off-equilibrium dynamics の厳密解）、H5（非平衡 SG 理論）
- **優先度**: ⭐ 高（"Dynamics of Glassy Systems" の理論的基盤となる原著）
- **メモ**: FDT 破れ・実効温度の概念の出典

### Crisanti-Sommers — spherical p-spin model

- **タイトル**: "The Spherical p-spin Interaction Spin-Glass Model"
- **著者**: Crisanti & Sommers (1992/1993 系)
- **関連論点**: H5（p-spin モデルと SG 相転移の厳密解析）
- **優先度**: ⭐ 高（p-spin モデルの静的・動的性質の基礎）
- **メモ**: 1RSB 相転移・モード結合理論との対応。LLM の「温度誘起崩壊」の理論的類比として有望

### Dynamics of Glassy Systems — 次に読む

- **著者**: L. F. Cugliandolo
- **関連論点**: U10（Cugliandolo-Kurchan 1993 の off-equilibrium dynamics）、H5（非平衡SG理論）
- **優先度**: ⭐ 次読む
- **メモ**: Spin-Glass for Pedestrians の次に読む。Tc2 の N 非依存性の理論的基盤になりうる

### AGS 1987 — Amit, Gutfreund, Sompolinsky

- **タイトル**: "Statistical Mechanics of Neural Networks near Saturation", Ann. Phys. 173
- **DOI**: 10.1016/0003-4916(87)90092-3
- **関連仮説**: H3, H5（Hopfield 模型の統計力学、SG相の理論）
- **優先度**: ⭐ 最優先（todo.md 参照）
- **メモ**: AGS 相図の recall/SG/PM 構造の理論的出典。本研究の相図と比較するための基礎

### arXiv:2504.00509 — Recitation over Reasoning

- **タイトル**: "Recitation over Reasoning: How Cutting-Edge LMs Can Fail on Elementary Reasoning Problems"
- **関連仮説**: H6、H7（novelty 確認用）
- **優先度**: 中（novelty positioning に必要）
- **メモ**: 用語 "recitation over reasoning" の先行文献。RoR-Bench で変種への性能低下を測定。温度・$q_{EA}$ 等の物理量化はなし（本研究が novelty）。
- **URL**: https://arxiv.org/abs/2504.00509

### arXiv:2304.14964 — Dense Associative Memories（Lucibello-Mézard 2023）

- **タイトル**: "The Exponential Capacity of Dense Associative Memories"
- **関連仮説**: H7（$N=6$ で recitation 消失の容量上限）
- **優先度**: 中
- **メモ**: Dense AM は $P = \exp(\alpha N)$。N=6（63手）で recitation が消えることと容量限界の定量的対応付けに使用。系列容量（sequence capacity）版 arXiv:2601.00984 も参照。
- **URL**: https://arxiv.org/abs/2304.14964

### 西森「スピングラス理論と情報統計力学」

- **出版社**: 岩波書店
- **用途**: スピングラス・RSB の日本語教科書
- **優先度**: 並行参照
- **メモ**: 読み進め中と記録されていたが進捗未確認。AGS 読了後に改めて整理する

---

## 完了

（まだなし）
