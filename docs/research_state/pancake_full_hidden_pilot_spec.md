# Pancake token:1 x all layers pilot 取得仕様

作成日: 2026-08-20

目的: Pancake Sorting の layer 方向の内部制約と、Move event 近傍の
token 方向 dynamics を識別できるかを検証するため、
`token:1 x all layers` full-hidden pilot の取得条件と Stop rule を固定する。

## 1. Question

```text
Q1. generated token ごとの全 Transformer layer hidden が欠損なく取得できるか。
Q2. Move mention 完了の前後を1 token単位で対応づけられるか。
Q3. c=(N, min_moves) を揃えた局所系と、同一初期状態の outcome 差を
    後続解析で比較できるデータになっているか。
```

この pilot で `F_l` / `G_l` の式自体は fit しない。まず観測契約と
試行間再現性を検証する。

## 2. 固定条件

```text
model_id: deepseek-ai/DeepSeek-R1-Distill-Qwen-14B
puzzle: pancake
temperature: 0.6
repetition_penalty: 1.1
n_shot: 0
num_predict: 4096
early_stop: disabled
capture_timing: token:1
capture_mode: all
hidden_dtype: float16
hidden_compression: npz_compressed
```

`num_predict=4096` は既存の N=3/N=4 debug run の EOS 到達長
（1049--3666 tokens）を収めつつ、1 trial の上限容量を抑えるために用いる。
4096 tokens で EOS まで到達しない trial は budget-censored として、
success/failure の代表軌道には採用しない。

## 3. hidden の観測契約

### 3.1 時間軸

runner は prompt hidden も保存するが、本 pilot の主解析は
`token_source == "generated"` の行だけを使う。prompt 先頭の大きな norm が
PCA、drift、layer 間差分を支配することを避ける。

generated 行 `h[t,l]` は、対応する `token_ids[t]` を sample する
直前の context state と解釈する。そのため Move mention が generated step
`s` で完了した場合の意味は次の通りとする。

```text
row s:     Move を完成させる token を sample する直前
row s + 1: 完成した Move mention を context に含む最初の hidden
```

event response は完了 step `s` の直後である `s+1` を基準に読む。
Move mention が複数 subword token からなるため、後続解析では完了点に
加えて span 開始点も保持する。

### 3.2 layer 軸

`capture_mode=all` で embedding を除く `layer_ids=1..num_hidden_layers` を保存する。
ただし HuggingFace model の `hidden_states` は、最終要素だけが最終 norm 後で
ある可能性がある。smoke で現行 `transformers` と model class の
forward 実装を確認し、各 `layer_ids` の capture point を記録する。

確認前は、特に最終差分 `h[t,L] - h[t,L-1]` を純粋な1 block update と
解釈しない。raw norm と正規化後差分を並べ、最終層の段差を診断する。

## 4. 比較 cell

| 役割 | N | min_moves | initial_state | 読みたい差 |
|---|---:|---:|---|---|
| success baseline | 3 | 3 | `[1, 3, 2]` | `c=(3,3)` 内の試行間変動 |
| mixed outcome | 4 | 3 | `[1, 2, 4, 3]` | 同一問題での sampling / outcome 差 |

N=4 では initial state を固定し、`sample_seed` だけを変える。
これにより N、min_moves、initial state 固有の紛らわしさを保ったまま、
`success_final` と `search_success_final_fail` の差を比較する。

N=3 と N=4 の比較では min_moves は揃うが、initial state と N が同時に
変わる。したがって、この2 cell だけから N の因果効果とは呼ばない。

## 5. 二段階の取得

### 5.1 P0: smoke

まず N=3 を1 trial だけ取得する。

```bash
python3 runners/pancake_hidden_sweep.py \
  --N 3 \
  --min-moves 3 \
  --initial-state 1,3,2 \
  --instance-id N3_mm3_full_hidden_smoke \
  --trials 1 \
  --sample-seed 1 \
  --temperature 0.6 \
  --num_predict 2048 \
  --capture-timing token \
  --capture-mode all \
  --hidden-dtype float16 \
  --no-early-stop \
  --output-root results/pancake/full_hidden_pilot_smoke \
  --event-output-root results/analysis/pancake_full_hidden_pilot_smoke
```

実行前に同じコマンドへ `--dry-run` を付け、初期状態、予算、
capture condition、出力先を確認する。

### 5.2 P1: N=4 sample-seed screening

N=4 はまず `token:8 x relative` で sampling seed を screen する。
生成条件は all-layer 再取得と揃える。

```bash
python3 runners/pancake_hidden_sweep.py \
  --N 4 \
  --min-moves 3 \
  --initial-state 1,2,4,3 \
  --instance-id N4_seed3_mm3_screen \
  --trials 10 \
  --sample-seed 1 \
  --temperature 0.6 \
  --num_predict 4096 \
  --capture-timing token:8 \
  --capture-mode relative \
  --hidden-dtype float16 \
  --no-early-stop \
  --output-root results/pancake/full_hidden_pilot_screen \
  --event-output-root results/analysis/pancake_full_hidden_pilot_screen
```

次の条件を満たす seed を最大各3本選ぶ。

- `success_final`
- `search_success_final_fail`
- `total_tokens < 4096`（budget-censored でない）
- join 完了、Move event 対応に致命的な警告がない

### 5.3 P2: selected seed の full-hidden 再取得

P1 で選んだ seed ごとに、同じ N、initial state、sampling 条件で
`token:1 x all` を1 trial ずつ取得する。output root は seed ごとに
分け、既存ファイルを上書きしない。

```bash
python3 runners/pancake_hidden_sweep.py \
  --N 4 \
  --min-moves 3 \
  --initial-state 1,2,4,3 \
  --instance-id N4_seed3_mm3_s<SELECTED_SAMPLE_SEED> \
  --trials 1 \
  --sample-seed <SELECTED_SAMPLE_SEED> \
  --temperature 0.6 \
  --num_predict 4096 \
  --capture-timing token \
  --capture-mode all \
  --hidden-dtype float16 \
  --no-early-stop \
  --output-root results/pancake/full_hidden_pilot \
  --event-output-root results/analysis/pancake_full_hidden_pilot
```

screen run と recapture run の `generated_text` SHA-256 が一致することを確認する。
一致しない場合は、sampling 以外の非決定性を切り分けるまで軌道比較に
採用しない。

N=3 baseline は sample seed 1--3 を候補とする。P0 が smoke success criteria を
満たし、かつ outcome が `success_final` だった場合だけ、その trial を seed 1 の
pilot data として数え、重複取得しない。計測系の合否とモデルの成否は
別々に判定する。

## 6. Smoke success criteria

- `hidden.shape == (T, 48, 5120)` で、全値が finite。
- `layer_ids == [1, 2, ..., 48]`。
- token:1 で `T == prompt_token_count + generated_token_count`。
- generated の `token_positions` が1刻みで、`token_ids` と同長。
- すべての `move_steps` が exact な generated row に対応する。
- `.npz` 単体の `capture_meta` に trial、initial state、min_moves、instance seed、
  sample seed、model、temperature、capture condition が残る。
- `summary.json` / NPZ / event JSON の join が `join_ok=true`。
- 実測の生成時間、NPZサイズ、peak RAM/VRAM を記録する。
- 生成末尾まで保存でき、容量不足または OOM がない。

`<final>` 境界は現行 join の比例的な文字位置推定を exact と扱わない。
main pilot で final commit 前後を主張に使う前に、runner で incremental decode 中の
`<final>` / `</final>` 完了 step を保存するか、tokenizer で厳密に再エンコード
する。これは smoke 時に方法を1つに決める。

## 7. Pilot success criteria

- N=3 `c=(3,3)` の `success_final` が3 trajectories 揃う。
- 同一 N=4 initial state で `success_final` と
  `search_success_final_fail` が各3 trajectories 揃う。
- 各 recapture で screen と generated text hash が一致する。
- Move completion と first post-event hidden を1 token単位で対応できる。
- 各層の norm、token drift、隣接 layer 差分を計算できる。
- 最終 norm の扱いを含む各 layer capture point の解釈が記録される。

## 8. Stop rule

- P0 smoke は1 trial で止める。失敗したら main pilot へ進まない。
- N=4 screening は最大10 sample seeds。目標 outcome が各3本集まらなくても
  追加実行せず、初期状態または設計を再検討する。
- all-layer 保存は N=3 success 3本、N=4 success 3本、
  N=4 final-fail 3本を上限とする。
- budget-censored、hash不一致、join失敗の trial を穴埋めするための追加実行は
  自動で行わない。原因を記録して一度止める。
- pilot 中に `F_l` / `G_l` の予測モデルを fit しない。
- PCA は健全性の可視化に限定し、主たる方程式推定に使わない。

## 9. Pilot 後の最小診断

各 trial で次だけを確認する。

1. layer ごとの hidden norm 分布と最終層の段差。
2. layer ごとの token drift `||h[t+1,l]-h[t,l]||`。
3. 隣接 layer 差分 `||h[t,l+1]-h[t,l]||`。
4. Move span の完了前後 `[-4,+8]` token window。
5. success/final-fail 内の試行間変動と、outcome 間差の大きさ。

この診断により、統計解析用 dataset で保存する代表 layer、event window、
必要試行数を決める。

## 10. Non-goals

- attention / MLP 出力の hook 実装
- KV cache の保存
- drift / diffusion の本推定
- one-step prediction と trial-level holdout
- N=5 への拡張
- activation steering
