# Pancake token event series 仕様

作成日: 2026-07-28

目的: Pancake Sorting の token-level hidden trajectory に、後処理で token-wise event flags と puzzle state trace を結合し、PCA trajectory、成功軌道解析、将来の drift / diffusion / Fokker-Planck 解析へ接続できる時系列データ形式を固定する。

## 1. 位置づけ

この仕様は `docs/research_state/pancake_debug_hidden_join_spec.md` の具体化である。

runner は hidden `.npz` と最小 metadata を保存する。event labeling、phase labeling、PCA、drift / diffusion 推定は runner では行わず、`analysis/` 配下の後処理で行う。

最初の対象は次の hidden pilot とする。

```text
puzzle: pancake
N: 3
min_moves: 3
trials: 5
temperature: 0.6
num_predict: 8192
capture_timing: token:8
capture_mode: relative
layers: layer_low, layer_mid, layer_top
hidden_dtype: float16
```

## 2. 入力

1 run directory は `run_local.py` の出力を想定する。

```text
results/pancake/hidden_success_probe/<model_slug>/N3_mm3_T0_6/
  meta.json
  summary.json
  hidden/
    trial_001_hidden_token_8_relative_float16.npz
    trial_002_hidden_token_8_relative_float16.npz
    ...
```

必須入力:

```text
summary.json
hidden/*.npz
```

hidden `.npz` の必須キー:

```text
hidden
token_ids
token_positions
token_source
is_think_token
layer_ids
generated_text
move_steps
move_texts
capture_meta
```

`capture_meta` には time axis 解釈用に以下が入っていることを期待する。

```text
time_axis
row_index_unit
token_position_unit
prompt_stride
generated_stride
dt_token_source
hidden_token_alignment
generated_hidden_semantics
```

## 3. 出力

後処理スクリプトは hidden 本体をコピーせず、軽量 JSON を保存する。

推奨パス:

```text
results/analysis/pancake_hidden_events/<model_slug>/N3_mm3_T0_6/
  trial_001_events.json
  trial_002_events.json
  ...
```

スクリプト名:

```text
analysis/join_pancake_hidden_events.py
```

CLI 案:

```bash
python3 analysis/join_pancake_hidden_events.py \
  results/pancake/hidden_success_probe/deepseek-r1-distill-qwen-14b/N3_mm3_T0_6 \
  --out-dir results/analysis/pancake_hidden_events/deepseek-r1-distill-qwen-14b/N3_mm3_T0_6
```

## 4. 時間軸

`hidden` の第0軸を primary time axis とする。

```text
t_row          = hidden[t] の row index
token_position = prompt + generated を結合した元 token 系列上の位置
dt_token       = token_position[t+1] - token_position[t]
```

`token:8` と `token:4` の比較では、`t_row` を物理時間として扱わない。drift / diffusion 推定では `dt_token` を使い、1 token あたりの量へ正規化する。

```text
z_t      = PCA(hidden[t])
dz_t     = z_{t+1} - z_t
dt       = dt_token[t]
drift    = dz_t / dt
diffusion = dz_t dz_t^T / dt
```

prompt hidden は現状全 token 保存なので `dt_token=1` が主になる。主解析ではまず `is_generated=true` の token に限定して PCA fit / projection を行う。

## 5. token_series schema

出力 JSON の中心は `token_series` である。各配列は同じ長さ `T = hidden.shape[0]` を持つ。

```json
{
  "token_series": {
    "t_row": [0, 1, 2],
    "token_position": [0, 1, 256],
    "dt_token": [1, 255, null],
    "token_source": ["prompt", "prompt", "generated"],
    "token_id": [123, 456, 789],
    "flags": {
      "is_prompt": [true, true, false],
      "is_generated": [false, false, true],
      "is_think_token": [false, false, true],
      "is_move_event": [false, false, true],
      "is_final_region": [false, false, false],
      "is_after_final_start": [false, false, false],
      "is_after_first_goal": [false, false, false]
    },
    "move_index": [null, null, 0],
    "state_index": [0, 0, 1],
    "distance_to_goal": [3, 3, 2],
    "v": [1.0, 1.0, 0.666667],
    "phase_label": ["prompt", "prompt", "think"]
  }
}
```

`dt_token[-1]` は次点がないため `null` とする。

## 6. flag 定義

`is_prompt`: `token_source == "prompt"` の token。

`is_generated`: `token_source == "generated"` の token。

`is_think_token`: hidden `.npz` の `is_think_token` をそのまま使う。think 境界推定に失敗した場合は全 `false` になり得る。

`is_move_event`: その token 時点で新しい `Flip k` mention が完成した場合に `true`。基本的には hidden `.npz` の `move_steps` を `token_position` へ写像して立てる。

`is_final_region`: `<final>` から `</final>` までの submitted answer 区間内の token。境界の token mapping に失敗した場合は全 `false` とし、`boundary_ok=false` を記録する。

`is_after_final_start`: `<final>` 開始以降の token。`</final>` 後も含む。

`is_after_first_goal`: 全 move mention を順にシミュレートしたとき、初めて goal に到達した move event 以降の token。

## 7. state trace 定義

token ごとの puzzle state は「その token 時点までに完成した move mention を適用した状態」とする。

move が出ていない token では、直前の状態を hold する。

```text
state_index[t]       = token t 時点までに適用済みの move 数
distance_to_goal[t]  = state_index[t] の状態から goal までの exact BFS distance
v[t]                 = distance_to_goal[t] / min_moves
```

move event ごとには、別途 `events` に before / after / delta を保存する。

```json
{
  "name": "move_mention",
  "t_row": 120,
  "token_position": 1420,
  "move_index": 0,
  "move": "Flip 3",
  "state_before": [1, 3, 2],
  "state_after": [2, 3, 1],
  "distance_before": 3,
  "distance_after": 2,
  "delta_distance": -1
}
```

`delta_distance` の初期解釈:

```text
-1: progress
 0: neutral / redundant
+1: backtrack
goal 後の move: excess / force
```

探索フェーズ、迷いフェーズ、進めるフェーズ、戻るフェーズ、強引に進むフェーズは、この `delta_distance` と自然文文脈を使って後段で付ける。初期 join では固定しすぎない。

## 8. phase_label

初期実装の `phase_label` は粗い rule-based label に限定する。

優先順:

```text
prompt
final
post_goal
think
search
```

定義:

```text
prompt: is_prompt
final: is_final_region
post_goal: is_after_first_goal and not is_final_region
think: is_think_token
search: 上記以外の generated token
```

これは可視化用の初期補助 label であり、論文用の failure mode label とは分ける。

## 9. join 検証

`summary.json` の trial 行と hidden `.npz` の `capture_meta` を照合する。

必須照合:

```text
puzzle
N
temperature
num_predict
trial
model_id
instance_id
initial_state
min_moves
```

欠けている項目がある場合は、照合可能な項目だけで判定し、出力 JSON に `join_warnings` を残す。

出力 JSON の top-level fields:

```json
{
  "schema_version": 1,
  "join_ok": true,
  "join_warnings": [],
  "boundary_ok": true,
  "summary_json": ".../summary.json",
  "hidden_npz": ".../hidden/trial_001_hidden_token_8_relative_float16.npz"
}
```

## 10. sample seed

再現性のため、hidden pilot では `instance_seed` と `sample_seed` を分ける。

```text
instance_seed: 問題インスタンス生成または固定初期状態の識別 seed
sample_seed: 生成 sampling の乱数 seed
```

`run_local.py` の metadata には最終的に以下を保存する。

```json
{
  "instance_id": "N3_seed1_mm3",
  "instance_seed": 1,
  "sample_seed": 1
}
```

`--sample-seed` が実装されるまでは、`--seed` を暫定的に sample seed として使う運用を避け、hidden pilot 実行前に CLI と metadata を分離する。

## 11. PCA への接続

PCA はこのスクリプトの責務ではない。別スクリプトで行う。

```text
analysis/fit_pancake_hidden_pca.py
analysis/project_pancake_hidden_pca.py
analysis/plot_pancake_hidden_trajectory.py
```

初期方針:

```text
1. is_generated=true の token に限定して PCA fit する。
2. layer_low / layer_mid / layer_top を別々に fit / project / plot する。
3. success N=3 の5 trial をまず同じ PCA 空間に重ねる。
4. move_event, final_start, first_goal を marker として重ねる。
5. concat layer PCA は、層別の挙動を確認した後に検討する。
```

## 12. 実装ステップ

1. `analysis/join_pancake_hidden_events.py` を作成する。
2. `summary.json` と hidden `.npz` の対応 trial を解決する。
3. `capture_meta` を parse し、join key を検証する。
4. `token_series.t_row`, `token_position`, `dt_token`, basic flags を作る。
5. `move_steps` / `move_texts` を token event に写像する。
6. `PancakeSortingEnv` で state trace / distance / v を再計算する。
7. `<final>` 境界を best-effort で token range に写像する。
8. `events.json` を保存する。
9. N=3 hidden pilot の5 trial で schema sanity check を行う。

## 13. 非目標

初期実装では以下を行わない。

```text
PCA fit / plot
drift / diffusion 推定
Fokker-Planck 方程式の推定
自然言語からの迷いフェーズ分類
LLM judge による event labeling
hidden 本体の再保存
```

