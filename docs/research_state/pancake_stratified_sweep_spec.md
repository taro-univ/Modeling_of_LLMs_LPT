# Pancake min_moves 層化スイープ仕様

作成日: 2026-07-28

目的: Pancake Sorting で `N`、初期状態、`min_moves`、token budget の効果が混ざることを避け、N=3-5 の難易度を層化して比較できる debug sweep / hidden capture の実行契約を固定する。

## 1. 背景

Pancake の `min_moves` は `N` と初期状態で決まる厳密な最短距離である。現在の初期状態生成は `goal_state` から `scramble_depth=N` 回 flip する方式だが、短縮経路が存在するため `min_moves=N` には固定されない。

現在の `seed` は主に問題インスタンス生成用であり、同じ `(N, seed)` は同じ `initial_state` と同じ `min_moves` を再現する。

```text
N + instance_seed -> initial_state -> min_moves
```

一方で、同じ問題を複数回 LLM に解かせるには、将来的に `instance_seed` と `sample_seed` を分ける必要がある。初期実装では既存の挙動に合わせ、候補表上の `seed` は `instance_seed` として扱う。

## 2. 実験上の問い

T はまず `0.6` に固定する。

比較したい効果:

- 同じ/近い `min_moves` で `N` を変える: stack 長、合法手候補数、状態表現の増大が、同程度の計画長でも失敗を増やすか。
- 同じ `N` 内で `min_moves` を変える: 計画長が失敗、loop、budget censoring をどれだけ増やすか。
- 同じ `N`・同じ/近い `min_moves` 内で初期状態を変える: 初期状態固有の failure dynamics を見る。

## 3. 必要な実装

### 3.1 候補表生成スクリプト

新規スクリプト:

```text
analysis/list_pancake_instances.py
```

責務:

- `N` と seed 範囲を受け取り、`PancakeSortingEnv(N=N, seed=seed)` を生成する。
- `initial_state`, `goal_state`, `min_moves`, `optimal_moves` を出力する。
- CSV と JSON の両方を書けるようにする。
- model loading はしない。

CLI 案:

```bash
python3 analysis/list_pancake_instances.py \
  --ns "3 4 5" \
  --seed-start 1 \
  --seed-end 100 \
  --csv-out results/debug_prompt/pancake/instances/pancake_instances_N3-5_seed1-100.csv \
  --json-out results/debug_prompt/pancake/instances/pancake_instances_N3-5_seed1-100.json
```

出力 CSV columns:

```text
N
seed
initial_state
goal_state
min_moves
optimal_moves
```

`initial_state`, `goal_state`, `optimal_moves` は JSON 文字列として保存する。

出力 JSON schema:

```json
{
  "schema_version": 1,
  "generator": "PancakeSortingEnv",
  "Ns": [3, 4, 5],
  "seed_start": 1,
  "seed_end": 100,
  "instances": [
    {
      "N": 5,
      "seed": 1,
      "initial_state": [1, 2, 5, 4, 3],
      "goal_state": [1, 2, 3, 4, 5],
      "min_moves": 3,
      "optimal_moves": ["Flip 5", "Flip 3", "Flip 5"]
    }
  ]
}
```

### 3.2 層化用 instances file

候補表から手で選んだ実行対象を、別 JSON に固定する。

推奨パス:

```text
configs/pancake_instances/
  N3-5_T0_6_minmoves_stratified_v1.json
```

schema:

```json
{
  "schema_version": 1,
  "description": "N=3-5 T=0.6 min_moves-stratified Pancake instances",
  "temperature": 0.6,
  "num_predict": 8192,
  "instances": [
    {
      "instance_id": "N5_seed1_mm3",
      "N": 5,
      "seed": 1,
      "initial_state": [1, 2, 5, 4, 3],
      "min_moves": 3,
      "notes": "existing exploratory seed"
    }
  ]
}
```

必須項目:

```text
instance_id
N
initial_state
min_moves
```

任意項目:

```text
seed
notes
temperature
num_predict
```

runner は `min_moves` を信用せず、`PancakeSortingEnv(N=N, initial_state=...)` から再計算して一致を検証する。一致しない場合はエラーで止める。

`instance_id` は出力ディレクトリ名に使うので、英数字、`_`, `-` のみにする。

### 3.3 pancake_debug_sweep.py の拡張

既存の seed sweep は残す。追加オプション:

```text
--instances-file PATH
```

挙動:

- `--instances-file` がない場合は現状通り `--ns`, `--temperatures`, `--trials`, `--seed-base` で走る。
- `--instances-file` がある場合は、ファイル内の `instances` を実行対象にする。
- temperature は優先順 `instance.temperature` > CLI `--temperatures` の各値 > file root `temperature`。
- num_predict は優先順 `instance.num_predict` > CLI `--num_predict` > file root `num_predict`。
- `trials` は初期実装では「instances の反復」には使わない。必要になったら `sample_seed` を導入する。

環境生成:

```python
PancakeSortingEnv(N=N, initial_state=tuple(initial_state))
```

出力ディレクトリ:

```text
results/debug_prompt/pancake/<model_slug>/<instance_id>_np<num_predict>_T<T_label>/
```

`debug.json` への追加項目:

```text
instance_id
instance_seed
requested_min_moves
```

既存の `seed` は後方互換のため残す。instances file に `seed` がある場合は同じ値を入れ、ない場合は `null` とする。

### 3.4 run_pancake_debug_stratified_sweep.sh

新規シェルスクリプト:

```text
runners/scripts/run_pancake_debug_stratified_sweep.sh
```

責務:

- `INSTANCES_FILE` を必須入力にする。
- model を1回だけ load するため、内部では `pancake_debug_sweep.py --instances-file ...` を呼ぶ。
- `NS`, `TRIALS`, `SEED_BASE` は使わない。

環境変数:

```text
MODEL_ID
INSTANCES_FILE
TEMPERATURES
NUM_PREDICT
DEVICE
N_SHOT
REPETITION_PENALTY
OUTPUT_ROOT
ANALYZE
DRY_RUN
```

実行例:

```bash
docker compose exec hanoi-minimal env \
  INSTANCES_FILE=configs/pancake_instances/N3-5_T0_6_minmoves_stratified_v1.json \
  TEMPERATURES=0.6 \
  NUM_PREDICT=8192 \
  bash runners/scripts/run_pancake_debug_stratified_sweep.sh
```

### 3.5 run_local.py の拡張

hidden capture で同じ初期状態を使うため、`run_local.py` に Pancake 専用の固定初期状態入力を追加する。

追加 CLI:

```text
--initial-state "1,2,5,4,3"
--instance-id N5_seed1_mm3
```

挙動:

- `--initial-state` は `--puzzle pancake` のみ許可する。
- `--seed` と `--initial-state` が両方ある場合、`initial_state` を優先し、`seed` は metadata 用の `instance_seed` として保存する。
- `summary.json` と hidden `capture_meta` に `initial_state`, `min_moves`, `instance_id`, `instance_seed` を保存する。

## 4. 最初の運用手順

### Step 1: 候補表を作る

```bash
docker compose exec hanoi-minimal python3 analysis/list_pancake_instances.py \
  --ns "3 4 5" \
  --seed-start 1 \
  --seed-end 100 \
  --csv-out results/debug_prompt/pancake/instances/pancake_instances_N3-5_seed1-100.csv \
  --json-out results/debug_prompt/pancake/instances/pancake_instances_N3-5_seed1-100.json
```

### Step 2: 層化 instances file を作る

目安:

```text
N=3: 代表 min_moves 層
N=4: min_moves=3, 4
N=5: min_moves=3, 5
```

最初は各層 2-3 instances で十分。N=5 8192 exploratory の結果を読んでから追加する。

### Step 3: debug stratified sweep を走らせる

```bash
docker compose exec hanoi-minimal env \
  INSTANCES_FILE=configs/pancake_instances/N3-5_T0_6_minmoves_stratified_v1.json \
  TEMPERATURES=0.6 \
  NUM_PREDICT=8192 \
  bash runners/scripts/run_pancake_debug_stratified_sweep.sh
```

### Step 4: hidden capture pilot

debug sweep で representative な success / failure / search_success_final_fail を選んで、`run_local.py --initial-state ... --instance-id ...` で token hidden を少数取得する。

## 5. 完了条件

この仕様の初期実装が完了したとみなす条件:

- `analysis/list_pancake_instances.py` で候補表を生成できる。
- `configs/pancake_instances/N3-5_T0_6_minmoves_stratified_v1.json` を読み、debug sweep が実行できる。
- 出力 directory 名が `instance_id` ベースになっている。
- `debug.json` に `instance_id`, `initial_state`, `min_moves`, `requested_min_moves` が保存される。
- `run_local.py --puzzle pancake --initial-state ...` で hidden capture が同一初期状態から実行できる。

## 6. 後回しにすること

- `sample_seed` による同一初期状態の複数 LLM sampling trial。
- min_moves を直接指定して runner 内で自動探索する機能。
- temperature sweep と min_moves 層化を同時に大規模化すること。
- DB schema への instance_id 追加。
