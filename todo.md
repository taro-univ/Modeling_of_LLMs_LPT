# TODO

優先度付きタスクリスト。優先度は P0（即着手）→ P1 → P2 の順。

研究方針に関わる判断（仮説、パズル選定、モデリング案採否、解析手法選定）は**必ず user に確認**してから着手する。手段（コーディング、論文選定）は委任。

最終目標：**2026-06-30 モデリング完了** → **2026-07 中間報告**（ハミルトニアン + シミュレーション成功）

対象モデル（4 モデル軸）：DeepSeek-7B / DeepSeek-14B / Qwen3-8B / Qwen3-14B  
llama-8B は補足扱い（スケーリング則分析から除外）。

---

## P0：実験実行中

- 🔄 **Qwen3-14B collapse_phase**（EXP-007）— 2026-06-05 開始。36セル × 25試行（N3-6, T1.1-3.0）

---

## P0：実験キュー（GPU 空き次第、順番に）

1. ~~**Qwen3-8B collapse_phase**~~ → 完了（EXP-005、36/36）
2. ~~**Qwen3-14B full_sweep**~~ → 完了（EXP-006、51/52、N6_T0_6 欠損）
2. **Lights Out × DeepSeek-7B sweep**（スクリプト整備済み）
   ```bash
   bash runners/scripts/run_lights_out_sweep.sh
   bash runners/scripts/run_lights_out_collapse_sweep.sh
   ```
3. **14B / N6_T0_8 補完**（クラッシュセルの再実行）

---

## P0：解析・実装（GPU 不要・即着手可）

- [x] **ゴールペグ・パリティ交絡の対処**（EXP-008 / SPEC-2026-06-05-001、2026-06-05）
  - [x] 全432セルを対称化 accuracy で再計算（`research_state/symmetric_accuracy.json`）
  - [x] env 対称化を Codex 実装（commit 9137c23、全43テスト pass、物理不変量検証済み）
  - [x] **補正済みデータで相図再生成**（`figures/phase_diagram_symmetric/`、全4モデル、2026-06-05）
  - [x] **観測4「$T_{c2}$ の N 非依存性」を対称化 accuracy で再フィット** → DeepSeek で確認・H5 証拠回復（`research_state/tc2_refit_symmetric.md`）
  - [x] **recitation order と reasoning-driven order の sub-classify**（D-3、2026-06-05、physics-agent 審査済み）
    - 判別子 tokens_per_move<15（move 列は一意ゆえ区別不能・計算量で分離）。相構造 reasoning→recitation→PM 確定。`research_state/subclass_d3.md`
  - [x] **L2 $P(q)$ で recitation basin の分離を検証** → PASS（2026-06-05）
    - recitation: 平均中心化 $q_\text{mean}=+0.53$（記憶 basin・$q_{EA}>0$）、reasoning/SG: $q\approx0$。`subclass_d3.md` の L2 検証節、`figures/recitation_order/<model>/pq_centered.png`
    - **H_eff への記憶 basin 組み込みゲート通過**。多井戸描像（full-B/C 縮退 + 高温記憶 basin）が L2 で裏付け
  - [ ] **H_eff（多井戸ハミルトニアン）の構築**：full-B/full-C 縮退基底 + 高温で顕在化する記憶 basin。reasoning/memorization の有効温度分離（高温記憶想起の符号問題 H-2）を理論側で詰める ★モデリング本体へ
  - [ ] **L2：full-B/full-C 経路の隠れ状態 overlap 検証**（二重井戸の縮退ペア確認、D-2）
- [ ] **SPEC-2026-05-22-001 の多モデル展開**（P(q) 分類器）
  - DeepSeek-14B（データあり）に対して実行
  - `q_tail_mass` の再キャリブレーションは全 4 モデルデータ揃い次第
- [ ] **Qwen3-8B collapse_phase 完了後の解析**
  - `run_pipeline.py` で相図 + P(q) 生成
- [ ] **Qwen3-8B full_sweep 解析**（全 N2-6 完了済み、相図の傾向確認）

---

## P1：解析

- [ ] **4 モデル横断 P(q) 比較**（DeepSeek 7B/14B + llama-8B の npz は揃っている）
- [ ] **モデリング案 1（3 状態ボルツマン）のフィッティング**
  - $T_{c1}, T_{c2}$ の定量化。`docs/Modeling_idea.md` の (E_O, E_SG, g_O, g_SG) を最小二乗推定
- [ ] **SPEC-2026-05-25-002（P(q) bimodality vs accuracy 予測能力）の実行**
  - physics-agent レビュー済み（draft）→ Track B で実行可能（詳細は SPEC-2026-05-25-002 Section 2.4 参照）
- [ ] **モデリング案 2（2 秩序変数 Landau）のフィッティング**（P(q) 解析後）

---

## P2：モデリング → 中間報告

- [ ] **L2 隠れ状態の次元縮約方針の決定**（physics-agent 検証後）
- [ ] **ハミルトニアン仮説の構築**（複数案を立てて比較）
- [ ] **複数モデル × 複数パズルのデータでフィッティング** → モデリング完了（**6/30 まで**）
- [ ] **制御外力シミュレーション**（H4 段階 1：秩序相が広がることを示す）
- [ ] **シミュレーション上の制御外力 ↔ 推論時駆動 の対応付け**（H4 段階 2）
- [ ] 中間報告ドキュメント執筆（**7 月中**）

---

## Phase 2 移行チェックリスト

- [ ] Tower of Hanoi × 4 モデル full_sweep 完了（Qwen3-8B 進行中、Qwen3-14B 未着手）
- [ ] 4 モデル全ての P(q) 相図生成・比較
- [ ] AGS 1987 読了（Amit, Gutfreund, Sompolinsky, Ann. Phys. 173, DOI: 10.1016/0003-4916(87)90092-3）
- [ ] arxiv:2503.23084 読了（"Reasoning-Memorization Interplay mediated by a single direction"）
- [x] **Lights Out 実装完了**（`envs/lights_out_env.py`、sweep スクリプト整備済み）
- [ ] Frog Jump 実装（`envs/frog_jump_env.py`、K(N)=N(N+2)、一意解設計）
- [ ] River Crossing 実装（`envs/river_crossing_env.py`）

---

## 文献（並行）

進捗詳細は `research_state/reading_log.md` を参照。

- **Spin-Glass Theory for Pedestrians**：参照用（読み進め中）
- **Dynamics of Glassy Systems（Cugliandolo）**：⭐ 次に読む（H5 / U10 直結）
- **AGS 1987（Amit, Gutfreund, Sompolinsky）**：⭐ 最優先（未着手）
- **arxiv:2503.23084**（Reasoning-Memorization Interplay）：読み始め中（H3 直結）
- **Apple GSM-Symbolic 論文**：読み始め中（H6 / 崩壊様式の比較）
- 西森「スピングラス理論と情報統計力学」：並行参照

---

## 補足モデル（スケーリング則分析から除外）

llama-8B は N≥3 で Ordered 相がほぼ存在せず、4 モデル軸のスケーリング則分析から除外済み。
「Ordered 相を持たないモデルの例」として補足資料に使用。

- ~~llama-8B collapse_phase N=6 T1.8~~ — 実行済みデータあり。解析は低優先度

---

## ✅ 完了済み

- [x] エージェントチーム構築（CLAUDE.md・AGENTS.md・GATE A/B/C フロー）
- [x] `stagnation_diagnostic.py` 実装・Algorithm E 移植（SPEC-2026-05-21-001）
- [x] 相図分類レビュー（`docs/phase_classification_review.md`）
- [x] 旧形式 results のアーカイブ化（`archive/results_legacy/`）
- [x] コード品質整備（Cyclomatic Complexity 9→2 削減）
- [x] SPEC-2026-05-22-001（P(q) 分類器）実装・deepseek-7b で実験完了
- [x] SPEC-2026-05-25-001（解析 OOP アーキテクチャ化）実装完了
- [x] EXP-002（ボルツマン直線性検定・Tc スケーリング）完了
- [x] EXP-003（llama-8B full_sweep + collapse_phase）ほぼ完了（N6 T1.8 残）
- [x] **Lights Out 環境実装**（`LightsOutEnv`、7 tests pass）
- [x] **run_local.py パズル横断対応**（`--puzzle`, `--seed`, `--no-loop-detection`）
- [x] **Lights Out sweep スクリプト整備**（`run_lights_out_sweep.sh`, `run_lights_out_collapse_sweep.sh`）
- [x] **4 モデル戦略確定**（DeepSeek-7B/14B + Qwen3-8B/14B、llama-8B は補足）
- [x] docs 整理・アーカイブ（Programming_Guide, log, 旧設計書）
- [x] **`/wrap-up` スラッシュコマンド実装・動作確認**（`.claude/commands/wrap-up.md`）
