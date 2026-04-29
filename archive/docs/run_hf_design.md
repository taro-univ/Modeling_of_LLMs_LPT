# run_hf.py 設計仕様書

## 概要

`run_hf.py` は `run.py`（Ollama API 版）の HuggingFace Transformers 対応版。
DeepSeek-R1-Distill-Qwen-7B を **NF4 4-bit 量子化**でローカル実行し、
推論崩壊の相転移解析に必要な**隠れ状態ベクトルを選択的に保存**する。

---

## 1. VRAM 内訳の詳細試算

### 対象モデル: DeepSeek-R1-Distill-Qwen-7B

| パラメータ | 値 |
|---|---|
| 総パラメータ数 | 7.62 B |
| アーキテクチャ | Qwen2.5-7B ベース |
| hidden\_size | 3,584 |
| num\_hidden\_layers | 28 |
| num\_attention\_heads | 28 |
| num\_key\_value\_heads | 4（GQA） |
| head\_dim | 128 |
| 語彙サイズ | 152,064 |

---

### 1.1 モデル重み（NF4 量子化後）

NF4（Normal Float 4）は QLoRA で導入された 4-bit 量子化形式。
各 64 パラメータブロックに対してスケールファクタを fp16 で保持する（Double Quantization により
スケール自体もさらに圧縮される）。

$$
\text{VRAM}_{\text{weights}} = \underbrace{N_{\text{embed}} \cdot d_{\text{model}} \cdot 2\,\text{B}}_{\text{Embedding（fp16）}}
+ \underbrace{N_{\text{transformer}} \times 0.5\,\text{B/param}}_{\text{Transformer 層（NF4）}}
+ \underbrace{\frac{N_{\text{transformer}}}{64} \times 2\,\text{B}}_{\text{量子化スケール（fp16）}}
$$

| 成分 | 計算 | 概算 |
|---|---|---|
| Embedding 層 (fp16) | $152064 \times 3584 \times 2$ | 1.09 GB |
| Transformer 層 (NF4) | $7.07 \times 10^9 \times 0.5\,\text{B}$ | 3.53 GB |
| 量子化スケール + Double Quant | $(7.07 \times 10^9 / 64) \times 2\,\text{B}$ | 0.22 GB |
| **合計** | | **≈ 4.84 GB** |

> **実測値（コミュニティベンチマーク）は 5.0〜5.5 GB 程度。** 以降の計算では **5.0 GB** を使用。

---

### 1.2 KV キャッシュ（トークン数依存）

KV キャッシュサイズの公式（GQA 対応版）：

$$
\text{VRAM}_{\text{KV}} = 2 \times L \times S \times H_{\text{kv}} \times d_{\text{head}} \times \text{dtype\_bytes}
$$

- $L = 28$（レイヤー数）
- $H_{\text{kv}} = 4$（GQA の KV ヘッド数）
- $d_{\text{head}} = 128$
- dtype = bfloat16（2 bytes）

$$
= 2 \times 28 \times S \times 4 \times 128 \times 2 = 57{,}344 \times S \; \text{bytes}
$$

| N | $\text{max\_tokens}\ S$ | KV キャッシュ |
|---|---|---|
| 5 | 4,096 | **228 MB** |
| 6 | 8,192 | **456 MB** |
| 7 | 16,384 | **912 MB** |

---

### 1.3 アクティベーションバッファ（1 トークン分）

カスタム逐次生成ループでは、1 ステップあたり**1 トークン分の隠れ状態のみ**が GPU に残る：

$$
\text{VRAM}_{\text{act}} = (L+1) \times 1 \times d_{\text{model}} \times 2\,\text{B}
= 29 \times 3584 \times 2 \approx \mathbf{0.21\,\text{MB}}
$$

隠れ状態保存のためのバッファは事実上 **無視できるサイズ**。

---

### 1.4 VRAM 合計サマリー（12 GB GPU での余裕）

| 成分 | N=5 | N=6 | N=7 |
|---|---|---|---|
| モデル重み (NF4) | 5.0 GB | 5.0 GB | 5.0 GB |
| KV キャッシュ | 0.23 GB | 0.46 GB | 0.91 GB |
| アクティベーション（1 token） | ~0.001 GB | ~0.001 GB | ~0.001 GB |
| PyTorch / CUDA ランタイム | 0.5 GB | 0.5 GB | 0.5 GB |
| **合計** | **≈ 5.7 GB** | **≈ 6.0 GB** | **≈ 6.4 GB** |
| **12 GB GPU での余裕** | **+6.3 GB** | **+6.0 GB** | **+5.6 GB** |

**結論: N=7 まで 12 GB GPU で問題なく動作する。N=8（32,768 tokens）でも KV が 1.8 GB 増加するのみで合計 ≈ 8.2 GB に収まる見込み。**

---

## 2. 各実装コンポーネントの詳細

### 2.1 モデルロード（bitsandbytes NF4）

```python
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import torch

MODEL_ID = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",          # NF4: 正規分布に最適化された非均一4-bit量子化
    bnb_4bit_compute_dtype=torch.bfloat16,  # 計算時は bfloat16 に dequantize
    bnb_4bit_use_double_quant=True,     # スケール自体を 8-bit で二重量子化（メモリ節約）
)

model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    quantization_config=bnb_config,
    device_map="cuda:0",
    torch_dtype=torch.bfloat16,
)
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
```

**NF4 の物理的意味:**
通常の 4-bit 均一量子化（INT4）と異なり、NF4 は正規分布 $\mathcal{N}(0, 1)$ の分位点を格子点として使用する。
Transformer の重みが経験的に正規分布に従うことを活用し、量子化誤差を最小化する。

$$
q_i = \text{round}\left( \frac{w_i - \mu_b}{\sigma_b} \cdot 2^{b-1} \right), \quad b=4
$$

---

### 2.2 カスタム逐次生成ループ

`model.generate()` を使わず、トークンを 1 つずつ生成することで：
- **任意のタイミングでの早期終了**が可能
- **Move 出力タイミングでの隠れ状態キャプチャ**が可能
- KV キャッシュを利用するため速度はほぼ同等

```
ループ構造:
  for step in range(max_new_tokens):
      outputs = model(input_ids=current_token, past_key_values=kv_cache,
                      use_cache=True, output_hidden_states=True)
      ↓
      次トークンを greedy decoding で決定
      ↓
      accumulated_text を更新
      ↓
      [Move 検出] → hidden state を CPU に転送して保存
      ↓
      [早期終了チェック] → 条件を満たしたらループを break
      ↓
      kv_cache を次ステップへ引き継ぎ
```

KV キャッシュの引き継ぎにより、全トークンの再計算は不要。1 ステップのコストは常に $O(S \cdot d_{\text{model}})$（$S$: 現在の系列長）。

---

### 2.3 早期終了（StoppingCriteria 相当の実装）

`run.py` の `check_early_stop()` をそのまま流用し、カスタムループ内で毎ステップ呼び出す。

| アルゴリズム | 条件 | 効果 |
|---|---|---|
| **A: Think Budget** | `<think>` 内推定トークンが `num_predict × ratio` 超 | Token Exhaustion 防止 |
| **B: Move Ceiling** | 抽出済み手数が最短手数の 1.5 倍超 | 過剰出力の早期検出 |
| **C: Move Loop** | 直近 6 手に同一手 or 往復手 | ループ崩壊の検出 |
| **D: No Move Catch-All** | 50% 消費しても手が 1 つも抽出されない | プレーンテキスト応答の補足 |

**`run.py` との差分:**
- Ollama ストリーミングの `for raw_line in resp.iter_lines()` → `for step in range(max_new_tokens)` に置換
- `check_early_stop()` の呼び出しインターフェースは変更なし

---

### 2.4 隠れ状態の選択的キャプチャ

#### キャプチャ戦略

全トークン × 全レイヤーの保存は非現実的：

$$
\text{N=5, 全保存} = 4096 \times 29 \times 3584 \times 2\,\text{B} \approx 0.85\,\text{GB（RAM）}
$$

**Move 出力トークン位置のみ**を保存する戦略を採用：

$$
\text{N=5（31 手）, 選択的保存} = 31 \times 3 \times 3584 \times 4\,\text{B（fp32）} \approx 1.3\,\text{MB}
$$

#### キャプチャするレイヤー

| レイヤーインデックス | 意味 | 研究上の意義 |
|---|---|---|
| `[-1]` (= layer 28) | 最終出力層 | 最終的な「意思決定」表現 |
| `[-8]` (= layer 21) | 中間後半層 | 高水準の推論表現 |
| `[-16]` (= layer 13) | 中間層 | 低〜中水準の特徴表現 |

相転移解析の観点では、**最終層の隠れ状態の軌跡**がポテンシャル $V(x)$ の変化と対応することが期待される。
中間層との比較により、崩壊がどの層で先行して発生するかを特定できる。

#### 保存データ構造（npz）

各試行について以下を `.npz` 形式で保存：

```
results_N{N}_hf/
  trial_{i:03d}_hidden.npz
    ├── layer_m1/   shape: (num_moves, 3584)  # 最終層
    ├── layer_m8/   shape: (num_moves, 3584)  # -8 層
    ├── layer_m16/  shape: (num_moves, 3584)  # -16 層
    ├── move_steps/ shape: (num_moves,)       # 何ステップ目で出力されたか
    └── move_texts  dtype: str array          # 抽出された手の文字列
```

---

## 3. ファイル構成

```
minimal_exp/
├── run.py              # 既存: Ollama API 版（変更なし）
├── run_hf.py           # 新規: HuggingFace 版（本仕様に基づき実装）
├── hanoi_env.py        # 共用: 環境定義（変更なし）
├── requirements.txt    # 更新: transformers, bitsandbytes, accelerate 追加
├── docs/
│   └── run_hf_design.md   # 本ファイル
└── results/
    └── hanoi/
        ├── results_N*.json              # Ollama 版の結果
        └── results_N*_hf/
            ├── summary.json             # HF 版の集計結果
            └── trial_*_hidden.npz       # 隠れ状態データ
```

---

## 4. 追加パッケージ（requirements.txt への追記分）

```
transformers>=4.45.0
bitsandbytes>=0.43.0
accelerate>=0.34.0
safetensors>=0.4.0
```

> **注意:** `bitsandbytes` は CUDA 11.x / 12.x 両対応だが、
> 現 Dockerfile の CUDA 12.8 環境では `bitsandbytes>=0.43.0` を使用すること。

---

## 5. 既存 run.py との比較

| 項目 | run.py（Ollama） | run_hf.py（HuggingFace） |
|---|---|---|
| モデル実行場所 | WSL2 ホスト（Ollama） | Docker コンテナ内 GPU |
| 量子化 | GGUF（Ollama 内部） | NF4（bitsandbytes） |
| 早期終了 | ストリーミング中に check | カスタムループ内で check |
| 隠れ状態 | **取得不可** | **Move 位置で npz 保存** |
| 推論速度 | 高速（llama.cpp） | やや遅い（Python ループ） |
| N=7 対応 | △（early stop 頼り） | ◎（VRAM 余裕あり） |

---

## 6. 研究上の位置づけ

隠れ状態 $\mathbf{h}^{(l)}_t \in \mathbb{R}^{d_{\text{model}}}$ を Move 位置 $t_1, t_2, \ldots, t_k$ で保存することで、
以下の解析が可能になる：

### 6.1 推論ポテンシャルとの相関

各 Move 位置の隠れ状態から、対応する盤面状態の $V(x)$ を計算済みの `hanoi_env.evaluate_state()` で得られる。

$$
\{ \mathbf{h}^{(28)}_{t_i},\ V(x_{t_i}) \}_{i=1}^{k}
$$

この対応から**「隠れ状態空間における $V(x)$ の等高線構造」**を PCA / UMAP で可視化できる。

### 6.2 崩壊の先行指標

推論が崩壊（ループ・Token Exhaustion）に向かう試行と成功試行とで、
**隠れ状態軌跡の発散度合い**（例: コサイン類似度の急落、ノルムの爆発）を比較することで、
崩壊の先行指標（early warning signal）を定量化できる。

これはスピン系の秩序変数 $m = \frac{1}{N}\sum_i s_i$ の振る舞いと統計力学的に対応する。

$$
\phi(t) = \frac{\mathbf{h}^{(28)}_t \cdot \mathbf{h}^{(28)}_{t-1}}{\|\mathbf{h}^{(28)}_t\| \|\mathbf{h}^{(28)}_{t-1}\|}
$$

$\phi(t)$ が急落する時刻が推論崩壊の「臨界点」に対応すると予想される。
