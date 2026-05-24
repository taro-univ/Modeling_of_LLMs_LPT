# TODO

優先度付きタスクリスト。優先度は P0（即着手）→ P1 → P2 の順。

研究方針に関わる判断（仮説、パズル選定、モデリング案採否、解析手法選定）は**必ず user に確認**してから着手する。手段（コーディング、論文選定）は委任。

最終目標：**2026-06-30 モデリング完了** → **2026-07 中間報告**（ハミルトニアン + シミュレーション成功）

---

## P0：進行中・即着手

### ✅ SPEC-2026-05-22-001（P(q) moments ベース相分類器）— 実験完了

- [x] physics-agent レビュー（Section 2）条件付き合格・全条件解消
- [x] research-agent レビュー（Section 3）R1〜R4 完了
- [x] implementation-agent 設計案（Section 4）完了
- [x] **GATE A**：壁打ち終了宣言 → specs/final/ へ移動（2026-05-22）
- [x] **GATE B**：final 仕様書目視確認 → Codex 起動（2026-05-22）
- [x] Codex 実装（commit c876e42）→ quality-check → physics 事後確認
- [x] **GATE C**：pytest 22 passed + 検証レポート提示 → 実験GO（2026-05-22）
- [x] 初回実験：deepseek-r1-distill-qwen-7b 86 条件を分類（commit 1ba0cf2）
  - ORD=18 / SG=32 / PM=27 / TRN=9
  - Ordered→SG 境界：N=3 T≈0.8〜0.9、N≥4 は T_c < 0.1
  - SG→PM 境界：N=3〜6 で T≈1.3〜1.4（N 依存性が弱い）
- [ ] **多モデル展開**：14B / llama-8B / Qwen3-7B / Qwen3-14B で同スイープ実施
- [ ] **q_tail_mass の再決定**：多モデルデータ取得後に感度解析で再キャリブレーション
- [ ] **$T_c(N)$ スケーリング則の定量化**：Ordered→SG 境界を N の関数として fitting

### ✅ SPEC-2026-05-21-001（stagnation 診断）— 完了

- [x] `stagnation_diagnostic.py` 実装（commit d9d6fc5）
- [x] Algorithm E を `run_local.py` に移植（commit 083e173）
- [x] stagnation sweep 実行（deepseek-r1-distill-qwen-7b 分）
- [x] stagnation sweep 結果の解析・Q3 確定（2026-05-22, commit c11a682）
  - 出現率 2.2%（450試行中 10件）→ 主要終了機構ではない
  - PM 優勢ゾーンで多発 → **PM 寄りの補助シグナルに確定**（user 決定）
  - SPEC-2026-05-22-001 の `stagnation_after_move_rate` 扱いと整合確認済み

### 🔧 Codex CLI 統合 — 設定済み・未検証

- [x] `AGENTS.md` を実装エージェント専用に書き直し
- [x] `.codex/config.yaml` 作成（model: gpt-5.5, approval_policy: auto-edit）
- [x] `CLAUDE.md`・`docs/research_flow.md` に GATE A/B/C を明文化
- [ ] **Codex CLI の動作確認**（実際に `codex --task-file ...` が動くかテスト）
  - 小さな仕様書でドライランし、実行ログ・git diff を確認
  - エラーが出る場合は `.codex/config.yaml` を調整

---

## P0：データ収集アーキテクチャ

- [ ] **5 モデル横断スイープアーキテクチャの整備**
  - 対象：deepseek-r1-distill-qwen-14B / llama 8B / Qwen3 7B / Qwen3 14B
  - 各モデルに対し `runners/test_model_architecture.py` で事前検証
  - 既存の `run_full_sweep.sh` / `run_collapse_phase_sweep.sh` を多モデル化
- [ ] **多様なパズルの実装**（パズル候補の選定は user 確認事項）
  - 必須制約：**解が一意**
  - その他の軸（branching factor, 状態空間の連続性, ポテンシャル地形）は多様に
- [ ] **`envs/` への新パズル追加用の抽象基底の整備**（`BaseEnv` の拡張耐性チェック）

---

## P1：解析

- [ ] **SG 相判定基準の確立**（SPEC-2026-05-22-001 の実装待ち）
  - $P(q)$ moments と早期終了ラベル `move_loop_*` の関係を定量的に定式化
  - stagnation 診断結果を補助シグナルとして統合
- [ ] **モデリング案 1（3 状態ボルツマン）のフィッティング**
  - $T_{c1}, T_{c2}$ の定量化
  - `docs/Modeling_idea.md` の (E_O, E_SG, g_O, g_SG) を最小二乗で推定
- [ ] **$P(q)$ の系統的計算**（hidden state の試行間内積）
- [ ] **モデリング案 2（2 秩序変数 Landau）のフィッティング**（$P(q)$ 解析が整い次第）

---

## P2：モデリング → 中間報告

- [ ] **L2 隠れ状態の次元縮約方針の決定**（フィジックスエージェント検証後）
- [ ] **ハミルトニアン仮説の構築**（複数案を立てる）
- [ ] **複数モデル × 複数パズルのデータでフィッティング** → モデリング完了（**6/30 まで**）
- [ ] **制御外力シミュレーション**（H4 段階 1：秩序相が広がることを示す）
- [ ] **シミュレーション上の制御外力 ↔ 推論時駆動 の対応付け**（H4 段階 2）
- [ ] 中間報告ドキュメント執筆（**7 月中**）

---

---

## P1：Phase 2 移行準備（Hanoi 完了後）

方針詳細は `research_state/phase2_strategy.md`、パズル候補評価は `research_state/puzzle_roadmap.md` を参照。

### Phase 2 移行チェックリスト

- [ ] Tower of Hanoi × 5 モデル full_sweep 完了（llama-8B / qwen-14B / Qwen3-7B / Qwen3-14B）
- [ ] 5 モデル全ての P(q) 相図生成・比較（モデル間での AGS 構造の一致・差異）
- [ ] AGS 1987 読了
- [ ] arxiv:2503.23084 読了（"Reasoning-Memorization Interplay mediated by a single direction"）

### 新パズル実装（確定分）

- [ ] **Frog Jump（蛙跳び）** 実装（`envs/frog_jump_env.py`、一意解設計・`BaseEnv` 継承）
  - K(N) = N(N+2) の検証テスト含む
- [ ] **River Crossing（川渡り問題）** 実装（`envs/river_crossing_env.py`）
  - キャラクター数・ルール設計で一意解を保証

### 新パズル実装（候補・未確定）

パズル追加は `research_state/puzzle_roadmap.md` を参照して user が選定。

- [ ] Lights Out（両エージェント推薦、GF(2) 構造）
- [ ] 8-puzzle（physics-agent 推薦、universality class 確認）
- [ ] Pancake Sorting（一意解の設計方法を詰めてから）
- [ ] Tower of London（先行 LLM 研究との比較が必要な場合）

---

## 学習（並行）

- 西森「スピングラス理論と情報統計力学」読了
- 散逸構造の専門書（読み進め中）
- 「Hopfield is All You Need」精読
- **AGS 1987（Almeida, Thouless, Sommers）**：⭐ 最優先
- **arxiv:2503.23084**（Reasoning-Memorization Interplay）：⭐ 優先（H3 直結）
- Apple 推論崩壊論文の精読
- 「LLM × 統計力学」既存研究のリサーチエージェント主導サーベイ

---

## ✅ 完了済み

- [x] エージェントチーム構築（Hybrid Architecture: Claude Opus/Sonnet + Codex CLI）
  - CLAUDE.md・AGENTS.md・.codex/config.yaml・docs/research_flow.md 整備
  - GATE A / B / C による承認フロー確定（2026-05-22）
- [x] `stagnation_diagnostic.py` 実装・Algorithm E 移植（SPEC-2026-05-21-001, 2026-05-21）
- [x] 相図分類レビュー（`docs/phase_classification_review.md`）
- [x] 旧形式 results のアーカイブ化（`archive/results_legacy/`）
- [x] コード品質整備（Cyclomatic Complexity 9→2 削減）
- [x] deepseek-r1-distill-qwen-7B の 14B 実験
