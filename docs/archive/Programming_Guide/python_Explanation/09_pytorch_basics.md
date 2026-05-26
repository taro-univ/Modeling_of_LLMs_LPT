# 09 PyTorch基礎

`run_hf.py` でのモデル推論（トークン生成・隠れ状態取得）に必要な概念。

## Tensor（テンソル）

PyTorch の基本データ型。NumPy の ndarray に似ているが GPU で動く。

```python
import torch

t = torch.tensor([[1.0, 2.0], [3.0, 4.0]])   # 2×2 テンソル
t.shape    # torch.Size([2, 2])
t.dtype    # torch.float32
t.device   # device(type='cpu')

# GPU に転送
device = "cuda:0"
t = t.to(device)
```

## device の扱い

```python
device = next(model.parameters()).device   # モデルが乗っているデバイスを取得

input_ids = tokenizer(...).input_ids.to(device)   # 入力を同じデバイスへ
next_token = torch.tensor([[token_id]], device=device)
```

## モデルの推論

```python
model.eval()   # 推論モード（ドロップアウト等を無効化）

with torch.no_grad():   # 勾配計算を無効化（メモリ・速度の節約）
    outputs = model(
        input_ids=input_ids,
        past_key_values=past_key_values,
        use_cache=True,
        output_hidden_states=True,   # 隠れ状態を出力に含める
    )
```

`torch.no_grad()` は推論時に必ず使う。勾配を計算しないのでメモリを大幅に節約できる。

## outputs の構造

```python
outputs.logits          # shape: (batch, seq_len, vocab_size) — 各トークンのスコア
outputs.past_key_values # KV キャッシュ（次ステップで再利用）
outputs.hidden_states   # tuple of (batch, seq_len, hidden_size) × (num_layers + 1)
```

### logits からトークンをサンプリング

```python
logits = outputs.logits[0, -1, :].float()   # 最後の位置の logits → 1D

# Temperature スケーリング
logits = logits / temperature

# Softmax → 確率分布
probs = torch.softmax(logits, dim=-1)

# サンプリング（greedy は temperature=0 相当で全試行が同一になる）
next_token_id = int(torch.multinomial(probs, num_samples=1).item())
```

### 隠れ状態の取り出し

```python
# hidden_states は (num_layers + 1) 個のテンソルのタプル
# [0] = embedding 層, [1]〜[28] = Transformer 層
hs = outputs.hidden_states[-1]   # 最終層: shape (batch, seq_len, hidden_size)
hs_last_token = hs[0, -1, :]     # バッチ0、最後のトークン位置 → 1D (hidden_size,)

# numpy に変換して保存
vec = hs_last_token.float().cpu().numpy()   # float32 に変換してから CPU へ
```

## KV キャッシュ（逐次生成の高速化）

トークンを1つずつ生成するループで、毎ステップ全トークンを再計算しないための仕組み。

```python
past_key_values = None

for step in range(num_predict):
    outputs = model(
        input_ids=current_input_ids,   # 最新の1トークンのみ渡す
        past_key_values=past_key_values,
        use_cache=True,
    )
    past_key_values = outputs.past_key_values   # 次ステップへ引き継ぐ

    next_token_id = ...
    current_input_ids = torch.tensor([[next_token_id]], device=device)
```

## 4-bit 量子化（BitsAndBytes）

7B パラメータモデルを VRAM 8GB 程度で動かすための量子化。

```python
from transformers import BitsAndBytesConfig

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",         # NF4: 正規分布の分位点を格子点に使う
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,    # スケールを 8-bit で二重量子化
)

model = AutoModelForCausalLM.from_pretrained(
    model_id,
    quantization_config=bnb_config,
    device_map="cuda:0",
    torch_dtype=torch.bfloat16,
)
```

NF4 量子化により、`float16`（14GB）に対して約 1/4 の VRAM（3〜4GB）でロードできる。

## dtype まとめ

| dtype | ビット数 | 用途 |
|---|---|---|
| `torch.float32` | 32 bit | logits の計算（精度優先） |
| `torch.bfloat16` | 16 bit | モデルの重み・推論（速度・VRAM 優先） |
| `torch.int32` | 32 bit | トークン ID |
