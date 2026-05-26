# TODO

優先度付きタスクリスト。優先度は P0（即着手）→ P1 → P2 の順。

研究方針に関わる判断（仮説、パズル選定、モデリング案採否、解析手法選定）は**必ず user に確認**してから着手する。手段（コーディング、論文選定）は委任。

最終目標：**2026-06-30 モデリング完了** → **2026-07 中間報告**（ハミルトニアン + シミュレーション成功）

対象モデル（4 モデル軸）：DeepSeek-7B / DeepSeek-14B / Qwen3-8B / Qwen3-14B  
llama-8B は補足扱い（スケーリング則分析から除外）。

---

## P0：実験実行中

- 🔄 **Qwen3-8B full_sweep** — N2-3 完了、N4 進行中（GPU 占有中）
- 🔄 **llama-8B collapse_phase N=6** — T1.1-1.5 完了、T1.8 進行中

---

## P0：実験キュー（GPU 空き次第、順番に）

1. **Qwen3-8B full_sweep 完了待ち** → 完了後に collapse_phase も実行
2. **Qwen3-14B full_sweep**（Qwen3-8B 完了後）
   ```bash
   bash runners/scripts/run_full_sweep.sh --models "Qwen/Qwen3-14B" --trials 25
   ```
3. **Lights Out × DeepSeek-7B sweep**（スクリプト整備済み）
   ```bash
   bash runners/scripts/run_lights_out_sweep.sh
   bash runners/scripts/run_lights_out_collapse_sweep.sh
   ```
4. **14B / N6_T0_8 補完**（クラッシュセルの再実行）

---

## P0：解析・実装（GPU 不要・即着手可）

- [ ] **SPEC-2026-05-22-001 の多モデル展開**（P(q) 分類器）
  - DeepSeek-14B / llama-8B（データあり）に対して実行
  - `q_tail_mass` の再キャリブレーションは全 4 モデルデータ揃い次第
- [ ] **llama-8B collapse_phase 解析の完成版**
  - N=6 T1.8 完了後に `run_pipeline.py` 再実行
- [ ] **Qwen3-8B N2-3 の初期解析**（現在のデータで相図の傾向確認）

---

## P1：解析

- [ ] **4 モデル横断 P(q) 比較**（DeepSeek 7B/14B + llama-8B の npz は揃っている）
- [ ] **モデリング案 1（3 状態ボルツマン）のフィッティング**
  - $T_{c1}, T_{c2}$ の定量化。`docs/Modeling_idea.md` の (E_O, E_SG, g_O, g_SG) を最小二乗推定
- [ ] **SPEC-2026-05-25-002（P(q) bimodality vs accuracy 予測能力）の実行**
  - physics-agent レビュー済み（draft）→ Track B で実行可能
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

## 学習（並行）

- 西森「スピングラス理論と情報統計力学」読了
- 散逸構造の専門書（読み進め中）
- **AGS 1987（Amit, Gutfreund, Sompolinsky）**：⭐ 最優先
- **arxiv:2503.23084**（Reasoning-Memorization Interplay）：⭐ 優先（H3 直結）
- Apple 推論崩壊論文の精読

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
