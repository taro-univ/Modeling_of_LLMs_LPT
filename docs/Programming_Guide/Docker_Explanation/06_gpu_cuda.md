# 06 GPU・CUDA：コンテナへの GPU 公開

## GPU をコンテナに渡す仕組み

通常、コンテナはホストのハードウェアに直接アクセスできない。GPU を使うには **NVIDIA Container Toolkit** が必要。

```
WSL2 ホスト
  └── NVIDIA ドライバ（ホスト側でインストール済み）
        ↓ NVIDIA Container Toolkit が仲介
      Docker コンテナ (hanoi-minimal)
        └── CUDA ライブラリ（イメージに含まれる）
              ↓
            PyTorch (torch.cuda.is_available() == True)
```

ホスト側のドライバは1つで、複数のコンテナが共有できる。コンテナ内の CUDA バージョンはドライバとは独立して選べる（ただし上限あり）。

## docker-compose.yml の GPU 設定

```yaml
hanoi-minimal:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: all           # 全 GPU を使う（"1" にすると1枚のみ）
            capabilities: [gpu]  # GPU 機能を要求
```

この設定が `docker run --gpus all` と等価。

実際の適用確認（`docker inspect` の結果）：
```json
"DeviceRequests": [
  {
    "Driver": "nvidia",
    "Count": -1,       // -1 = all
    "Capabilities": [["gpu"]]
  }
]
```

## CUDA バージョンの関係

```
ホスト NVIDIA ドライバ
    ↓ 対応する最大 CUDA バージョンが決まる
イメージの CUDA バージョン（Dockerfile の FROM）
    nvidia/cuda:12.8.0-devel-ubuntu22.04
    ↓
コンテナ内の PyTorch（CUDA 12.8 対応ホイール）
    torch==2.x.x+cu128
```

**制約**：ホストドライバが対応する最大 CUDA バージョン以上のイメージは動かない。
ドライバのバージョンは `nvidia-smi` で確認できる。

```bash
# ホスト側
nvidia-smi
# → CUDA Version: 12.8  ← このバージョン以下のイメージが動く

# コンテナ内から確認
docker compose exec hanoi-minimal nvidia-smi
docker compose exec hanoi-minimal python3 -c "import torch; print(torch.cuda.is_available())"
```

## ベースイメージの選択

```dockerfile
FROM nvidia/cuda:12.8.0-devel-ubuntu22.04
```

| タグ | 含まれるもの | サイズ | 用途 |
|---|---|---|---|
| `base` | CUDA ランタイムのみ | 最小 | 推論のみ、自前でライブラリを追加 |
| `runtime` | ランタイム + cuDNN | 中 | 多くの推論ユースケース |
| `devel` | runtime + コンパイラ + ヘッダ | 大 | ライブラリのビルドが必要なとき |

**このプロジェクトが `devel` を選ぶ理由：**
`bitsandbytes`（4-bit 量子化ライブラリ）が CUDA のコンパイラヘッダを必要とするため。
`runtime` だとビルド時に失敗する。

## PyTorch の CUDA ホイール

```dockerfile
RUN pip3 install torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cu128
```

`cu128` は CUDA 12.8 対応版。PyTorch の公式 PyPI には CUDA 対応版がないため、
専用インデックスを指定する必要がある。

| ホイール識別子 | 対応 CUDA |
|---|---|
| `cu118` | CUDA 11.8 |
| `cu121` | CUDA 12.1 |
| `cu124` | CUDA 12.4 |
| `cu128` | CUDA 12.8（このプロジェクト） |

## NF4 量子化と VRAM

`run_scaling_sweep.sh` で VRAM 事前検証を行っているのはこの制約のため。

モデルを NF4 4-bit で量子化すると重みのメモリ使用量が 1/4 になる：

```
DeepSeek-R1-Distill-Qwen-7B（fp16）: ~14 GB
                           （NF4）:  ~3.5 GB  ← bitsandbytes で量子化
+ KV キャッシュ（生成トークン数に比例）
```

コンテナ内での VRAM 確認：

```python
import torch
free_bytes, total_bytes = torch.cuda.mem_get_info(0)
print(f"空き: {free_bytes/1e9:.1f} GB / 合計: {total_bytes/1e9:.1f} GB")
```

```bash
# コンテナ外から確認
docker compose exec hanoi-minimal nvidia-smi \
    --query-gpu=name,memory.total,memory.used,memory.free \
    --format=csv,noheader
```

## 複数 GPU の使い分け

`--device cuda:1` で使用する GPU を指定できる（`run_hf.py` の `--device` オプション）：

```bash
# GPU 0 で実験
python3 runners/run_hf.py --N 4 --temperature 0.6 --device cuda:0

# GPU 1 で別の実験を並列実行
python3 runners/run_hf.py --N 5 --temperature 0.8 --device cuda:1
```

`count: all` により全 GPU がコンテナに公開されているため、両方使える。
