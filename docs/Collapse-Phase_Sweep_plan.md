# Collapse-Phase Sweep 実施計画

## 目的・位置づけ

`full_sweep`（T=0.2〜1.0）は秩序相〜相境界の相図描画を対象とする。
T≥1.0 の崩壊相は全 N で acc≈0 であり、相図には不要だが、その**内部構造**には物理的情報がある。

```
         T
  高 │  paramagnetic（PM）   ← q≈0 に集中、no_move 多発
     │
T_SG │- - - - - - - - -      ← この転移線を本実験で決定する
     │  spin glass（SG）     ← P(q) 双峰性、move_loop_repeat 多発
     │
  低 │  ordered              ← full_sweep の対象
       N=2   N=3   N=4   N=5
```

**この実験で明らかにすること:**

- $T_{SG \to PM}(N)$ の推定（SG 相と PM 相の境界温度）
- $T_{SG \to PM}$ が N によらず一定か（Idea 6 で予測する p-spin 普遍性の検証）
- 崩壊モード（`move_loop_repeat` vs `no_move_catchall`）の T 依存性
- P(q) 分布の形状変化（双峰性の消失点 = $T_{SG \to PM}$）

---

## 前提条件（実施前に完了していること）

- [ ] **Algorithm E の実装完了**: `stagnation_after_move` が `run.py` で有効になっていること
- [ ] **Algorithm D の閾値変更**: `no_move_ratio` が `0.50 → 0.25` に変更されていること
- [ ] `full_sweep` の N=3〜5 データが揃っており、秩序相での最初の手が 500 tok 以内に出ることを確認済み

> T≥1.0 は Algorithm E 未実装時に 1 試行あたり 200〜880s かかるケースが多発する。
> 30 trials × 9 温度点 × 3 N = 810 試行のうち数百試行が長時間化する恐れがあるため、
> **Algorithm E の実装なしに本実験を実施してはならない**。

---

## 実装検証テスト

Collapse-Phase Sweep の実施前に、Algorithm D（閾値変更）と Algorithm E（新規実装）が
正しく動作することを以下のテストで確認する。
**全テストが PASS になるまで本番実験を開始してはならない。**

テストはコンテナ内のプロジェクトルートで実行する。

```bash
docker compose exec hanoi-minimal bash
cd /app
python3 -m pytest tests/test_early_stop.py -v   # テストファイルを用意している場合
# または以下の各スニペットを python3 で直接実行する
```

---

### D-1: no_move_catchall — 閾値超過で発動する

`no_move_ratio=0.25`, `num_predict=4096` のとき、閾値は
`4096 × 0.25 × 3.5 = 3584 chars`。それを超えかつ手が 0 件なら発動する。

```python
from runners.run import check_early_stop, EarlyStopConfig

cfg = EarlyStopConfig(
    no_move_ratio=0.25,
    enable_think_budget=False, enable_move_ceiling=False, enable_move_loop=False,
)
# 3600 chars（閾値 3584 を超過）、手なし
text = "A" * 3600
result = check_early_stop(text, num_predict=4096, min_moves=7, cfg=cfg)
assert result == "no_move_catchall", f"FAIL: got {result}"
print("D-1 PASS")
```

---

### D-2: no_move_catchall — 閾値未満では発動しない

```python
from runners.run import check_early_stop, EarlyStopConfig

cfg = EarlyStopConfig(
    no_move_ratio=0.25,
    enable_think_budget=False, enable_move_ceiling=False, enable_move_loop=False,
)
# 3500 chars（閾値 3584 未満）、手なし
text = "A" * 3500
result = check_early_stop(text, num_predict=4096, min_moves=7, cfg=cfg)
assert result is None, f"FAIL: got {result}"
print("D-2 PASS")
```

---

### D-3: no_move_catchall — 手が 1 件でも存在すれば発動しない

閾値を超えていても `moves≥1` なら Algorithm D は発動しない
（Algorithm E の管轄になる）。

```python
from runners.run import check_early_stop, EarlyStopConfig

cfg = EarlyStopConfig(
    no_move_ratio=0.25,
    enable_think_budget=False, enable_move_ceiling=False, enable_move_loop=False,
)
# 閾値超過テキスト中に手が 1 件存在する
text = "A" * 3600 + "\nMove 1 from A to C\n"
result = check_early_stop(text, num_predict=4096, min_moves=7, cfg=cfg)
assert result is None, f"FAIL: got {result}"
print("D-3 PASS")
```

---

### D-4: no_move_catchall — 秩序相で誤発動しない

秩序相では最初の手が 500 tok 以内に出現する（実測値）。
500 tok ≈ 1750 chars であり、閾値 3584 chars を下回る。

```python
from runners.run import check_early_stop, EarlyStopConfig

cfg = EarlyStopConfig(
    no_move_ratio=0.25,
    enable_think_budget=False, enable_move_ceiling=False, enable_move_loop=False,
)
# 1750 chars の推論後に最初の手が出現するケース（秩序相の上限相当）
text = "thinking..." * 130 + "\nMove 1 from A to C\n"   # ≈ 1750 chars
result = check_early_stop(text, num_predict=4096, min_moves=7, cfg=cfg)
assert result is None, f"FAIL: got {result}"
print("D-4 PASS")
```

---

### D-5: 旧閾値（0.50）との差分確認

`no_move_ratio=0.50` のままなら 3600 chars では発動しないことを確認し、
変更の効果を数値で把握する。

```python
from runners.run import check_early_stop, EarlyStopConfig

cfg_old = EarlyStopConfig(
    no_move_ratio=0.50,
    enable_think_budget=False, enable_move_ceiling=False, enable_move_loop=False,
)
text = "A" * 3600
result = check_early_stop(text, num_predict=4096, min_moves=7, cfg=cfg_old)
assert result is None, f"FAIL: 旧閾値で誤発動 (got {result})"

cfg_new = EarlyStopConfig(
    no_move_ratio=0.25,
    enable_think_budget=False, enable_move_ceiling=False, enable_move_loop=False,
)
result = check_early_stop(text, num_predict=4096, min_moves=7, cfg=cfg_new)
assert result == "no_move_catchall", f"FAIL: 新閾値で未発動 (got {result})"
print("D-5 PASS  (旧=None, 新=no_move_catchall で差分が正しい)")
```

---

### E-1: stagnation_after_move — moves=1 後に停滞で発動する

`stagnation_ratio=0.20`, `num_predict=4096` のとき、閾値は `4096 × 0.20 = 819 tokens`。
`last_move_token_pos=100`, `current_token_pos=1000` → gap=900 > 819 で発動する。

Algorithm E はストリーミングループ側で管理するため、条件ロジックを関数として切り出して検証する。

```python
def check_stagnation(last_move_token_pos, current_token_pos,
                     num_predict=4096, stagnation_ratio=0.20):
    """Algorithm E の発動条件を単体で検証するヘルパー。"""
    if last_move_token_pos is None:
        return None
    gap = current_token_pos - last_move_token_pos
    if gap > num_predict * stagnation_ratio:
        return "stagnation_after_move"
    return None

result = check_stagnation(last_move_token_pos=100, current_token_pos=1000)
assert result == "stagnation_after_move", f"FAIL: got {result}"
print("E-1 PASS  (moves=1後, gap=900 > 819)")
```

---

### E-2: stagnation_after_move — moves=4 後に停滞で発動する（B3 ボトルネック）

`moves≥2` でも同じロジックで発動することを確認する。

```python
# 4手目が tok=300 で出て、その後 tok=1200 まで新しい手なし
result = check_stagnation(last_move_token_pos=300, current_token_pos=1200)
assert result == "stagnation_after_move", f"FAIL: got {result}"
print("E-2 PASS  (moves=4後, gap=900 > 819)")
```

---

### E-3: stagnation_after_move — 閾値未満では発動しない

```python
# last_move=800, current=1000 → gap=200 < 819
result = check_stagnation(last_move_token_pos=800, current_token_pos=1000)
assert result is None, f"FAIL: got {result}"
print("E-3 PASS  (gap=200 < 819, 発動しない)")
```

---

### E-4: stagnation_after_move — moves=0 では発動しない

`last_move_token_pos is None`（手が一度も出ていない）のとき、Algorithm E は
発動しない（その役割は Algorithm D が担う）。

```python
result = check_stagnation(last_move_token_pos=None, current_token_pos=2000)
assert result is None, f"FAIL: got {result}"
print("E-4 PASS  (moves=0, Eは非発動)")
```

---

### E-5: stagnation_after_move — 秩序相で誤発動しない

秩序相では全手が 1621 tok 以内に完成する（実測最大値）。
N=3 の最短手数 7 手が均等間隔で出る場合、手間隔は `1621 / 7 ≈ 231 tok` であり閾値 819 未満。

```python
# 最も間隔が大きいケース: 最後の手が tok=1400, 次の手はなく tok=1621 で終了
# gap = 1621 - 1400 = 221 < 819 → 発動しない
result = check_stagnation(last_move_token_pos=1400, current_token_pos=1621)
assert result is None, f"FAIL: 秩序相で誤発動 (got {result})"
print("E-5 PASS  (秩序相最終手後 gap=221 < 819)")
```

---

### E-6: Algorithm C（move_loop_repeat）との優先順位

SG 相でループが発生した場合、Algorithm C が先に発動し
Algorithm E は発動しないことを確認する。
`check_early_stop` 内で C が E より先に評価されることを静的に確認する。

```python
import inspect
from runners.run import check_early_stop

src = inspect.getsource(check_early_stop)
c_pos = src.find("move_loop_repeat")
# Algorithm E の発動コード（実装後）が check_early_stop に含まれる場合
e_pos = src.find("stagnation_after_move")

if e_pos == -1:
    print("E-6 SKIP  (Algorithm E は check_early_stop 外で実装されているため別途確認)")
else:
    assert c_pos < e_pos, "FAIL: Algorithm E が C より先に評価されている"
    print("E-6 PASS  (C が E より先に評価される)")
```

---

### テスト合格基準まとめ

| テスト ID | 内容 | 合格条件 |
|---|---|---|
| D-1 | 閾値超過・手なし | `"no_move_catchall"` |
| D-2 | 閾値未満・手なし | `None` |
| D-3 | 閾値超過・手あり | `None` |
| D-4 | 秩序相相当（1750 chars + 手）| `None` |
| D-5 | 旧旧閾値との差分 | 旧=`None`、新=`"no_move_catchall"` |
| E-1 | moves=1後 gap=900 | `"stagnation_after_move"` |
| E-2 | moves=4後 gap=900 | `"stagnation_after_move"` |
| E-3 | gap=200（閾値未満）| `None` |
| E-4 | moves=0（last_pos=None）| `None` |
| E-5 | 秩序相・gap=221 | `None` |
| E-6 | C が E より先に評価 | `c_pos < e_pos`（または SKIP）|

---

## パラメータ設計

| パラメータ | 値 | 根拠 |
|---|---|---|
| T | 1.0, 1.1, 1.2, 1.3, 1.5, 1.8, 2.0, 2.5, 3.0 | SG→PM 転移点（予測: T≈1.1〜1.3）を挟む細かいグリッド |
| N | 3, 4, 5 | N=2 は T=1.0 で既に崩壊済みのためスキップ。N=6 は別途検討 |
| trials | 30 | P(q) の双峰性解析に必要な統計量（最低 20 推奨）|
| n-shot | 0 | 外部磁場なし（full_sweep と統一）|
| model | `deepseek-ai/DeepSeek-R1-Distill-Qwen-7B` | スケーリング則検証用に他モデルも追加可 |
| num_predict | 4096（N≤5 の場合） | `calc_num_predict(N)` に従う |

**総試行数:** 9 T × 3 N × 30 trials = **810 試行**

**推定時間（Algorithm E 実装後）:**

| 領域 | 1 試行あたりの推定時間 | 試行数 | 小計 |
|---|---|---|---|
| SG 相（T=1.0〜1.3）| 30〜80s | 360 | 3〜8 時間 |
| PM 相（T=1.5〜3.0）| 15〜40s（Algorithm D 改訂後）| 450 | 2〜5 時間 |
| **合計** | — | 810 | **5〜13 時間** |

---

## 出力ディレクトリ構造

```
results/hanoi/collapse_phase/
└── deepseek-r1-distill-qwen-7b/
    ├── N3_T1_0/
    │   ├── summary.json
    │   └── meta.json
    ├── N3_T1_1/
    │   ├── summary.json
    │   └── meta.json
    ├── ...
    └── N5_T3_0/
        ├── summary.json
        └── meta.json
```

`full_sweep` とは独立したディレクトリ（`collapse_phase`）に保存し、解析スクリプトも分離する。

---

## 実行手順

### Step 1: 専用スクリプトの作成

`run_full_sweep.sh` を元に `run_collapse_phase_sweep.sh` を作成する。
変更点は以下の 3 箇所のみ:

```bash
# デフォルト値の変更
NS_STR="3 4 5"
TS_STR="1.0 1.1 1.2 1.3 1.5 1.8 2.0 2.5 3.0"
TRIALS=30

# 出力ディレクトリの変更（BASE_DIR）
BASE_DIR="results/hanoi/collapse_phase/${SLUG}"

# CMD の --sweep-type を変更
CMD="python3 runners/run_local.py \
    ...
    --sweep-type  collapse_phase  \
    ..."
```

### Step 2: ドライランで確認

```bash
# コンテナ内で実行
bash runners/scripts/run_collapse_phase_sweep.sh --dry-run
```

出力コマンドを目視確認し、T グリッド・N・出力先が正しいことを確認する。

### Step 3: 本番実行

```bash
bash runners/scripts/run_collapse_phase_sweep.sh --analyze
```

中断再開は自動対応済み（`summary.json` が `trials` 件に達しているセルはスキップ）。

### Step 4: DB 同期

```bash
bash db/sync.sh
```

---

## 解析手順と期待される図

### 解析 1: 崩壊モード分布の T 依存性

**スクリプト:** `analysis/analyze_phase_diagram.py`（`--dir` に `collapse_phase/{slug}` を指定）

**確認事項:**

- `move_loop_repeat` 比率（SG 相の指標）が T の上昇とともに減少するか
- `no_move_catchall` / `stagnation_after_move` 比率（PM 相の指標）が T の上昇とともに増加するか
- 2 指標の交差点 → $T_{SG \to PM}$ の粗推定

期待される図（early_stop 内訳の積み上げ棒グラフ）:

```
比率
1.0 │                        ██████████  ← no_move / stagnation（PM）
    │              ██████████████████
    │   ██████████████████████████████  ← move_loop_repeat（SG）
0.0 └────────────────────────────── T
    1.0  1.1  1.2  1.3  1.5  1.8  2.0
              ↑
         T_SG→PM ≈ 1.1〜1.3
```

### 解析 2: P(q) 分布の形状変化

**スクリプト:** `analysis/analyze_pq.py`（`--dir` に `collapse_phase/{slug}` を指定）

**確認事項:**

- T=1.0〜1.2 で P(q) が双峰性を示すか（q≈0 と q≈1 に分離 → SG 相）
- T≥1.5 で P(q) が q≈0 に集中するか（単峰性 → PM 相）
- 双峰性が消えるしきい値 = $T_{SG \to PM}$

### 解析 3: q_EA の T 依存性（$T_{SG \to PM}$ の定量化）

**スクリプト:** `analysis/analyze_pq.py`（`--out-summary` オプション）

$$q_{EA}(T) = \langle q^2 \rangle^{1/2}$$

- SG 相では $q_{EA} > 0$（記憶が残る）
- PM 相では $q_{EA} \approx 0$（記憶なし）
- $q_{EA}(T)$ の折れ点 → $T_{SG \to PM}$ の定量推定

**確認事項:**

- $T_{SG \to PM}$ が N=3, 4, 5 で揃っているか
  - 揃っている → p-spin 普遍性（Idea 6 の予測）を支持
  - N 依存性あり → Hopfield 項が支配的（容量効果）

### 解析 4: 臨界減速（Critical Slowing Down）

**スクリプト:** `analysis/analyze_slowing.py`

`pq_sweep` の npz データ（または `collapse_phase` の summary.json）から
`move_steps[0]`（最初の Move が出るまでのトークン位置）を集計する。

$$\tau_{\text{first\_move}} \sim |T - T_c|^{-z\nu}$$

T_c 付近（T≈1.0 前後）で first_move_step が発散するか確認する（Idea 5 の検証）。

---

## 結果の解釈ガイド

### シナリオ A: $T_{SG \to PM}$ が N 非依存（予測通り）

```
q_EA
高 │ ▓▓▓▓▓\
   │       \  ← N=3,4,5 が同じ曲線を描く
低 │        \___
   └─────────── T
          T_{SG→PM} ≈ 1.1〜1.3
```

→ p-spin 項（Idea 6 の (II) 項）が支配的。T 駆動の転移はモデル内部の性質。
→ 論文での主張: 「LLM の推論崩壊に p-spin モデルの臨界現象が対応する」

### シナリオ B: $T_{SG \to PM}$ に N 依存性あり

→ Hopfield 項（容量効果）が SG 相の性質に影響を与えている。
→ スケーリング則 $T_{SG \to PM}(N)$ の形状（冪乗・指数・線形）を解析する。

### シナリオ C: P(q) に双峰性が見られない

→ trials=30 では統計量不足の可能性 → trials=50 に増やして再実験。
→ または SG 相が T=1.0〜1.1 の狭い領域にのみ存在する。

---

## チェックリスト

### 実施前

- [ ] Algorithm D 閾値変更済み（`no_move_ratio = 0.25`）
- [ ] テスト D-1〜D-5 が全て PASS
- [ ] Algorithm E 実装完了（`stagnation_after_move`、`stagnation_ratio=0.20`）
- [ ] テスト E-1〜E-6 が全て PASS（E-6 は SKIP 可）
- [ ] `run_collapse_phase_sweep.sh` を作成済み
- [ ] `--dry-run` でコマンド確認済み
- [ ] GPU VRAM に余裕あること（空き ≥ 5 GB）

### 実施後

- [ ] 810 セルの `summary.json` が全て存在する
- [ ] `bash db/sync.sh` 完了
- [ ] 解析 1: 崩壊モード分布の積み上げグラフ作成
- [ ] 解析 2: P(q) 分布の双峰性確認（T=1.0〜1.3）
- [ ] 解析 3: q_EA vs T のグラフ作成・$T_{SG \to PM}$ 推定
- [ ] 解析 4: first_move_step vs T のグラフ作成（臨界減速の有無）
- [ ] シナリオ A/B/C のどれに該当するか判定し、Idea 6 との整合性をまとめる

---

## 実装フロー

実験を動かすまでに必要なコード変更・テスト・スクリプト作成を順番に示す。
各 Step に「Claudeへの指示文」「実行コマンド」「期待される結果」を記載した。

### タスク一覧

| Step | 内容 | 変更ファイル | 所要目安 |
|---|---|---|---|
| 1 | Algorithm D 閾値変更（1行） | `runners/run.py` | 1 分 |
| 2 | Algorithm E — EarlyStopConfig 拡張 | `runners/run.py` | 5 分 |
| 3 | Algorithm E — ストリーミングループ更新 | `runners/run.py` | 10 分 |
| 4 | テストファイル作成 | `tests/test_early_stop.py`（新規） | 10 分 |
| 5 | テスト実行・全 PASS 確認 | — | 5 分 |
| 6 | `run_collapse_phase_sweep.sh` 作成 | `runners/scripts/`（新規） | 5 分 |
| 7 | ドライランで確認 | — | 2 分 |
| 8 | 本番実行 | — | 5〜13 時間 |
| 9 | 解析実行 | — | 30 分 |

---

### Step 1: Algorithm D 閾値変更

**変更箇所:** `runners/run.py` の `EarlyStopConfig` 定義内

```
変更前: no_move_ratio: float = 0.50
変更後: no_move_ratio: float = 0.25
```

**Claudeへの指示:**

```
runners/run.py の EarlyStopConfig データクラスにある
`no_move_ratio: float = 0.50` を `0.25` に変更してください。
それ以外は一切変更しないでください。
```

**確認コマンド:**

```bash
grep "no_move_ratio" runners/run.py
```

**期待される出力:**

```
    no_move_ratio: float = 0.25
```

---

### Step 2: Algorithm E — EarlyStopConfig 拡張

**変更箇所:** `EarlyStopConfig` のフィールド末尾と有効化フラグ末尾に追加する。

```python
# フィールド追加（max_move_multiplier の下）
stagnation_ratio: float = 0.20

# 有効化フラグ追加（enable_move_loop の下）
enable_stagnation: bool = True
```

**Claudeへの指示:**

```
runners/run.py の EarlyStopConfig データクラスに以下の変更を加えてください。

1. フィールド `max_move_multiplier: float = 1.5` の下に次の行を追加:
       stagnation_ratio: float = 0.20

2. フラグ `enable_move_loop: bool = True` の下に次の行を追加:
       enable_stagnation: bool = True

docstring の Attributes にも stagnation_ratio の説明を追記してください:
   stagnation_ratio : float
       最後の手が出てから新たな手が出ないまま
       num_predict のこの割合のチャンク数が経過したら打ち切る。
       Algorithm E: Stagnation After Move。
```

**確認コマンド:**

```bash
grep -n "stagnation" runners/run.py
```

**期待される出力:**

```
（行番号）    stagnation_ratio: float = 0.20
（行番号）    enable_stagnation: bool = True
（行番号）    stagnation_ratio : float
```

---

### Step 3: Algorithm E — ストリーミングループ更新

**変更箇所:** `query_ollama` 関数内のストリーミングループ。

Ollama のストリーミングは 1 チャンク ≈ 1 トークンであるため、
チャンク数（`chunk_count`）をトークン位置の代理指標として使う。

変更前の初期化ブロック（`accumulated = ""` 付近）:
```python
accumulated   = ""
total_tokens  = 0
stop_reason: Optional[str] = None
```

変更後:
```python
accumulated       = ""
total_tokens      = 0
stop_reason: Optional[str] = None
chunk_count       = 0          # Algorithm E: チャンク数 ≈ 生成トークン数
last_move_chunk   = None       # Algorithm E: 最後に手が出たチャンク位置
prev_n_moves      = 0          # Algorithm E: 直前チェック時の手数
```

変更前のループ本体（`accumulated += ...` から `break` まで）:
```python
for raw_line in resp.iter_lines():
    if not raw_line:
        continue
    chunk = json.loads(raw_line)
    accumulated  += chunk.get("response", "")
    total_tokens  = chunk.get("eval_count", total_tokens)

    if chunk.get("done"):
        break

    # 早期終了チェック（50 文字おきに評価 → オーバーヘッド最小化）
    if early_stop_cfg is not None and len(accumulated) % 50 < 5:
        reason = check_early_stop(
            accumulated, num_predict, min_moves, early_stop_cfg
        )
        if reason:
            stop_reason = reason
            break
```

変更後:
```python
for raw_line in resp.iter_lines():
    if not raw_line:
        continue
    chunk = json.loads(raw_line)
    accumulated  += chunk.get("response", "")
    total_tokens  = chunk.get("eval_count", total_tokens)
    chunk_count  += 1

    if chunk.get("done"):
        break

    # Algorithm E: last_move_chunk を更新（毎チャンク、軽量）
    if early_stop_cfg is not None and early_stop_cfg.enable_stagnation:
        n_moves = len(_MOVE_RE.findall(accumulated))
        if n_moves > prev_n_moves:
            last_move_chunk = chunk_count
            prev_n_moves    = n_moves

        # 停滞チェック（手が出た後に限定）
        if last_move_chunk is not None:
            gap = chunk_count - last_move_chunk
            if gap > num_predict * early_stop_cfg.stagnation_ratio:
                stop_reason = "stagnation_after_move"
                break

    # 既存の早期終了チェック（50 文字おきに評価 → オーバーヘッド最小化）
    if early_stop_cfg is not None and len(accumulated) % 50 < 5:
        reason = check_early_stop(
            accumulated, num_predict, min_moves, early_stop_cfg
        )
        if reason:
            stop_reason = reason
            break
```

**Claudeへの指示:**

```
runners/run.py の query_ollama 関数に Algorithm E（停滞検出）を実装してください。

変更 1: accumulated = "" の直後にある初期化ブロックに以下を追加してください。
    chunk_count     = 0
    last_move_chunk = None
    prev_n_oves     = 0

変更 2: ストリーミングループ内の `accumulated += chunk.get("response", "")` の
直後に `chunk_count += 1` を追加してください。

変更 3: `if chunk.get("done"): break` の直後、既存の早期終了チェック（50文字おき）
の直前に、以下のブロックを挿入してください。

    # Algorithm E: last_move_chunk を更新（毎チャンク、軽量）
    if early_stop_cfg is not None and early_stop_cfg.enable_stagnation:
        n_moves = len(_MOVE_RE.findall(accumulated))
        if n_moves > prev_n_moves:
            last_move_chunk = chunk_count
            prev_n_moves    = n_moves

        if last_move_chunk is not None:
            gap = chunk_count - last_move_chunk
            if gap > num_predict * early_stop_cfg.stagnation_ratio:
                stop_reason = "stagnation_after_move"
                break

以上3点のみ変更し、他のロジックは変更しないでください。
変数名のタイポ（prev_n_oves → prev_n_moves）に注意してください。
```

**確認コマンド:**

```bash
grep -n "stagnation\|chunk_count\|last_move_chunk\|prev_n_moves" runners/run.py
```

**期待される出力（行番号は変動する）:**

```
（行番号）    chunk_count     = 0
（行番号）    last_move_chunk = None
（行番号）    prev_n_moves    = 0
（行番号）    chunk_count  += 1
（行番号）    if early_stop_cfg is not None and early_stop_cfg.enable_stagnation:
（行番号）            last_move_chunk = chunk_count
（行番号）            prev_n_moves    = n_moves
（行番号）            if gap > num_predict * early_stop_cfg.stagnation_ratio:
（行番号）                stop_reason = "stagnation_after_move"
```

---

### Step 4: テストファイル作成

**Claudeへの指示:**

```
以下の内容で tests/test_early_stop.py を新規作成してください。
tests/ ディレクトリが存在しない場合は作成してください。
```

作成するファイルの全内容:

```python
"""
tests/test_early_stop.py

Algorithm D（no_move_ratio 閾値変更）と Algorithm E（stagnation_after_move）の
単体テスト。Collapse-Phase Sweep 実施前に全テストが PASS であることを確認する。

実行方法（コンテナ内 /app から）:
    python3 -m pytest tests/test_early_stop.py -v
"""

import pytest
from runners.run import check_early_stop, EarlyStopConfig


# ===========================================================================
# テスト用ヘルパー
# ===========================================================================

def _d_only_cfg(no_move_ratio: float) -> EarlyStopConfig:
    """Algorithm D のみを有効にした設定を返す。"""
    return EarlyStopConfig(
        no_move_ratio=no_move_ratio,
        enable_think_budget=False,
        enable_move_ceiling=False,
        enable_move_loop=False,
        enable_stagnation=False,
    )


def check_stagnation(
    last_move_chunk: int | None,
    current_chunk: int,
    num_predict: int = 4096,
    stagnation_ratio: float = 0.20,
) -> str | None:
    """
    Algorithm E の発動条件を単体で検証するヘルパー。
    query_ollama のストリーミングループと同一ロジック。
    """
    if last_move_chunk is None:
        return None
    gap = current_chunk - last_move_chunk
    if gap > num_predict * stagnation_ratio:
        return "stagnation_after_move"
    return None


# ===========================================================================
# Algorithm D テスト（no_move_ratio 閾値変更の検証）
# ===========================================================================

class TestAlgorithmD:

    def test_d1_fires_above_threshold(self):
        """D-1: 3600 chars（閾値 3584 超）、手なし → no_move_catchall"""
        cfg = _d_only_cfg(no_move_ratio=0.25)
        text = "A" * 3600
        result = check_early_stop(text, num_predict=4096, min_moves=7, cfg=cfg)
        assert result == "no_move_catchall"

    def test_d2_silent_below_threshold(self):
        """D-2: 3500 chars（閾値 3584 未満）、手なし → None"""
        cfg = _d_only_cfg(no_move_ratio=0.25)
        text = "A" * 3500
        result = check_early_stop(text, num_predict=4096, min_moves=7, cfg=cfg)
        assert result is None

    def test_d3_silent_when_move_exists(self):
        """D-3: 閾値超過 + 手 1 件 → None（E の管轄）"""
        cfg = _d_only_cfg(no_move_ratio=0.25)
        text = "A" * 3600 + "\nMove 1 from A to C\n"
        result = check_early_stop(text, num_predict=4096, min_moves=7, cfg=cfg)
        assert result is None

    def test_d4_no_false_positive_in_ordered_phase(self):
        """D-4: 秩序相相当（1750 chars + 手）→ 誤発動しない"""
        cfg = _d_only_cfg(no_move_ratio=0.25)
        # 500 tok ≈ 1750 chars の推論後に最初の手（実測上限）
        text = "thinking..." * 130 + "\nMove 1 from A to C\n"
        result = check_early_stop(text, num_predict=4096, min_moves=7, cfg=cfg)
        assert result is None

    def test_d5_old_threshold_does_not_fire(self):
        """D-5: 旧閾値 0.50 では 3600 chars で発動せず、新閾値 0.25 では発動する"""
        text = "A" * 3600
        old_result = check_early_stop(
            text, num_predict=4096, min_moves=7, cfg=_d_only_cfg(0.50)
        )
        new_result = check_early_stop(
            text, num_predict=4096, min_moves=7, cfg=_d_only_cfg(0.25)
        )
        assert old_result is None
        assert new_result == "no_move_catchall"


# ===========================================================================
# Algorithm E テスト（stagnation_after_move の検証）
# ===========================================================================

class TestAlgorithmE:

    def test_e1_fires_after_moves1_stagnation(self):
        """E-1: moves=1後 gap=900 チャンク（閾値 819）→ stagnation_after_move"""
        result = check_stagnation(last_move_chunk=100, current_chunk=1000)
        assert result == "stagnation_after_move"

    def test_e2_fires_after_moves4_stagnation(self):
        """E-2: moves=4後 gap=900（B3 ボトルネック）→ stagnation_after_move"""
        result = check_stagnation(last_move_chunk=300, current_chunk=1200)
        assert result == "stagnation_after_move"

    def test_e3_silent_below_threshold(self):
        """E-3: gap=200（閾値 819 未満）→ None（手と手の間の通常推論）"""
        result = check_stagnation(last_move_chunk=800, current_chunk=1000)
        assert result is None

    def test_e4_silent_when_no_moves(self):
        """E-4: last_move_chunk=None（moves=0）→ None（D の管轄）"""
        result = check_stagnation(last_move_chunk=None, current_chunk=2000)
        assert result is None

    def test_e5_no_false_positive_in_ordered_phase(self):
        """E-5: 秩序相で誤発動しない（最終手後 gap=221 < 819）"""
        # 全手が 1621 チャンク以内に完成（実測最大値）
        # 最後の手が chunk=1400、その後は chunk=1621 で EOS
        result = check_stagnation(last_move_chunk=1400, current_chunk=1621)
        assert result is None

    def test_e6_algorithm_c_fires_before_e_in_loop(self):
        """E-6: ループ中は last_move_chunk が更新され続けるため E は発動しない"""
        # ループ中は手が連続して出る → gap が蓄積しない
        # chunk=10 ごとに手が出る場合、gap は常に < 819
        for move_chunk in range(100, 1000, 10):
            current = move_chunk + 9  # 次の手が出る直前
            result = check_stagnation(
                last_move_chunk=move_chunk, current_chunk=current
            )
            assert result is None, (
                f"E-6 FAIL: gap={current - move_chunk} で誤発動 "
                f"(move_chunk={move_chunk}, current={current})"
            )
```

**確認コマンド:**

```bash
python3 -m pytest tests/test_early_stop.py -v --tb=short
```

---

### Step 5: テスト実行・全 PASS 確認

**実行コマンド（コンテナ内）:**

```bash
docker compose exec hanoi-minimal bash -c "cd /app && python3 -m pytest tests/test_early_stop.py -v"
```

**期待される出力:**

```
========================= test session starts ==========================
collected 11 items

tests/test_early_stop.py::TestAlgorithmD::test_d1_fires_above_threshold PASSED
tests/test_early_stop.py::TestAlgorithmD::test_d2_silent_below_threshold PASSED
tests/test_early_stop.py::TestAlgorithmD::test_d3_silent_when_move_exists PASSED
tests/test_early_stop.py::TestAlgorithmD::test_d4_no_false_positive_in_ordered_phase PASSED
tests/test_early_stop.py::TestAlgorithmD::test_d5_old_threshold_does_not_fire PASSED
tests/test_early_stop.py::TestAlgorithmE::test_e1_fires_after_moves1_stagnation PASSED
tests/test_early_stop.py::TestAlgorithmE::test_e2_fires_after_moves4_stagnation PASSED
tests/test_early_stop.py::TestAlgorithmE::test_e3_silent_below_threshold PASSED
tests/test_early_stop.py::TestAlgorithmE::test_e4_silent_when_no_moves PASSED
tests/test_early_stop.py::TestAlgorithmE::test_e5_no_false_positive_in_ordered_phase PASSED
tests/test_early_stop.py::TestAlgorithmE::test_e6_algorithm_c_fires_before_e_in_loop PASSED

========================== 11 passed in 0.XXs ==========================
```

**FAIL が出た場合の対応:**

| エラー内容 | 原因 | 対処 |
|---|---|---|
| `ImportError: cannot import 'enable_stagnation'` | Step 2 未完了 | Step 2 の変更を再確認 |
| D-1 が None を返す | `no_move_ratio` がまだ 0.50 | Step 1 の変更を確認 |
| D-5 で旧閾値が発動する | 変更前後が逆になっている | run.py のデフォルト値を確認 |
| E-1〜E-2 が None を返す | `check_stagnation` のロジックミス | 閾値計算式を確認（`4096 × 0.20 = 819.2`） |

---

### Step 6: run_collapse_phase_sweep.sh 作成

**Claudeへの指示:**

```
runners/scripts/run_full_sweep.sh をコピーして
runners/scripts/run_collapse_phase_sweep.sh を新規作成してください。

以下の3点のみ変更し、それ以外は run_full_sweep.sh と同一にしてください。

変更 1: デフォルト値（ファイル上部の変数定義）
    NS_STR="3 4 5"
    TS_STR="1.0 1.1 1.2 1.3 1.5 1.8 2.0 2.5 3.0"
    TRIALS=30

変更 2: BASE_DIR の定義
    変更前: BASE_DIR="results/hanoi/full_sweep/${SLUG}"
    変更後: BASE_DIR="results/hanoi/collapse_phase/${SLUG}"

変更 3: CMD 内の --sweep-type
    変更前: --sweep-type  full_sweep
    変更後: --sweep-type  collapse_phase

ファイル先頭のコメントも collapse_phase 向けに書き換えてください。
```

**確認コマンド:**

```bash
diff runners/scripts/run_full_sweep.sh runners/scripts/run_collapse_phase_sweep.sh
```

**期待される diff（この 3 箇所のみ差分）:**

```diff
-NS_STR="2 3 4 5 6"
-TS_STR="0.2 0.4 0.6 0.8 1.0 1.2 1.5 2.0"
-TRIALS=25
+NS_STR="3 4 5"
+TS_STR="1.0 1.1 1.2 1.3 1.5 1.8 2.0 2.5 3.0"
+TRIALS=30
...
-    BASE_DIR="results/hanoi/full_sweep/${SLUG}"
+    BASE_DIR="results/hanoi/collapse_phase/${SLUG}"
...
-                --sweep-type  full_sweep     \
+                --sweep-type  collapse_phase \
```

---

### Step 7: ドライランで確認

**実行コマンド:**

```bash
docker compose exec hanoi-minimal bash -c \
  "cd /app && bash runners/scripts/run_collapse_phase_sweep.sh --dry-run"
```

**確認ポイント:**

- `N` が `3 4 5` の 3 種類のみ表示される（N=2, N=6 が含まれない）
- `T` が `1.0 1.1 1.2 1.3 1.5 1.8 2.0 2.5 3.0` の 9 点のみ
- 出力ディレクトリが `results/hanoi/collapse_phase/...` になっている
- `--sweep-type collapse_phase` が CMD に含まれる
- 総試行数が `9 × 3 × 30 = 810` と表示される

**期待されるサマリー出力の抜粋:**

```
========================================================
  Full Sweep  (phase diagram + P(q) + model sweep)
========================================================
  モデル数  : 1
    - deepseek-ai/DeepSeek-R1-Distill-Qwen-7B
  N         : 3 4 5
  T         : 1.0 1.1 1.2 1.3 1.5 1.8 2.0 2.5 3.0
  trials/セル: 30
  総試行数  : 810  (810 × 1 モデル)
========================================================
```

---

### Step 8: 本番実行

**実行コマンド:**

```bash
docker compose exec hanoi-minimal bash -c \
  "cd /app && bash runners/scripts/run_collapse_phase_sweep.sh --analyze" \
  2>&1 | tee logs/collapse_phase_sweep.log
```

> `logs/` ディレクトリがなければ `mkdir -p logs` で作成する。

**進捗確認（別ターミナルから）:**

```bash
# 完了セル数を確認
find results/hanoi/collapse_phase -name "summary.json" | wc -l

# 直近の出力を確認
tail -f logs/collapse_phase_sweep.log

# 長時間停滞していないか確認（stagnation_after_move 件数）
python3 - <<'EOF'
import json, pathlib
es = {}
for p in pathlib.Path("results/hanoi/collapse_phase").rglob("summary.json"):
    for r in json.loads(p.read_text()):
        k = r.get("early_stop") or "null"
        es[k] = es.get(k, 0) + 1
for k, v in sorted(es.items()):
    print(f"  {k}: {v}")
EOF
```

**中断・再開:**

```bash
# 中断は Ctrl+C でよい（summary.json 生成済みのセルは自動スキップ）
# 再開は同じコマンドを再実行するだけ
bash runners/scripts/run_collapse_phase_sweep.sh --analyze
```

---

### Step 9: 解析実行

`--analyze` オプション付きで実行した場合は自動実行されるが、
個別に再実行したい場合は以下を使う。

```bash
SLUG="deepseek-r1-distill-qwen-7b"
BASE="results/hanoi/collapse_phase/${SLUG}"
FIG="figures/collapse_phase/${SLUG}"
mkdir -p "$FIG"

# 解析 1: 崩壊モード分布（early_stop 内訳）
python3 analysis/analyze_phase_diagram.py \
    --dir "$BASE" \
    --ns 3 4 5 \
    --ts 1.0 1.1 1.2 1.3 1.5 1.8 2.0 2.5 3.0 \
    --out "${FIG}/phase_diagram.png"

# 解析 2・3: P(q) 分布 + q_EA vs T
python3 analysis/analyze_pq.py \
    --dir       "$BASE" \
    --ns        3 4 5 \
    --ts        1.0 1.1 1.2 1.3 1.5 1.8 2.0 2.5 3.0 \
    --out-dist  "${FIG}/pq_dist.png" \
    --out-summary "${FIG}/pq_summary.png"

# 解析 4: 臨界減速（first_move_step）
python3 analysis/analyze_slowing.py \
    --dir "$BASE" \
    --out "${FIG}/slowing.png"
```

**生成される図の一覧と確認ポイント:**

| ファイル | 確認ポイント |
|---|---|
| `phase_diagram.png` | T=1.1〜1.3 で `move_loop_repeat` → `no_move_catchall` に切り替わる |
| `pq_dist.png` | T=1.0〜1.2 で双峰性、T≥1.5 で q≈0 集中 |
| `pq_summary.png` | q_EA が N=3,4,5 で重なるか確認（p-spin 普遍性） |
| `slowing.png` | T≈1.0 前後で first_move_step が増大するか |

**解析後の DB 同期:**

```bash
docker compose exec hanoi-minimal bash -c "cd /app && bash db/sync.sh"
```
