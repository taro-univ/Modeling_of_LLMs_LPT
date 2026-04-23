# スケーリング則抽出実験設計書

## 研究目的

**Layer 1**（7B単体の phase_diagram / pq_sweep）で3相の存在を実証した後、
複数モデルで同一実験を行い、**相境界のスケーリング則がモデルによらず普遍的か**を検証する。

主張したい命題：

> LLM の推論崩壊は、生成温度 $T$・タスク複雑度 $N$・モデル容量 $M$ の 3 変数空間で
> 記述される相図を持ち、相境界のスケーリング指数 $\alpha$ はモデルアーキテクチャに依存しない
> 普遍クラスを形成する。

---

## 変数の整理

| 変数 | 物理的対応 | 本実験での役割 |
|---|---|---|
| $T$（temperature） | 熱浴温度・ノイズ強度 | 制御変数（各モデルでスイープ） |
| $N$（disk count） | システムサイズ・エネルギー障壁 | 制御変数（各モデルでスイープ） |
| $M$（model capacity） | スピン系のスピン数・有効自由度 | モデル間比較の軸 |
| $n\text{-shot}$ | 外部磁場 | 固定（experiment_design.md に従う） |

### スケーリング則の形式

$T$ 方向の相境界（accuracy = 0.5 の交差点）を $T_c(N, M)$ と定義する。

$$
T_c(N,\ M) = A(M) \cdot N^{-\alpha}
\quad \text{または} \quad
T_c(N,\ M) = B(M) \cdot e^{-\beta N}
$$

- $\alpha,\ \beta$：スケーリング指数（**普遍クラスを特徴づける**）
- $A(M),\ B(M)$：モデル依存の係数（容量が大きいほど大きい）

普遍性の主張：**$\alpha$（または $\beta$）がモデルによらず一定**であること。

### $N$ 方向の臨界点

$T = T_{\min}$（低温極限）における臨界ディスク数 $N_c(M)$ を定義する。

$$
N_c(M) \;\propto\; \log M \quad \text{または} \quad N_c(M) \;\propto\; M^{\gamma}
$$

$N_c(M)$ のスケーリングはモデル容量とタスク難度の関係を記述し、
モデル規模の「推論容量」の定量指標になる。

---

## 対象モデル

### 選定基準

- HuggingFace Transformers で `output_hidden_states=True` が使えること
- NF4 4-bit 量子化で VRAM 12GB に収まること
- 推論（Reasoning）の有無が揃う構成にすること

### モデル一覧

| 優先度 | モデル | パラメータ数 $M$ | hidden_size | NF4 VRAM目安 | 役割 |
|---|---|---|---|---|---|
| ★★★ | `DeepSeek-R1-Distill-Qwen-7B` | 7B | 3584 | 5 GB | **ベースライン**（Layer 1 と同一） |
| ★★★ | `DeepSeek-R1-Distill-Qwen-14B` | 14B | 5120 | 9 GB | **同系列スケーリング**・$T_c(N)$ の3点目確立 |
| ★★★ | `DeepSeek-R1-Distill-Llama-8B` | 8B | 4096 | 5 GB | **異アーキテクチャ**（Qwen vs Llama）での普遍性確認 |
| ★★ | `Qwen/Qwen2.5-7B-Instruct` | 7B | 3584 | 5 GB | **Reasoning蒸留なし**のベースライン（3相が出るか） |
| ★ | `DeepSeek-R1-Distill-Qwen-1.5B` | 1.5B | 1536 | 1 GB | スケーリング則の**下限点**（$N_c$ が最小） |

### VRAM 見積もり（NF4, bfloat16 compute）

$$
\text{VRAM}_{\text{total}} = \underbrace{\frac{M \times 4\,\text{bit}}{8}}_{\text{モデル重み}}
+ \underbrace{2 \times L \times S \times H_{\text{kv}} \times d_{\text{head}} \times 2\,\text{bytes}}_{\text{KV キャッシュ}}
$$

| モデル | 重み | KV キャッシュ (S=4096) | 合計 |
|---|---|---|---|
| 1.5B (Qwen) | 0.75 GB | 0.13 GB | **0.9 GB** |
| 7B (Qwen) | 3.5 GB | 0.23 GB | **4.0 GB** |
| 8B (Llama) | 4.0 GB | 0.27 GB | **4.5 GB** |
| 14B (Qwen) | 7.0 GB | 0.37 GB | **7.5 GB** |

全モデルが 12GB VRAM に収まる。

---

## 実験条件

### 基本方針

各モデルで **phase_diagram.sh と同一の (N, T) グリッドを 20 trials** 走らせる。
精度の高い $T_c(N)$ 推定には 30 trials が望ましいが、複数モデルの比較が目的のため 20 trials で効率を優先する。

### グリッド設計

```
N      = 2, 3, 4, 5, 6
T      = 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0
trials = 20 per (N, T)
総試行数/モデル = 5 × 8 × 20 = 800
```

### モデルごとの注意点

| モデル | 特記事項 |
|---|---|
| 14B | N=4 で acc ≈ 80% が期待される → $T_c(N=4)$ の精密推定が可能 |
| Llama-8B | `hidden_states` のレイヤー数が異なる（32層）。CAPTURE_LAYERS の相対インデックスは変更不要 |
| 1.5B | N=2 でも崩壊する可能性あり → T スイープより N=2, 3 に集中してもよい |
| Qwen-Instruct | `<think>` プリフィルが不要の可能性あり（要確認）。崩壊モードが変わる可能性がある |

### `run_hf.py` の変更点

モデル切り替えは `--model-id` 引数のみで対応可能（既実装）。

```bash
python3 run_hf.py \
    --model-id deepseek-ai/DeepSeek-R1-Distill-Llama-8B \
    --N 4 --trials 20 --temperature 0.6 \
    --output-dir results/hanoi/scaling/Llama8B/N4_T0_6 \
    --output     results/hanoi/scaling/Llama8B/N4_T0_6/summary.json
```

出力先: `results/hanoi/scaling/{ModelTag}/N{N}_T{T}/`

---

## 測定量

### accuracy $m(N, T, M)$

相境界 $T_c(N, M)$ の推定に直接使う主要測定量。

$$
T_c(N,\ M) \;:\quad m(N,\ T_c,\ M) = 0.5
$$

### 崩壊モード比率

各 $(N, T, M)$ セルにおける early\_stop 内訳：

$$
f_{\text{loop}}(N, T, M), \quad f_{\text{nomov}}(N, T, M), \quad f_{\text{goal}}(N, T, M)
$$

スピングラス相と常磁性相の相境界を **$f_{\text{loop}} = f_{\text{nomov}}$** の等値線として定義できる。
これは accuracy ベースの $T_c$ とは異なる独立な相境界推定量になる。

### P(q) overlap 分布（隠れ状態）

Layer 1（pq\_sweep）で確立した手法を各モデルに適用する。

$$
q^{\alpha\beta} = \frac{\mathbf{h}^{\alpha} \cdot \mathbf{h}^{\beta}}{\|\mathbf{h}^{\alpha}\| \|\mathbf{h}^{\beta}\|}
$$

| 相 | $P(q)$ の形状 | $q_{EA}$ |
|---|---|---|
| 秩序相 | $q \approx 1$ に集中 | 1 に近い |
| スピングラス相 | 双峰 or 広幅 | $0 < q_{EA} < 1$ |
| 常磁性相 | $q \approx 0$ に集中 | ≈ 0 |

---

## 解析手法

### Step 1: 各モデルで $T_c(N)$ を推定

accuracy 行列から線形補間で $T_c(N, M)$ を求める（`analyze_phase_diagram.py` の既存ロジックを流用）。

$$
T_c(N,\ M) \approx T_j + (T_{j+1} - T_j) \cdot \frac{0.5 - m_j}{m_{j+1} - m_j}
$$

### Step 2: スケーリング則のフィット

各モデルで得た $(N,\ T_c)$ の点群に対し、冪乗則と指数則の両方をフィットする。

$$
\ln T_c = \ln A - \alpha \ln N \quad \text{（冪乗則: log-log 直線）}
$$

$$
\ln T_c = \ln B - \beta N \quad \text{（指数則: log-linear 直線）}
$$

フィットの質（$R^2$）で関数形を選択する。

### Step 3: $\alpha$ の比較

複数モデルで得た $\alpha$ を比較し、普遍性を検定する。

$$
\bar{\alpha} = \frac{1}{K}\sum_{k=1}^{K} \alpha_k, \quad \sigma_\alpha = \text{std}(\{\alpha_k\})
$$

$\sigma_\alpha / \bar{\alpha} \ll 1$ であれば普遍クラスの主張が成立する。

### Step 4: $N_c(M)$ のスケーリング

$T = T_{\min} = 0.2$ における秩序相の上限 $N_c(M)$ を各モデルで特定し、
パラメータ数 $M$ に対してプロットする。

$$
N_c(M) \sim \gamma \log M + \delta
$$

が成立すれば、「推論容量は対数スケールで増大する」という命題が導かれる。

---

## 期待される結果

### 相図の比較（概念図）

```
N
6  |                   [14B]
5  |            [8B, 14B]
4  | [1.5B] [7B]  [8B]  [14B]
3  | [1.5B] [7B]  ...
2  |   ...
   └──────────────────────────── T
     0.2     0.8     1.5     2.0

  ░ 崩壊相  ▓ 秩序相
  [M] = モデルごとの秩序相の境界線
```

モデルが大きいほど秩序相が右上に広がる（$T_c$ が高く・$N_c$ が大きい）ことが期待される。

### スケーリングプロット（期待）

```
log T_c
  │  ○ 1.5B
  │   ○ 7B
  │    ○ 8B(Llama)
  │     ○ 14B
  │──────────────── 傾き = -α（普遍）
  └────────────────── log N
```

係数 $A(M)$ は上にシフト（容量依存）するが、傾き $-\alpha$ は共通。

---

## 実施順序

```
1. DeepSeek-R1-Distill-Qwen-14B
   → N=4 でT_c が測れる → スケーリング則の3点目を確立
   → Layer 1（7B）との比較で Qwen 系の α を決定

2. DeepSeek-R1-Distill-Llama-8B
   → Qwen-7B と α を比較 → アーキテクチャ依存性の検証

3. Qwen2.5-7B-Instruct
   → Reasoning蒸留なしで3相が出るか確認
   → 出ない場合:「スピングラス崩壊は推論訓練に固有の現象」という主張が成立

4. DeepSeek-R1-Distill-Qwen-1.5B
   → N_c(M) スケーリングの下限点を追加
   → α の3点目として使用可能
```

各モデルの実行スクリプト: `run_scaling_sweep.sh`（未実装・要作成）

---

## 成果物

| ファイル | 内容 |
|---|---|
| `results/hanoi/scaling/{ModelTag}/` | 各モデルの npz + summary.json |
| `figures/scaling_law.png` | $T_c(N)$ の log-log プロット（モデル別） |
| `figures/Nc_scaling.png` | $N_c(M)$ vs $\log M$ プロット |
| `figures/phase_diagram_comparison.png` | モデル別相図の重ね合わせ |
| `analyze_scaling.py` | Step 1〜4 の解析スクリプト（未実装・要作成） |
