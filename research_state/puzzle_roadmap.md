# パズルロードマップ（Puzzle Roadmap）

複数パズルによる普遍性検証の計画。パズル候補の選定根拠・評価・確定状況を管理する。

**最終目標**：異なる状態空間構造を持つ複数パズルで同様の (T, N) 相図を描き、Ordered/SG/PM 3相構造の**モデル普遍性**を示す。

---

## 確定済みパズル

### Tower of Hanoi（ハノイの塔）
- **状態空間**：Sierpinski ガスケット（2^N - 1 手の最短解）
- **K(N)**：$K(N) = 2^N - 1$（解析的）
- **一意解**：✅
- **EXP-001 結果**：N=2 Ordered / N=3 低T Ordered・高T SG / N=4-6 SG 支配 → AGS 相図と整合
- **status**：✅ スイープ実行中（5 モデル展開予定）

### Frog Jump（蛙跳び）
- **状態空間**：線形配置、一方向移動制約
- **K(N)**：$K(N) = N(N+2)$（N 匹ずつの場合）
- **一意解**：✅（解が一意に定まる設計）
- **物理的意味**：ToH と異なるグラフ位相 → universality class 比較の第一候補
- **status**：✅ **確定**（実装待ち）

### River Crossing（川渡り問題）
- **状態空間**：制約付き状態遷移グラフ
- **K(N)**：パズルサイズによって可変（設計で制御）
- **一意解**：✅（キャラクター数・ルール設計で制御可）
- **物理的意味**：branching factor が ToH より大きい → ポテンシャル地形の多様性
- **status**：✅ **確定**（実装待ち）

---

## 候補パズル（評価済み・未確定）

### Lights Out
- **状態空間**：GF(2) 線形代数。$5 \times 5$ で $2^{25}$ 状態
- **K(N)**：最小手数（線形代数で計算可能）
- **一意解**：✅（初期配置を選べば解が一意）
- **physics-agent 評価**：⭕ control 実験として有用。**フラストレーション構造がない**ため、SG 相が出れば LLM 固有の現象（外在的ではなく内在的 SG）として解釈できる
- **research-agent 評価**：⭕ GF(2) 構造 → REM / random code SG 理論と接続。LLM benchmark がほぼゼロで novelty 高い
- **両エージェント**：一致して推薦
- **status**：🟡 保留（Frog Jump / River Crossing 実装後に検討）

### 8-puzzle（スライドパズル）
- **状態空間**：$(3 \times 3)$ グリッド、181,440 状態
- **K(N)**：最適手数は BFS で計算可能
- **一意解**：✅
- **physics-agent 評価**：⭕ ToH と同じ universality class の確認実験として有用。H3 の普遍性を異なるパズルで再現
- **research-agent 評価**：（明示的評価なし）
- **status**：🟡 保留（普遍性クラス検証段階で候補）

### Pancake Sorting（パンケーキソート）
- **状態空間**：Cayley グラフ（ToH の Sierpinski と構造が異なる）
- **K(N)**：最小反転数（上界 $2N - 3$、下界不明）
- **一意解**：⚠️ **最短解が一意でない**場合が多い → 設計で制御する必要あり
- **physics-agent 評価**：⭕ AGS/REM/p-spin の判別に最も有用（新しい universality class）。ただし一意解問題がクリティカル
- **research-agent 評価**：（明示的評価なし）
- **status**：🟡 保留（一意解の設計方法を検討後）

### Tower of London
- **状態空間**：3本ペグ + 玉の移動。ToH より短い最適手数（1〜5手）
- **一意解**：✅（設計しやすい）
- **physics-agent 評価**：❌ ToH と同じ tree 状態空間 → 新しい universality class の証拠にならない。冗長
- **research-agent 評価**：⭕ Bárez et al. 2023 による LLM 評価先行研究あり。比較の足場になる
- **エージェント対立**：⚠️ 物理的新規性 vs. LLM 比較研究の足場
- **status**：🟡 保留（研究方針による。LLM 先行研究との比較を重視するなら採用）

---

## 非推薦（評価済み・除外）

| パズル | 除外理由 |
|---|---|
| **Cryptarithmetic** | 逐次的 dynamics がなく、SG / PM の動的遷移が観測しにくい |
| **Rush Hour** | 最小手数 K(N) が解析的に書けない → スケーリング則の検証不可 |

---

## 先行研究・参考論文

| 論文 | 関連パズル | 重要度 |
|---|---|---|
| Almeida, Thouless, Sommers 1987 (AGS) | 全般（相図の理論的基盤） | ⭐⭐⭐ 最優先読了 |
| Bárez et al. 2023 | Tower of London | LLM 評価の先行研究 |
| "Reasoning-Memorization Interplay mediated by a single direction" (arxiv:2503.23084) | 全般（H3 直接関連） | ⭐⭐⭐ **要読了**。hidden state の「推論方向」が Hopfield アトラクターに対応する可能性 |

---

## 実装優先順位（現時点）

```
Phase 1（進行中）   : Tower of Hanoi — 5 モデル展開
Phase 2（次）       : Frog Jump + River Crossing — 実装確定
Phase 3（候補検討） : Lights Out / 8-puzzle / Pancake Sorting から選定
Phase 4（任意）     : Tower of London（LLM 先行研究との比較が必要と判断した場合）
```

**選定方針**：相図の形状（Ordered/SG/PM 3 相構造）がパズル間で共通する場合 → H3 の普遍性支持。形状が異なる場合 → 新しい universality class として解析。好奇心ベースで選んでよい。
