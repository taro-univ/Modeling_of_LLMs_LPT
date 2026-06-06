# 02 Dockerfile：イメージのビルド手順

Dockerfile はイメージを作る「レシピ」。各命令が1つの**レイヤー**になり、
変更がなければキャッシュが再利用される。

## このプロジェクトの Dockerfile

```dockerfile
FROM nvidia/cuda:12.8.0-devel-ubuntu22.04
```

### FROM — ベースイメージの指定

全ての Dockerfile は既存イメージをベースに始まる。

```dockerfile
FROM nvidia/cuda:12.8.0-devel-ubuntu22.04
#    ^^^^^^^^^^^^^^^^  ^^^^^^^^^^^^^^^^^^^
#    イメージ名         タグ（バージョン）
```

`nvidia/cuda:12.8.0-devel-ubuntu22.04` は NVIDIA 公式イメージで：
- Ubuntu 22.04 をベース OS として含む
- CUDA 12.8 のコンパイラ・ライブラリが含まれる（`devel` タグ）
- GPU を使うソフトウェアのビルドに必要なヘッダファイルも含まれる

`-devel` vs `-runtime`：
- `-runtime`：CUDA ライブラリのみ（推論だけなら軽量なこちらが多い）
- `-devel`：コンパイラ・ヘッダも含む（`bitsandbytes` のビルドに必要）

---

```dockerfile
ENV DEBIAN_FRONTEND=noninteractive
```

### ENV — 環境変数の設定

ビルド中・コンテナ実行中の両方で有効な環境変数を設定する。

```dockerfile
ENV DEBIAN_FRONTEND=noninteractive
# apt-get install 時に対話的な質問（タイムゾーン選択など）をスキップさせる

ENV MPLBACKEND=Agg
# matplotlib がディスプレイなしでも動くようにする（ヘッドレス環境）
# GUI ウィンドウを開こうとしてエラーになるのを防ぐ

ENV PYTHONPATH=/app
# Python のモジュール検索パスに /app を追加
# PYTHONPATH=. python3 analysis/... と同じ効果
```

---

```dockerfile
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*
```

### RUN — コマンドの実行

ビルド時に一度だけ実行され、結果がレイヤーとして固定される。

- `apt-get update && apt-get install -y` はセットで書く（別 RUN にするとキャッシュの問題が起きる）
- `&& rm -rf /var/lib/apt/lists/*` はキャッシュを削除してイメージサイズを削減
- `\` で複数行に折り返す（Shell_Explanation/05 参照）

---

```dockerfile
WORKDIR /app
```

### WORKDIR — 作業ディレクトリの設定

以降の `RUN`・`COPY`・`CMD` の実行ディレクトリを設定する。
コンテナに入ったとき（`docker compose exec hanoi-minimal bash`）の初期ディレクトリにもなる。

---

```dockerfile
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
```

### COPY — ファイルをイメージに追加

```dockerfile
COPY <ホスト側のパス> <コンテナ内のパス>
COPY requirements.txt .    # カレント（WORKDIR=/app）にコピー
```

**`requirements.txt` だけを先にコピーする理由（キャッシュ効率化）：**

```
COPY requirements.txt .       ← このレイヤーは requirements.txt が変わるまでキャッシュ
RUN pip3 install ...           ← 同じく変わらなければキャッシュ（pip install は重い）
（後でソースコードをコピーしても pip install は再実行されない）
```

もし `COPY . .` を先に書くと、ソースコードを1行変えるだけで `pip install` が毎回走ってしまう。

---

```dockerfile
RUN pip3 install --no-cache-dir \
    torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cu128
```

**PyTorch を別の RUN で入れる理由：**

- `requirements.txt` の `torch`（プレースホルダー）を CUDA 12.8 対応ホイールで上書きする
- `--index-url` で PyTorch の専用インデックスを指定（公式 PyPI には CUDA 対応版がない）
- `cu128` は CUDA 12.8 対応ホイールの識別子

## レイヤーキャッシュのしくみ

```
Layer 1: FROM nvidia/cuda:...            ← ほぼ変わらない（キャッシュ有効）
Layer 2: ENV DEBIAN_FRONTEND=...
Layer 3: RUN apt-get install ...         ← ほぼ変わらない
Layer 4: ENV MPLBACKEND=Agg / WORKDIR
Layer 5: COPY requirements.txt .        ← requirements.txt が変わったら以降を再実行
Layer 6: RUN pip3 install requirements  ← ↑の変更に連動して再実行
Layer 7: RUN pip3 install torch (CUDA)  ← ↑の変更に連動して再実行
```

`docker compose up --build` でリビルドするとき、変更があったレイヤーより下だけ再実行される。
