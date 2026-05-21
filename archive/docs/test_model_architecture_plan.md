# test_model_architecture_plan.md

## 目的

`run_local.py` を複数モデルに対応させ、新モデルで実験を走らせる前に
アーキテクチャ・思考起動・出力フォーマット・hidden state 抽出の正しさを
系統的に検証する。

本ドキュメントは以下の 2 つを定義する。

1. **`run_local.py` に実装すべき共通変更**（実装対象と仕様）
2. **`test_model_architecture.py` のテスト仕様**（実装が正しいことを確認する手順）

---

## 対象モデル

| 識別子 | HuggingFace model_id | ベースアーキテクチャ | 想定層数 | hidden_size |
|---|---|---|---|---|
| `qwen7b` | `deepseek-ai/DeepSeek-R1-Distill-Qwen-7B` | Qwen2.5 | 28 | 3584 |
| `qwen14b` | `deepseek-ai/DeepSeek-R1-Distill-Qwen-14B` | Qwen2.5 | 48 | 5120 |
| `llama8b` | `deepseek-ai/DeepSeek-R1-Distill-Llama-8B` | Llama-3.1 | 32 | 4096 |
| `qwen3-8b` | `Qwen/Qwen3-8B` | Qwen3 | 36 | 4096 |
| `qwen3-14b` | `Qwen/Qwen3-14B` | Qwen3 | 40 | 5120 |

`想定層数` と `hidden_size` は T1 テストで実測値と照合する。

---

## 1. run_local.py への共通実装変更

### 変更 C1: CAPTURE_LAYERS の動的計算

**現状の問題**

```python
# runners/run_local.py:104–108（変更前）
CAPTURE_LAYERS: dict[str, int] = {
    "layer_m1":  -1,   # 最終出力層 (layer 28) ← 7B 固定コメント
    "layer_m8":  -8,   # 中間後半層 (layer 21)
    "layer_m16": -16,  # 中間層    (layer 13)
}
```

モデルの層数に依存したマジックナンバー。14B（48層）では `-16` が深さ 67% を指し、
7B（28層）の `-16`（深さ 46%）と比較不能になる。

**変更後の仕様**

モデルロード後に `model.config.num_hidden_layers` を読み、
**層の相対深度が一定**になるようインデックスを動的に決定する。

```python
def make_capture_layers(num_hidden_layers: int) -> dict[str, int]:
    """層数に依存しない深度比率でキャプチャ層を決定する。"""
    return {
        "layer_top":  -1,                             # 100% 深度（最終層）
        "layer_mid":  -(num_hidden_layers // 2),      #  50% 深度
        "layer_low":  -(num_hidden_layers * 3 // 4),  #  25% 深度
    }
```

モデルロード完了後に呼び出し、グローバル定数 `CAPTURE_LAYERS` を置き換える。

**検証ポイント（T1 で確認）**

- 各インデックスの絶対値が `num_hidden_layers + 1`（embedding 層込みの長さ）未満であること
- `hidden_states` タプルの参照がエラーなく行えること

---

### 変更 C2: 出力ディレクトリへのモデル名組み込み

**現状の問題**

```python
# runners/run_local.py:556（変更前）
base = args.output_dir or f"results/hanoi/results_N{args.N}_hf"
```

`--output-dir` を省略すると、モデルによらず同一パスに書き込まれ、
7B の結果が 14B に上書きされる。

**変更後の仕様**

`model_id` からスラッシュ・大文字を除去したスラグを生成してパスに含める。

```
results/hanoi/<model_slug>/N<N>/
例:
  results/hanoi/deepseek-r1-distill-qwen-7b/N4/
  results/hanoi/deepseek-r1-distill-qwen-14b/N4/
  results/hanoi/qwen3-8b/N4/
```

`meta.json` の `model` フィールドには元の `model_id` をそのまま記録する。

---

### 変更 C3: run_experiment_hf 内の model_id 参照修正

**現状の問題**

```python
# runners/run_local.py:398（変更前）
print(f"  Tower of Hanoi (HF)  N={N}  trials={trials}  model={MODEL_ID}")
```

グローバル定数 `MODEL_ID`（7B のデフォルト値）を参照しているため、
`--model-id` で別モデルを指定してもログに 7B が表示される。

**変更後の仕様**

`run_experiment_hf` に `model_id: str` 引数を追加し、`main()` から渡す。
`MODEL_ID` のグローバル定数は削除する。

---

### 変更 C4: ModelProfile による think 起動方式の抽象化

**現状の問題**

```python
# runners/run_local.py:220–221（変更前）
formatted += "<think>\n"   # DeepSeek-R1 専用のプリフィル
```

Qwen3 はチャットテンプレートに `enable_thinking=True` を渡すことで
thinking モードが有効になる（`<think>` プリフィルを追加すると動作が
未定義または破綻する可能性がある）。

**変更後の仕様**

`ModelProfile` データクラスを定義し、think 起動方式をモデルごとに切り替える。

```python
@dataclass
class ModelProfile:
    model_id:        str
    think_mode:      str   # "prefill" | "chat_template" | "none"
    think_open_tag:  str = "<think>"
    think_close_tag: str = "</think>"
```

| `think_mode` 値 | 動作 | 対象モデル |
|---|---|---|
| `"prefill"` | チャットテンプレート適用後に `<think>\n` を末尾追加（現状維持） | DeepSeek-R1-Distill-Qwen/Llama 系 |
| `"chat_template"` | `apply_chat_template(..., enable_thinking=True)` を使用し、プリフィルは追加しない | Qwen3 系 |
| `"none"` | thinking なし | 将来の比較実験用 |

`model_id` 文字列のプレフィックスマッチで自動選択する補助関数を実装する。

```python
def resolve_model_profile(model_id: str) -> ModelProfile:
    ...
```

`_estimate_reasoning_tokens` および早期終了 Algorithm A は
`think_open_tag` / `think_close_tag` を参照するよう修正する。

---

## 2. モデルごとに確認すべき事項

各モデルを初めて使う際に以下の項目をすべて手動で確認・記録する。
これらの実測値は `ModelProfile` の自動選択ロジックを書く根拠にもなる。

### 共通確認項目（全モデル）

| # | 確認事項 | 確認方法 |
|---|---|---|
| M-1 | `num_hidden_layers` の実測値 | `AutoConfig.from_pretrained` で取得 |
| M-2 | `hidden_size` の実測値 | 同上 |
| M-3 | `apply_chat_template` が system ロールを受け入れるか | トークナイザーでエラーなく実行 |
| M-4 | `<think>` / `</think>` タグが出力に現れるか | N=2, T=0.6, 1試行で確認 |
| M-5 | `_MOVE_RE_WITH_DISK` が最低 1 手をマッチするか | 同上の出力テキストに対して正規表現を適用 |
| M-6 | `output_hidden_states=True` でエラーが出ないか | モデル forward 1 ステップ実行 |

---

### DeepSeek-R1-Distill-Qwen-14B（`qwen14b`）

7B と同一の Qwen2.5 チャットテンプレートを使用するため基本動作は同一のはずだが、
層数・次元が異なる点を重点的に確認する。

| # | 確認事項 | 期待値 | 不一致時の対処 |
|---|---|---|---|
| Q14-1 | `num_hidden_layers` | 48 | `make_capture_layers` に正しい値が渡されるか確認 |
| Q14-2 | `hidden_size` | 5120 | npz の shape が `(num_moves, 5120)` か確認 |
| Q14-3 | `layer_low`（-36）が `hidden_states` タプルの範囲内か | OK（embedding 込みで 49 要素） | CAPTURE_LAYERS 生成ロジックの見直し |
| Q14-4 | VRAM 消費量（NF4 + N=4, T=0.6） | 12 GB 以下 | `num_predict` を下げる |

---

### DeepSeek-R1-Distill-Llama-8B（`llama8b`）

Llama-3.1 チャットテンプレートは Qwen とタグ構造が異なる（`<|start_header_id|>system<|end_header_id|>` 等）。
system ロールの通過を最優先で確認する。

| # | 確認事項 | 期待値 | 不一致時の対処 |
|---|---|---|---|
| L8-1 | `num_hidden_layers` | 32 | 同上 |
| L8-2 | `hidden_size` | 4096 | 同上 |
| L8-3 | `apply_chat_template` が system ロールをエラーなく処理するか | OK | Llama テンプレートは system を別タグで持つため `messages` 構造を調整 |
| L8-4 | `<think>` プリフィルで推論が正常に起動するか | `<think>` → `</think>` が出力される | `think_mode="prefill"` で問題なければ OK |
| L8-5 | few-shot の user/assistant ターンが正しく処理されるか | マルチターン形式で渡され、モデルが拒否しないか | Llama はロールストリクトな場合があるため 1 手で確認 |

---

### Qwen3-8B / Qwen3-14B（`qwen3-8b`, `qwen3-14b`）

think 起動方式が他とは異なる可能性が最も高いモデル。
`enable_thinking=True` の有無・効果を最優先で確認する。

| # | 確認事項 | 期待値 | 不一致時の対処 |
|---|---|---|---|
| Q3-1 | `apply_chat_template` が `enable_thinking` キーワードを受け入れるか | KeyError が出ない | tokenizer のバージョンを確認、`trust_remote_code=True` が必要か確認 |
| Q3-2 | `enable_thinking=True` なしで `<think>` プリフィルを使った場合の出力 | `<think>` が出力に現れるか | 現れない場合は `think_mode="chat_template"` に固定 |
| Q3-3 | `enable_thinking=True` で thinking が閉じるか（`</think>` が出力されるか） | YES | 閉じない場合は `think_budget` の閾値調整が必要 |
| Q3-4 | `num_hidden_layers` の実測値 | 8B: 36、14B: 40（推定） | 実測後に期待値を更新 |
| Q3-5 | `_estimate_reasoning_tokens` が正しく機能するか | `reasoning_tokens > 0` | think タグの書式が異なる場合は正規表現を修正 |

---

## 3. test_model_architecture.py の仕様

### 実行方法

```bash
# コンテナ内から実行
PYTHONPATH=/app python runners/test_model_architecture.py --model-id <model_id> [--no-gpu-tests]
```

`--no-gpu-tests` フラグで T0 のみ実行可能にする（モデルダウンロード前の事前確認用）。

### テスト構成と合否判定

| テストグループ | GPU 要否 | 概要 |
|---|---|---|
| **T0** | 不要 | 設定・tokenizer の事前確認 |
| **T1** | 必要 | モデルロードと CAPTURE_LAYERS 検証 |
| **T2** | 必要 | thinking 起動の検証（N=2, 1 試行） |
| **T3** | 必要 | 出力フォーマット検証（N=2, 1 試行） |
| **T4** | 必要 | hidden state 抽出の形状・健全性検証 |
| **T5** | 必要 | 機能的サニティチェック（N=2, 3 試行） |

各テストは PASS / FAIL / WARN の 3 段階で判定し、標準出力に結果を出力する。

- **PASS**: 期待値と一致
- **WARN**: 実験は進められるが注意が必要（例: VRAM が多め、など）
- **FAIL**: 実験実行前に修正必須

---

### T0: 設定確認（GPU 不要）

`AutoConfig.from_pretrained` と `AutoTokenizer.from_pretrained` のみ使用。

| テスト ID | 確認内容 | PASS 条件 | FAIL 時の意味 |
|---|---|---|---|
| T0-1 | `num_hidden_layers` を取得・表示 | 値が取得できる（実測値として記録） | 設定ファイルが壊れている |
| T0-2 | `hidden_size` を取得・表示 | 値が取得できる | 同上 |
| T0-3 | `tokenizer.chat_template` が存在するか | `chat_template is not None` | チャットテンプレートなし（プロンプト設計が必要） |
| T0-4 | system ロールを含む `messages` で `apply_chat_template` が通るか | エラーが出ない | system ロール非対応（`messages` 構造の変更が必要） |
| T0-5 | `apply_chat_template(..., enable_thinking=True)` が通るか | エラーが出ない → PASS / TypeError → WARN（`think_mode="prefill"` を使うべき） | — |

**T0 の出力例:**

```
[T0] 設定確認: deepseek-ai/DeepSeek-R1-Distill-Qwen-14B
  T0-1 PASS  num_hidden_layers = 48
  T0-2 PASS  hidden_size       = 5120
  T0-3 PASS  chat_template 存在
  T0-4 PASS  system ロール OK
  T0-5 WARN  enable_thinking 非対応 → think_mode="prefill" を使用
```

---

### T1: モデルロードと CAPTURE_LAYERS 検証

NF4 量子化でフルロードし、`make_capture_layers` の結果を検証する。

| テスト ID | 確認内容 | PASS 条件 |
|---|---|---|
| T1-1 | NF4 量子化ロードが完了するか | エラーなく完了 |
| T1-2 | `model.config.hidden_size` が T0-2 の値と一致するか | 一致 |
| T1-3 | `make_capture_layers(num_hidden_layers)` の各インデックスが hidden_states タプル長の範囲内か | `abs(idx) <= num_hidden_layers + 1`（embedding 込み）|
| T1-4 | VRAM 消費量が 12 GB 以下か | 12 GB 以下 → PASS、12〜14 GB → WARN、14 GB 超 → FAIL |

---

### T2: thinking 起動検証

N=2, temperature=0.6, 1 試行。`generate_with_hidden_states` を直接呼び出す。

| テスト ID | 確認内容 | PASS 条件 |
|---|---|---|
| T2-1 | 出力テキストに `<think>` が存在するか | あり |
| T2-2 | 出力テキストに `</think>` が存在するか（正常クローズ） | あり |
| T2-3 | `_estimate_reasoning_tokens` が 0 より大きいか | `reasoning_tokens > 0` |
| T2-4 | `think_open_tag` の前に実質的なコンテンツが出力されていないか（プリフィルの二重付与がないか） | `accumulated_text` が `<think>` から始まるか、または `<think>` より前が空白のみ |

---

### T3: 出力フォーマット検証

T2 と同一の試行結果を使って Move 抽出を検証する。

| テスト ID | 確認内容 | PASS 条件 |
|---|---|---|
| T3-1 | `_MOVE_RE_WITH_DISK` が 1 件以上マッチするか | マッチ数 ≥ 1 |
| T3-2 | 抽出した手の `src ≠ dst` か（自己ループ手がないか） | 全手で `src ≠ dst` |
| T3-3 | disk 番号が `1` 以上 `N` 以下か | 全手で `1 <= disk <= N` |
| T3-4 | `env.extract_moves_from_text` と `_MOVE_RE_WITH_DISK` のマッチ数が一致するか | 一致（パースの整合性確認） |

---

### T4: hidden state 抽出の形状・健全性検証

T2 と同一の試行で保存された `GenerationResult.hidden_states` を検証する。

| テスト ID | 確認内容 | PASS 条件 |
|---|---|---|
| T4-1 | `hidden_states` の各キーが `make_capture_layers` の出力キーと一致するか | 完全一致 |
| T4-2 | 各配列の shape が `(num_moves, hidden_size)` か | 一致（`hidden_size` は `model.config.hidden_size`）|
| T4-3 | NaN / Inf が含まれないか | `np.isfinite(arr).all()` が True |
| T4-4 | `move_texts` と `move_steps` の長さが `num_moves` と一致するか | 一致 |
| T4-5 | fallback パス（`__fallback__`）が誤って記録されていないか | `move_texts` に `"__fallback__"` が含まれない（N=2 では必ず 1 手以上出力されるはず） |

---

### T5: 機能的サニティチェック

N=2, 3 試行で低温・高温の定性的な傾向を確認する。
**数値的な閾値ではなく傾向の確認**であり、確率的ゆらぎを考慮した緩い基準とする。

| テスト ID | 確認内容 | PASS 条件 | 備考 |
|---|---|---|---|
| T5-1 | T=0.2 で 3 試行中 1 回以上正解するか | accuracy_sum ≥ 1 | N=2 は最も簡単なケース |
| T5-2 | T=0.2 での `early_stop` が `goal_reached` または `None` が多数か | `goal_reached` + `None` ≥ 2/3 | ループや no_move が多発する場合は設定に問題あり |
| T5-3 | `summary.json` と同等のフィールドが結果辞書に含まれるか | `accuracy`, `early_stop`, `num_moves`, `temperature`, `N` が全て存在する | DB 同期の前提条件 |

---

## 4. テスト実行フロー（新モデル追加時の手順）

```
1. T0 のみ実行（--no-gpu-tests）
       ↓ FAIL があれば ModelProfile の設定を修正してから続行
2. T1 実行（モデルロード）
       ↓ T1-4 WARN の場合は num_predict を下げるか N の上限を決める
3. T2–T4 実行（1 試行・N=2）
       ↓ T2 FAIL → think_mode の修正
       ↓ T3 FAIL → _MOVE_RE の修正または出力フォーマット確認
       ↓ T4 FAIL → make_capture_layers またはフォールバック処理の修正
4. T5 実行（3 試行・N=2）
       ↓ 全 PASS → 実験スイープ実行可
5. 実測した num_hidden_layers / hidden_size / think_mode を
   本ドキュメントの「対象モデル」表に追記して確定させる
```

---

## 5. ファイル配置

```
runners/
  run_local.py                  # 変更 C1–C4 を適用済みのメインスクリプト
  test_model_architecture.py    # 本仕様書に基づくテストスクリプト
docs/
  test_model_architecture_plan.md   # 本ドキュメント
```
