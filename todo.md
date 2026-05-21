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

### ⏳ SPEC-2026-05-21-001（stagnation 診断）— 実装済み・解析待ち

- [x] `stagnation_diagnostic.py` 実装（commit d9d6fc5）
- [x] Algorithm E を `run_local.py` に移植（commit 083e173）
- [x] stagnation sweep 実行（deepseek-r1-distill-qwen-7b 分）
- [ ] stagnation sweep 結果の解析・レポートまとめ
  - `results/hanoi/stagnation_sweep/deepseek-r1-distill-qwen-7b/` を読む
  - SG 寄り / PM 寄りの統計的傾向を SPEC-2026-05-21-001 に記録
  - SPEC-2026-05-22-001 の補助シグナルとして活用

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

## 学習（並行）

- 西森「スピングラス理論と情報統計力学」読了
- 散逸構造の専門書（読み進め中）
- 「Hopfield is All You Need」精読
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
