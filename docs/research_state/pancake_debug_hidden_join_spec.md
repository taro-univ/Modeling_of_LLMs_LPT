# Pancake debug JSON と hidden NPZ の結合仕様

作成日: 2026-07-28

目的: Pancake Sorting の debug sweep 結果と token-level hidden trajectory を結合し、PCA trajectory 図、event marker、outcome 別 drift/diffusion 推定へ進むための解析側契約を固定する。

## 1. 位置づけ

`debug.json` は puzzle state と outcome label の正本とする。

hidden `.npz` は token hidden trajectory の正本とする。

runner 側で PCA や drift/diffusion は計算しない。結合、phase labeling、PCA、図作成は `analysis/` 配下の後処理で行う。

## 2. 入力ファイル

1 trial は原則として同じ run directory に対応する。

```text
results/debug_prompt/pancake/<model_slug>/N<N>_seed<seed>_np<num_predict>_T<T_label>/
  debug.json
  generated.txt
  formatted_prompt.txt
  hidden/
    trial_hidden_token_<layers>_<dtype>.npz
```

初期実装では hidden ファイル名は固定しなくてよい。`hidden/*.npz` が1個だけならそれを読む。複数ある場合は CLI で明示する。

## 3. join key

結合は DB ではなくファイル単位で行う。

必須一致項目:

| debug.json | hidden capture_meta | 備考 |
|---|---|---|
| `puzzle` | `puzzle` | `pancake` 固定 |
| `N` | `N` | int |
| `seed` | `seed` | `null` 可だが pilot では必須推奨 |
| `model_id` | `model_id` | 完全一致 |
| `temperature` | `temperature` | float の丸め差に注意 |
| `num_predict` | `num_predict` | int |
| `generated_token_count` | `generated_token_count` | hidden 側に存在する場合のみ検証 |

`generated_text` は大きいので join key にはしない。ただし hash を保存できるなら、`generated_text_sha256` を `capture_meta` に追加して検証する。

## 4. debug.json から使う値

必須:

```text
puzzle
N
seed
model_id
temperature
num_predict
initial_state
goal_state
min_moves
generated_token_count
done_reason
generated_text
moves_final
moves_all_mentions
goal_reached_all_mentions
final_accuracy
state_trace
v_trace
first_goal_index
repeated_state_count
excess_after_goal
```

後処理で追加する標準 label:

| label | 定義 |
|---|---|
| `success_final` | `final_accuracy == 1` |
| `search_success_final_fail` | `final_accuracy == 0` かつ `goal_reached_all_mentions == true` |
| `no_final` | `moves_final` が空 |
| `length_stop` | `done_reason == "length"` |
| `loop_trap` | 暫定的に `repeated_state_ratio >= threshold` |
| `search_fail` | 上記以外の失敗 |

注意: `loop_trap` は現在のしきい値 0.3 だと N=3 成功例にも強く立つ。発表用の排他的 label ではなく、当面は補助フラグとして扱う。

## 5. hidden NPZ から使う値

`docs/hidden_state_capture_spec.md` の token timing 標準スキーマを前提にする。

必須:

```text
hidden              # [T, L, D]
token_ids           # [T]
token_positions     # [T]
token_source        # [T], "prompt" or "generated"
is_think_token      # [T]
layer_ids           # [L]
generated_text      # scalar string
move_steps          # [M]
move_texts          # [M]
capture_meta        # JSON string
```

`hidden[t]` は `token_ids[t]` を sample する直前の内部状態として解釈する。この定義は drift/diffusion 推定時に明示する。

## 6. event alignment

最初の実装で可視化する event:

| event | token index の決め方 |
|---|---|
| `move_mention_i` | hidden `.npz` の `move_steps[i]` |
| `first_goal` | `debug.json.first_goal_index` 番目の move mention に対応する `move_steps` |
| `final_start` | `generated_text` 内の `<final>` 開始位置を token offset に写像 |
| `final_end` | `</final>` 終了位置を token offset に写像 |
| `think_end` | `</think>` 終了位置、または `capture_meta.think_end_token` |
| `eos_or_length` | 最後の generated token |

文字位置から token 位置への写像は tokenizer が必要なので、初期実装では以下の優先順にする。

1. hidden `.npz` の `move_steps` を move event の正本にする。
2. `capture_meta.think_end_token` があれば think boundary に使う。
3. `<final>` 境界は後処理で tokenizer を使って推定し、推定不能なら `null` にする。

## 7. 中間成果物

結合後の軽量 JSON を run directory または `results/analysis/` に保存する。

推奨ファイル:

```text
results/analysis/pancake_hidden_events/<model_slug>/N<N>_seed<seed>_T<T_label>_events.json
```

スキーマ:

```json
{
  "schema_version": 1,
  "debug_json": ".../debug.json",
  "hidden_npz": ".../hidden/trial_hidden_token_all_float16.npz",
  "join_ok": true,
  "outcome_label": "success_final",
  "flags": {
    "loop_trap": true,
    "no_final": false,
    "length_stop": false
  },
  "problem": {
    "N": 4,
    "seed": 1,
    "temperature": 0.0,
    "initial_state": [2, 4, 1, 3],
    "goal_state": [1, 2, 3, 4],
    "min_moves": 4
  },
  "events": [
    {"name": "move_mention", "i": 0, "token_index": 120, "move": "Flip 2", "state_after": [4, 2, 1, 3], "v": 0.75},
    {"name": "first_goal", "token_index": 230, "move_index": 3},
    {"name": "final_start", "token_index": 1180},
    {"name": "final_end", "token_index": 1238}
  ]
}
```

## 8. 最初の解析スクリプト案

ファイル:

```text
analysis/join_pancake_hidden_events.py
```

CLI:

```bash
python3 analysis/join_pancake_hidden_events.py \
  results/debug_prompt/pancake/deepseek-r1-distill-qwen-14b \
  --run-dir-glob 'N*_seed*_np4096_T*' \
  --hidden-glob 'hidden/*.npz' \
  --out-dir results/analysis/pancake_hidden_events/deepseek-r1-distill-qwen-14b
```

責務:

- `debug.json` と hidden `.npz` の join key を検証する。
- outcome label と補助 flags を付ける。
- `move_steps` と `state_trace` / `v_trace` を結合する。
- PCA 前の event JSON を保存する。
- hidden 本体はコピーしない。

非責務:

- PCA fit/apply
- drift/diffusion 推定
- 図作成
- token hidden の再保存

## 9. PCA への接続

次のスクリプトは別に分ける。

```text
analysis/fit_pancake_hidden_pca.py
analysis/plot_pancake_hidden_trajectory.py
```

推奨順序:

1. N=3 success と N=4 mixed 条件から少数 trial を選ぶ。
2. 代表層または `layer_top` 相当を取り出す。
3. token stride を粗くして PCA basis を fit する。
4. 各 trial を PCA 空間へ project する。
5. event JSON の token index を marker として重ねる。

## 10. 未確定事項

- `<final>` 境界の token index 推定を tokenizer 再エンコードで十分とするか、runner 側で boundary token を保存するか。
- `loop_trap` を排他的 outcome label に含めるか、補助フラグに留めるか。
- hidden pilot を `debug_prompt.py` 系に寄せるか、`run_local.py` の正式 runner に寄せるか。
- full hidden pilot の保存単位を trial ごと `.npz` にするか、条件ごと bundle にするか。
