# SPEC-2026-05-25-001 壁打ち Round 1

**日付**: 2026-05-25
**参加者**: implementation-agent, orchestration

---

## 確定事項

| 内容 | 根拠 |
|---|---|
| `PM_KEYS` を `("no_move_catchall", "move_ceiling")` に修正 | analyze_pq.py:113 / analyze_integrated.py:120 の実装に合わせる |
| `analyze_integrated.py` 廃止は 2 段階移行が必要 | `pq_metrics.py`・`pq_phase_classifier.py`・`stagnation_diagnostic.py` が直接 import |
| 共有ユーティリティを `analysis/io_utils.py` に切り出す | `_cosine`・`TS_ALL`・`TS_PQ`・生の `load_condition_raw` を共通モジュールへ |
| `ConditionData` に `sg_rate`, `ordered_rate`, `n_trials` を追加 | `pq_phase_classifier.py` 等の既存コードで参照されている |
| `--data-dirs` 複数対応は廃止（`--data-dir` 単一必須に変更） | 事実上 1dir で使われている。マージロジック除去で简略化 |
| `argparse` のデフォルト vs 明示指定の判定に `None` センチネルを使う | `parser.set_defaults()` では判定不可。`argparse.SUPPRESS` または `None` default を採用 |
| `compute_qea` は `analyze_pq.py` 版を採用（サブサンプリングなし） | `analyze_integrated.py` 版の `max_pairs_per_trial=300` はパフォーマンス最適化で物理的意味なし |

## 実装範囲の確定

**本 SPEC に含む（追加）**：
- `analysis/io_utils.py`（新規）: `_cosine`・`TS_ALL`・`TS_PQ` を格納
- `pq_metrics.py`・`pq_phase_classifier.py`・`stagnation_diagnostic.py` の import 先変更
- `analyze_integrated.py` → thin wrapper（削除ではなく io_utils + BaseAnalyzer へのラッパー）

**確認が必要な項目**：
- `_discover_sweep_dirs`（analyze_slowing.py の自動ディレクトリ検出）の扱い → ラッパーに残す or 廃止？

## 次のアクション

SPEC 更新 → GATE A（ユーザー確認）待ち

---

## 変更履歴

| 日付 | 変更内容 | 担当 |
|---|---|---|
| 2026-05-25 | Round 1 議事録作成 | orchestration |
