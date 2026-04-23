FROM nvidia/cuda:12.8.0-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

# -------------------------------------------------------
# System packages
# -------------------------------------------------------
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# -------------------------------------------------------
# Environment variables
# -------------------------------------------------------
ENV MPLBACKEND=Agg
ENV PYTHONPATH=/app

WORKDIR /app

# -------------------------------------------------------
# 最小実験用 Python 依存パッケージ (torch はローカル用プレースホルダ)
# -------------------------------------------------------
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# -------------------------------------------------------
# PyTorch (CUDA 12.8 対応ホイール) — requirements.txt の torch を上書き
# -------------------------------------------------------
RUN pip3 install --no-cache-dir \
    torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cu128
