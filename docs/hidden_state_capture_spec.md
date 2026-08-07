# Hidden State Capture 拡張仕様書

作成日: 2026-07-24

対象: `runners/run_local.py` の HuggingFace Transformers 版実験 runner

目的: LLM の推論生成過程を、パズル状態空間だけでなく token 時間方向の内部状態軌道として保存し、後続の PCA・move 同期・確率方程式・マクロ変数解析へ接続できるようにする。

## 1. 背景と設計方針

現状の runner は、モデルが `Move ...` または `Toggle ...` 形式の手を生成したタイミングで hidden state を保存する。これはパズル状態が1手進んだ観測点として有用だが、自己回帰生成の自然な時間ステップは token である。

したがって、支配方程式・マスター方程式・確率過程として LLM 推論を扱うためには、抽出タイミングを切り替えられる必要がある。

今回の基本方針は次の通り。

- runner は raw / near-raw な hidden trajectory と最小 metadata を保存する。
- drift, diffusion, overlap, PCA, phase classifier などの物理量は runner では計算しない。
- 物理量は `analysis/` 配下の後処理スクリプトで計算する。
- hidden 本体は DB に格納しない。DB は summary, metadata, artifact path の索引に限定する。
- 初期段階は `.npz` を使う。大規模化した段階で Zarr / HDF5 を検討する。

## 2. CLI 仕様

### 2.1 capture timing

`run_local.py` に `--capture-timing` を追加する。

指定可能値:

```text
move
token
token:<stride>
```

意味:

| 値 | 保存タイミング | 主用途 |
|---|---|---|
| `move` | 手が新しく検出された token step | パズル状態遷移、V(x)、既存解析との互換 |
| `token` | 生成された全 token | 確率過程、支配方程式、PCA の raw data |
| `token:8` | 8 token ごと | token 全保存の低容量近似 |

default は既存互換のため `move` とする。

`token:<stride>` の `<stride>` は正の整数とする。例: `token:1` は `token` と同義。

`think` 専用 capture mode は初回実装には含めない。think 境界の扱いは、保存対象の切替ではなく token ラベルとして実装する。理由は、モデルごとに `<think>` / `</think>` の decode 挙動が異なり、実験開始前に不安定な分岐を runner に入れないためである。

### 2.2 capture layers

`--capture-mode` は既に追加済み。

指定可能値:

```text
relative
all
```

意味:

| 値 | 保存層 |
|---|---|
| `relative` | 25%, 50%, 100% 深度の3点。既存互換 |
| `all` | embedding を除く全 Transformer 層通過後 |

`all` の層名は `layer_001`, `layer_002`, ..., `layer_NNN` とする。

### 2.3 hidden dtype

`--hidden-dtype` を追加する。

指定可能値:

```text
float16
float32
```

default は `float16` とする。

理由:

- token × all layers では `float32` が重すぎる。
- PCA や粗視化解析の初期検証では `float16` で十分な可能性が高い。
- 数値誤差検証が必要な場合のみ `float32` を使う。

### 2.4 保存圧縮

`--hidden-compression` を追加する。

指定可能値:

```text
none
npz_compressed
```

default は `npz_compressed` とする。

`none` は `np.savez`、`npz_compressed` は `np.savez_compressed` を使う。

## 3. 保存ディレクトリ仕様

token mode の hidden は summary と分けて `hidden/` 配下に保存する。

推奨ディレクトリ:

```text
results/
  <puzzle>/
    <sweep_type>/
      <model_slug>/
        N<N>_T<T>/
          meta.json
          summary.json
          hidden/
            trial_001_hidden_<timing>_<layers>_<dtype>.npz
            trial_002_hidden_<timing>_<layers>_<dtype>.npz
```

例:

```text
results/lights_out/token_probe/qwen3-14b/N3_T0_6/
  meta.json
  summary.json
  hidden/
    trial_001_hidden_token_all_float16.npz
```

既存の `--output-dir` 指定時も、hidden 本体は原則 `output_dir / "hidden"` に保存する。

## 4. `.npz` スキーマ

### 4.1 token 系 timing の標準スキーマ

`--capture-timing token`, `token:<stride>` では、layer ごとの別配列ではなく単一テンソルとして保存する。

必須キー:

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

各キーの仕様:

| key | dtype | shape | 内容 |
|---|---|---:|---|
| `hidden` | `float16` or `float32` | `[T, L, D]` | 保存対象 token ごとの全/選択層 hidden |
| `token_ids` | `int32` | `[T]` | 保存対象 token の token id |
| `token_positions` | `int32` | `[T]` | prompt + generated を結合した系列内の token position。0始まり |
| `token_source` | object/string | `[T]` | `prompt` または `generated` |
| `is_think_token` | `bool` | `[T]` | think 区間内と判定された token か |
| `layer_ids` | `int32` | `[L]` | hidden_states tuple 上の層 index。embedding は原則除外 |
| `generated_text` | object/string | scalar | 完成した生成テキスト |
| `move_steps` | `int32` | `[M]` | move/toggle が完成した token step |
| `move_texts` | object/string | `[M]` | 抽出された move/toggle 文字列 |
| `capture_meta` | object/string | scalar | JSON 文字列 |

`hidden[t, l, :]` は、`token_positions[t]` に対応する token の `layer_ids[l]` 層 hidden state を表す。

prompt token の hidden も保存対象に含める。容量は増えるが、prompt から generation への初期条件を後から再構成できることを優先する。

prompt token の hidden は、prefill forward で得られる `outputs.hidden_states[layer_idx][0, prompt_position, :]` を保存する。generated token の hidden は、各 step の `outputs.hidden_states[layer_idx][0, -1, :]` を保存し、その hidden から sample された `next_token_id` と対応させる。

### 4.2 move timing の標準スキーマ

`--capture-timing move` でも、新スキーマ `hidden[M,L,D]` へ完全移行する。既存の `layer_low`, `layer_mid`, `layer_top` 互換キーは保存しない。

必須キー:

```text
hidden
layer_ids
move_steps
move_texts
capture_meta
generated_text
token_ids
```

この場合の `hidden` shape は `[M, L, D]` とする。

## 5. `capture_meta` 仕様

`capture_meta` は JSON 文字列として `.npz` 内に保存する。

必須フィールド:

```json
{
  "schema_version": 1,
  "capture_timing": "token",
  "capture_stride": 1,
  "capture_layers": "all",
  "hidden_dtype": "float16",
  "hidden_shape": [1024, 40, 5120],
  "model_id": "Qwen/Qwen3-14B",
  "model_slug": "qwen3-14b",
  "tokenizer_name": "Qwen/Qwen3-14B",
  "puzzle": "lights_out",
  "N": 3,
  "temperature": 0.6,
  "trial": 1,
  "num_predict": 1024,
  "early_stop": "goal_reached",
  "accuracy": 1
}
```

推奨フィールド:

```json
{
  "n_shot": 1,
  "repetition_penalty": 1.1,
  "seed": 42,
  "think_mode": "chat_template",
  "think_start_token": 0,
  "think_end_token": 512,
  "prompt_token_count": 256,
  "generated_token_count": 768,
  "file_format": "npz",
  "compression": "npz_compressed",
  "time_axis": "captured_token_rows",
  "row_index_unit": "hidden_row",
  "token_position_unit": "prompt_plus_generated_token_index",
  "prompt_stride": 1,
  "generated_stride": 8,
  "dt_token_source": "successive_token_positions_difference",
  "hidden_token_alignment": "hidden_row_i_matches_token_positions_i"
}
```

`capture_meta` は、`.npz` 単体を別ディレクトリへ移動しても解析条件が復元できることを目的にする。

`time_axis` 系 metadata は、`token:4` と `token:8` のように capture stride が異なる hidden trajectory を後処理で比較するために使う。
`hidden` の第0軸は常に保存された row index であり、物理的な token 時間差は `.npz` の `token_positions` の隣接差、または `generated_stride` から復元する。

## 6. runner 内部設計

### 6.1 capture timing parser

`parse_capture_timing(value: str)` を追加する。

返り値例:

```python
CaptureTiming(mode="move", stride=None)
CaptureTiming(mode="token", stride=1)
CaptureTiming(mode="token", stride=8)
```

不正値:

- `token:0`
- `token:-1`
- `token:abc`
- `think`
- 空文字

は `ValueError` または argparse error とする。

### 6.2 GenerationResult の拡張

現状の `GenerationResult.hidden_states: dict[str, np.ndarray]` は move timing には自然だが、token timing では扱いにくい。

拡張案:

```python
@dataclass
class GenerationResult:
    text: str
    total_tokens: int
    reasoning_tokens: int
    early_stop: Optional[str]
    hidden_states: dict[str, np.ndarray]
    hidden_tensor: Optional[np.ndarray]
    token_ids: np.ndarray
    token_positions: np.ndarray
    token_source: np.ndarray
    is_think_token: np.ndarray
    layer_ids: np.ndarray
    move_steps: np.ndarray
    move_texts: list[str]
    capture_meta: dict
```

段階的な実装簡略化のため、既存の `hidden_states` フィールドは一時的に残してもよい。ただし保存ファイルは新スキーマ `hidden[..., L, D]` に統一し、`layer_low`, `layer_mid`, `layer_top` 互換キーは出力しない。

token timing / move timing とも `hidden_tensor` を主データとする。

### 6.3 prompt + token capture の実装点

token timing では、まず prompt prefill 時の全 prompt token hidden を保存する。

prefill forward:

```python
outputs = model(input_ids=input_ids, use_cache=True, output_hidden_states=True)
```

保存対象:

```python
outputs.hidden_states[layer_idx][0, prompt_position, :]
```

その後、既存の生成 loop では各 step で:

```python
outputs = model(..., output_hidden_states=True)
next_token_id = sample(...)
```

を実行している。

token timing では、各 step の `outputs.hidden_states` から `capture_layers` 対象層の `outputs.hidden_states[layer_idx][0, -1, :]` を取り出し、CPU 側 buffer に保存する。

注意:

- generated token に対応する hidden は「次 token を sample する直前の context hidden」である。
- `token_ids[t]` はその hidden から sample された `next_token_id` と対応させる。
- したがって `hidden[t]` は `p(token_ids[t] | previous tokens)` の内部状態として解釈する。

prompt token と generated token は `token_source` で区別する。

### 6.4 think boundary labeling

`think` 専用 capture mode は初回実装しない。

ただし、think 開始・終了タイミングで遷移率が変わる可能性があるため、token ごとのラベル `is_think_token` と、`capture_meta.think_start_token`, `capture_meta.think_end_token` は保存する。

モデル profile ごとの注意:

- DeepSeek-R1-Distill 系: runner が `<think>\n` を prefill するため、生成開始直後から reasoning 区間とみなせる。
- Qwen3 系: `apply_chat_template(..., enable_thinking=True)` に依存する。出力テキスト内の `</think>` 検出を終了条件に使う。
- think close tag が検出されない場合は、生成終了または early stop までを think 区間とみなす。

初回実装では、think 境界検出に失敗しても実験を止めない。`think_start_token` / `think_end_token` を `null` にし、`is_think_token` を全 `False` または profile に基づく保守的推定にする。

## 7. 容量見積もり

概算式:

```text
size_bytes ≈ T × L × D × bytes_per_value
```

14B 級を `D=5120`, `L=40` とした場合:

| token数 T | fp16 | fp32 |
|---:|---:|---:|
| 1024 | 約0.42GB | 約0.84GB |
| 2048 | 約0.84GB | 約1.68GB |
| 4096 | 約1.68GB | 約3.36GB |
| 8192 | 約3.36GB | 約6.71GB |

48層モデルで `T=4096`, `D=5120` の場合:

```text
fp16: 約2.01GB / trial
fp32: 約4.03GB / trial
```

`np.savez_compressed` は連続値 hidden に対して劇的には効かない前提で見積もる。安全側には fp16 raw size の 0.7〜1.0 倍程度を想定する。

初期検証の推奨条件:

```text
puzzle: lights_out または hanoi
N: 3
trials: 2〜5
temperature: 0.2, 0.6, 1.0
capture_timing: token または token:8
capture_mode: all
hidden_dtype: float16
num_predict: 1024〜2048
```

## 8. DB 方針

hidden 本体は DB に入れない。

当面は `meta.json`, `summary.json`, `.npz` 内 `capture_meta` で管理する。

DB 拡張が必要になった段階で、次の `hidden_artifacts` テーブルを追加する。

```sql
CREATE TABLE IF NOT EXISTS hidden_artifacts (
    id                  SERIAL PRIMARY KEY,
    trial_id             INTEGER REFERENCES trials(id) ON DELETE CASCADE,
    path                TEXT NOT NULL,
    format              TEXT NOT NULL,
    capture_timing      TEXT NOT NULL,
    capture_stride      INTEGER,
    capture_layers      TEXT NOT NULL,
    hidden_dtype        TEXT NOT NULL,
    shape_json          JSONB,
    n_tokens_captured   INTEGER,
    n_layers_captured   INTEGER,
    hidden_size         INTEGER,
    file_size_bytes     BIGINT,
    compression         TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

解析結果は別テーブルに分ける。

```sql
CREATE TABLE IF NOT EXISTS analysis_artifacts (
    id                  SERIAL PRIMARY KEY,
    experiment_id        INTEGER REFERENCES experiments(id) ON DELETE CASCADE,
    trial_id             INTEGER REFERENCES trials(id) ON DELETE CASCADE,
    input_artifact_id    INTEGER REFERENCES hidden_artifacts(id) ON DELETE SET NULL,
    analysis_type        TEXT NOT NULL,
    path                TEXT,
    params_json          JSONB,
    metrics_json         JSONB,
    created_at           TIMESTAMPTZ DEFAULT NOW()
);
```

## 9. analysis 側との責務分離

runner では以下を計算しない。

- PCA
- drift field
- diffusion tensor
- cosine drift
- layer-wise contraction
- trial overlap `q`
- state-conditioned transition matrix
- early-stop-conditioned phase statistics

これらは `analysis/` 配下に別スクリプトとして実装する。

想定される後処理:

```text
raw hidden [T,L,D]
  -> token stride 再サンプリング
  -> move_steps による move 同期再サンプリング
  -> PCA / random projection
  -> Δh_t, drift, diffusion
  -> 成功/失敗/early_stop 別の統計
```

## 10. 実装順序

推奨する実装順序:

1. `--capture-timing` parser を追加する。
2. `--hidden-dtype` を追加する。
3. `--hidden-compression` を追加する。
4. prompt hidden + generated hidden を `hidden[T,L,D]` として保存する。
5. hidden 保存先を `output_dir / "hidden"` に分離する。
6. `capture_meta` を `.npz` に保存する。
7. move timing も `hidden[M,L,D]` の統一スキーマへ移行する。
8. small N / short token で smoke test を作る。
9. think boundary label を `is_think_token` / `think_start_token` / `think_end_token` として保存する。
10. 必要になった段階で DB に `hidden_artifacts` を追加する。
11. 大規模化した段階で Zarr / HDF5 へ移行する。

## 11. テスト仕様

最低限追加するテスト:

### 11.1 parser test

- `move` が `mode="move"` になる。
- `token` が `mode="token", stride=1` になる。
- `token:8` が `mode="token", stride=8` になる。
- `think`, `token:0`, `token:-1`, `token:abc` がエラーになる。

### 11.2 capture layer test

- `make_capture_layers(num_layers, mode="relative")` が既存3層を返す。
- `make_capture_layers(num_layers, mode="all")` が `layer_001` から `layer_NNN` を返す。

### 11.3 npz schema test

実モデルを使わない小さいダミー配列で保存関数をテストする。

- token mode の `.npz` に必須キーが存在する。
- `hidden.shape == (T, L, D)`。
- `hidden.dtype == np.float16`。
- `token_source` が `prompt` / `generated` を含む。
- `is_think_token.shape == (T,)`。
- `capture_meta` が JSON として parse できる。

### 11.4 smoke test

GPU / torch 利用可能環境でのみ実行する。

- `--capture-timing token:8 --capture-mode all --hidden-dtype float16 --num_predict 64 --trials 1`
- 保存された `.npz` の `hidden.shape[0] <= prompt_token_count + 64`。
- `layer_ids` が `capture_layers` と一致する。

## 12. 未確定事項・検討事項

### 12.1 token hidden の厳密な意味づけ

本仕様では `hidden[t]` を「`token_ids[t]` を sample する直前の hidden」と定義する。

別定義として「生成された token を入力した後の hidden」を保存する設計もあり得る。確率過程としては前者が自然だが、後処理で混同しないよう metadata に明記する必要がある。

### 12.2 prompt token 保存による容量増加

prompt token の hidden は保存する方針で確定。

容量増加は許容する。今後、prompt が長すぎて実験運用に支障が出る場合のみ、prompt hidden の stride / truncation オプションを検討する。

### 12.3 think 専用 capture mode

`--capture-timing think` は初回実装から外す。

理由は、DeepSeek-R1-Distill 系と Qwen3 系で think tag の扱いが異なり、`</think>` が special token として decode から消える場合もあり得るため。

ただし、think 開始・終了で遷移率が変わる可能性はあるため、token label として `is_think_token`, `think_start_token`, `think_end_token` は保存する。将来、境界検出が安定した段階で `--capture-timing think` を追加する。

### 12.4 `.npz` から Zarr / HDF5 への移行時期

初期検証は `.npz` でよい。

ただし、1 trial が数GBになり、部分読み込み・並列解析・クラッシュ耐性が必要になった段階で Zarr を優先検討する。

### 12.5 move timing の旧スキーマ

move timing も新スキーマ `hidden[M,L,D]` へ完全移行する方針で確定。

`layer_low`, `layer_mid`, `layer_top` の互換キーは保存しない。既存解析スクリプトが必要な場合は、新スキーマを読むように更新する。

### 12.6 DB 拡張の実施タイミング

現段階では `hidden_artifacts` テーブルは必須ではない。

token mode の実験数が増え、ファイル検索・重複管理・解析結果追跡が面倒になった段階で追加する。think 専用 capture mode と同様、将来拡張へ回す。

### 12.7 解析用マクロ変数の定義

次は後処理側で以下の候補を比較する。

- token 時間方向: `h_{t+1} - h_t`
- 層方向: `h_t^{l+1} - h_t^l`
- cosine drift
- PCA 後の低次元軌道
- move 同期後の coarse trajectory
- trial 間 overlap `q`
- early_stop 種類別の drift / diffusion

どれを主論文・主実験の観測量にするかは未確定。
