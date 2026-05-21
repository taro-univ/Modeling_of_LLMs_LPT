# test_model_architecture_runbook.md

新モデルを追加するときの検証手順・期待出力・トラブルシューティング、
および Docker 環境のセットアップをまとめたリファレンス。

---

## 1. 環境セットアップ

### 1-A. Docker Desktop を使う場合（通常の PC 作業時）

```bash
# Docker Desktop を起動してから WSL2 ターミナルで実行
docker compose up -d --build
docker compose exec hanoi-minimal bash
```

### 1-B. Docker Engine を WSL2 に直接インストール（SSH リモート作業・推奨）

Docker Desktop は GUI アプリのため SSH 接続中は起動できない。
以下の手順で Docker Engine を WSL2 内に直接インストールすると、
Docker Desktop 不要でリモートからそのまま動かせる。

```bash
# WSL2 内で一度だけ実行
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Docker サービスを起動（WSL2 は systemd が無効な場合がある）
sudo service docker start

# 動作確認
docker --version
docker compose version
```

WSL2 を再起動した場合はサービスの再起動が必要：

```bash
sudo service docker start
```

自動起動させたい場合は `~/.bashrc` または `~/.zshrc` に追記：

```bash
# WSL2 起動時に Docker サービスを自動起動
if service docker status 2>&1 | grep -q "not running"; then
    sudo service docker start > /dev/null 2>&1
fi
```

---

## 2. テスト実行コマンド

コンテナ内から実行する。`PYTHONPATH=/app` は設定済み。

```bash
# コンテナに入る
docker compose exec hanoi-minimal bash

# --- T0 のみ（GPU 不要・モデルダウンロード前の事前確認）---
PYTHONPATH=/app python3 runners/test_model_architecture.py \
    --model-id deepseek-ai/DeepSeek-R1-Distill-Qwen-14B \
    --no-gpu-tests

# --- 全テスト実行（GPU 必要）---
# DeepSeek-R1-Distill-Qwen-7B（デフォルト）
PYTHONPATH=/app python3 runners/test_model_architecture.py \
    --model-id deepseek-ai/DeepSeek-R1-Distill-Qwen-7B

# DeepSeek-R1-Distill-Qwen-14B
PYTHONPATH=/app python3 runners/test_model_architecture.py \
    --model-id deepseek-ai/DeepSeek-R1-Distill-Qwen-14B

# DeepSeek-R1-Distill-Llama-8B
PYTHONPATH=/app python3 runners/test_model_architecture.py \
    --model-id deepseek-ai/DeepSeek-R1-Distill-Llama-8B

# Qwen3-8B
PYTHONPATH=/app python3 runners/test_model_architecture.py \
    --model-id Qwen/Qwen3-8B

# Qwen3-14B
PYTHONPATH=/app python3 runners/test_model_architecture.py \
    --model-id Qwen/Qwen3-14B
```

---

## 3. 期待される出力の全体像

DeepSeek-R1-Distill-Qwen-7B を例にとった正常系の出力。

```
[INFO] model_id   = deepseek-ai/DeepSeek-R1-Distill-Qwen-7B
[INFO] think_mode = prefill

[T0] 設定確認: deepseek-ai/DeepSeek-R1-Distill-Qwen-7B
  ✓ T0-1 PASS  num_hidden_layers = 28
  ✓ T0-2 PASS  hidden_size       = 3584
  ✓ T0-3 PASS  chat_template 存在
  ✓ T0-4 PASS  system ロール OK
  △ T0-5 WARN  enable_thinking 非対応 → think_mode="prefill" を使用
[T0] --- WARN ---

[T1] モデルロード: deepseek-ai/DeepSeek-R1-Distill-Qwen-7B  device=cuda:0
  ✓ T1-1 PASS  NF4 量子化ロード完了
  ✓ T1-2 PASS  hidden_size = 3584（T0 と一致）
  ✓ T1-3 PASS  全インデックスが範囲内 (tuple_len=29): {'layer_top': -1, 'layer_mid': -14, 'layer_low': -21}
  ✓ T1-4 PASS  VRAM = 5.xx GB（< 12 GB）
[T1] --- PASS ---

[INFO] T2〜T4 用の共有試行を生成中（N=2, T=0.6, 1 試行）…

[T2] thinking 起動検証
  ✓ T2-1 PASS  <think> を確認
  ✓ T2-2 PASS  </think> を確認（正常クローズ）
  ✓ T2-3 PASS  reasoning_tokens = 312
  ✓ T2-4 PASS  プリフィル二重付与なし
[T2] --- PASS ---

[T3] 出力フォーマット検証
  ✓ T3-1 PASS  3 手を抽出
  ✓ T3-2 PASS  自己ループなし（全手で src ≠ dst）
  ✓ T3-3 PASS  全手のディスク番号が範囲内（1〜2）
  ✓ T3-4 PASS  パーサ件数一致（3 件）
[T3] --- PASS ---

[T4] hidden state 検証
  ✓ T4-1 PASS  キー一致: ['layer_low', 'layer_mid', 'layer_top']
  ✓ T4-2 PASS  全配列の shape = (3, 3584)
  ✓ T4-3 PASS  全配列に NaN / Inf なし
  ✓ T4-4 PASS  move_texts / move_steps / num_moves = 3 で一致
  ✓ T4-5 PASS  __fallback__ なし
[T4] --- PASS ---

[T5] 機能的サニティチェック（N=2, trials=3, T=0.2）
  ✓ T5-1 PASS  正解 2/3 試行
  ✓ T5-2 PASS  goal_reached / None = 3/3 試行
  ✓ T5-3 PASS  必須フィールド ['N', 'accuracy', 'early_stop', 'num_moves', 'temperature'] が全 3 試行に存在
[T5] --- PASS ---

============================================================
  TEST SUMMARY
============================================================
  PASS: 18  WARN: 1  FAIL: 0

  Overall: WARN
============================================================
```

終了コード `0`（WARN のみは成功扱い）、FAIL が 1 件でもあれば終了コード `1`。

---

## 4. 各モデルで注目すべき違い

| モデル | think_mode | T0-5 | num_hidden_layers | tuple_len | VRAM 目安 |
|---|---|---|---|---|---|
| DeepSeek-R1-Distill-Qwen-7B  | prefill       | WARN | 28 | 29 | ~5 GB  |
| DeepSeek-R1-Distill-Qwen-14B | prefill       | WARN | 48 | 49 | ~10 GB |
| DeepSeek-R1-Distill-Llama-8B | prefill       | WARN | 32 | 33 | ~6 GB  |
| Qwen3-8B                     | chat_template | PASS | 36 | 37 | ~6 GB  |
| Qwen3-14B                    | chat_template | PASS | 40 | 41 | ~10 GB |

**T0-5 の WARN（DeepSeek-R1 系）は正常**。`enable_thinking` 非対応のため `prefill` モードを使う設計であり、対処不要。

**Qwen3 系の T2-4** は `chat_template` モード固有の確認になる。出力が `<think>` から始まっていなければ WARN（`enable_thinking` が効いていない可能性）。

---

## 5. 問題が起きたときの読み方

| FAIL テスト | 意味 | 対処 |
|---|---|---|
| T0-4 | system ロール非対応 | `build_few_shot_messages` の messages 構造を調整、または system を user に統合 |
| T0-5 FAIL | `apply_chat_template` で予期しないエラー | tokenizer のバージョンを確認、`trust_remote_code=True` が必要か確認 |
| T1-1 | NF4 ロード失敗 | VRAM 不足、または bitsandbytes のバージョン不一致 |
| T1-3 | インデックス範囲外 | `make_capture_layers` の計算ロジックを確認（`layer_low` が embedding を含む tuple 長を超えている） |
| T1-4 WARN | VRAM 12〜14 GB | `--num_predict` を下げるか N の上限を設定して運用 |
| T1-4 FAIL | VRAM >= 14 GB | 実験実行前に対処必須。量子化設定を見直すか、より小さい N で試す |
| T2-1 / T2-2 | think タグが出ない | `think_mode` の選択を見直す。prefill → chat_template を試す |
| T2-3 | reasoning_tokens = 0 | think タグのパターンが期待と異なる。`ModelProfile` の `think_open_tag` / `think_close_tag` を確認 |
| T2-4 FAIL（prefill） | `<think>` が生成テキスト先頭に出現 | プリフィル二重付与。`apply_chat_template` の呼び出し前後を確認 |
| T2-4 WARN（chat_template） | `<think>` から出力が始まっていない | `enable_thinking=True` が効いていない可能性。tokenizer バージョンを確認 |
| T3-1 | Move が 0 件 | モデルが全く手を出力していない（常磁性相に相当）。T=0.6 で N=2 が無出力なら設定に問題 |
| T3-4 | パーサ件数不一致 | `_MOVE_RE_WITH_DISK` と `extract_moves_from_text` の間に実装差がある。正規表現を確認 |
| T4-2 | shape 不一致 | `capture_layers` のインデックスが hidden_states タプル外を指している（T1-3 と合わせて確認） |
| T4-3 | NaN / Inf あり | モデルの forward パスで数値爆発。量子化設定または `torch_dtype` を確認 |
| T4-5 | `__fallback__` あり | Move が 1 手も出なかった（T3-1 と同時に FAIL するはず）。常磁性相の可能性 |
| T5-1 FAIL | N=2・T=0.2 で 0 正解 | モデルが正常に動作していない可能性が高い。T2〜T4 の結果と合わせて確認 |
| T5-2 FAIL | ループ / no_move が多発 | think モードが正常に起動していないか、repetition_penalty が不適切 |
| T5-3 FAIL | 必須フィールド欠損 | `run_experiment_hf` の戻り値辞書に `N` / `temperature` / `num_moves` が含まれていない |

---

## 6. 新モデル追加時の推奨手順

```
1. --no-gpu-tests で T0 を実行
       ↓ T0-4 FAIL → messages 構造を修正
       ↓ T0-5 WARN → 正常（prefill モード使用）
       ↓ T0-5 PASS → Qwen3 系。chat_template モード確定

2. 全テストを実行（T1〜T5）
       ↓ T1-4 WARN → num_predict の上限を検討
       ↓ T2 FAIL  → think_mode を修正して再実行
       ↓ T3 FAIL  → 出力フォーマットを手動確認
       ↓ T4 FAIL  → make_capture_layers または fallback 処理を修正

3. 全 PASS（WARN は許容）になったら実験スイープを実行
       python3 runners/run_local.py --model-id <model_id> --N 4
```
