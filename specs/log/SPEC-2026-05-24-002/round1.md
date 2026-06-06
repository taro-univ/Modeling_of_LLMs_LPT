# SPEC-2026-05-24-002 壁打ち Round 1

**日付**: 2026-05-24  
**参加者**: physics-agent（SPEC-001 Round 2 転用）, implementation-agent, orchestration

---

## 確定事項

| 内容 | 根拠 |
|---|---|
| Algorithm C 不適用の理由を「involution のため SG シグナルとして無効」に更新 | SPEC-001 Round 2 physics-agent 審査 |
| import ブロックに TowerOfHanoiEnv・LightsOutEnv を追加（puzzle_factories のため必要） | impl-agent 指摘 |
| `run_experiment_hf` を案 B（`env: BaseEnv` を引数受け取り）に確定 | impl-agent 推奨。単一責任原則に合致 |
| `environment` フィールドと出力パス（`results/hanoi/` ハードコード）を本 SPEC に含める | impl-agent 指摘。DB sync 汚染防止のため |
| `build_few_shot_messages` の Lights Out 非対応を Known Limitation として明記 | impl-agent 指摘。別 SPEC で対応 |
| Lights Out 実験は `--n-shot 0` で few-shot 無効化して運用（暫定） | Known Limitation の対処 |

## 実装範囲の確定

**本 SPEC に含む**：
- `run_local.py` の型アノテーション変更・import 整理
- `run_experiment_hf` シグネチャ変更（env 外部化）
- `build_few_shot_messages` の `make_sub_env` 置換 + Known Limitation コメント
- `--puzzle` CLI 引数追加
- `environment` フィールドと出力パスの `args.puzzle` 参照化

**本 SPEC に含まない（別 SPEC）**：
- sweep スクリプト（`run_full_sweep.sh`）の `--puzzle` 対応
- `build_few_shot_messages` の Lights Out 専用プロンプト実装
- `--seed` 引数の追加（再現性のため将来対応）

## 次のアクション

user が「壁打ち終了 OK」を宣言次第、GATE A → specs/final/ 移動 → GATE B → Codex 実装

---

## 変更履歴

| 日付 | 変更内容 | 担当 |
|---|---|---|
| 2026-05-24 | Round 1 議事録作成 | orchestration |
