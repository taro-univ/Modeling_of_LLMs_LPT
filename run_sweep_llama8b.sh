#!/bin/bash
# Sweep runner for DeepSeek-R1-Distill-Llama-8B
# T grid: 0.1 ~ 1.0 (step 0.1), N=2~6  — same as qwen-7b / qwen-14b
# Run this INSIDE the container: bash /app/run_sweep_llama8b.sh
cd /app
mkdir -p /app/logs
export PYTHONPATH=/app
bash runners/scripts/run_full_sweep.sh \
    --models 'deepseek-ai/DeepSeek-R1-Distill-Llama-8B' \
    --ts '0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1.0' \
    --trials 25 \
    --analyze \
    > /app/logs/sweep_llama8b.log 2>&1
echo "EXIT_CODE=$?" >> /app/logs/sweep_llama8b.log
