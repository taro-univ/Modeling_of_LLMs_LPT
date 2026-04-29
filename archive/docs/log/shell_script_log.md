# Shell Script Log

Claude Codeが実行したShell Scriptの自動ログ。

---

## 2026-04-23 20:41:40

```bash
cat /home/shona/Modeling_of_LLMs_LPT/db/init.sql && echo "---" && cat /home/shona/Modeling_of_LLMs_LPT/db/sync.sh && echo "---" && cat /home/shona/Modeling_of_LLMs_LPT/db/sync_one.py
```

## 2026-04-23 20:47:32

```bash
find /home/shona/Modeling_of_LLMs_LPT -name "*.sh" | sort
```

## 2026-04-23 20:47:35

```bash
cat /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_temp_sweep.sh && echo "===" && cat /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_phase_diagram.sh
```

## 2026-04-23 20:47:38

```bash
cat /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_pq_sweep.sh && echo "===" && cat /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_scaling_sweep.sh
```

## 2026-04-26 20:02:49

```bash
ls /home/shona/Modeling_of_LLMs_LPT/runners/scripts/ && grep -r "run_hf" /home/shona/Modeling_of_LLMs_LPT/ --include="*.sh" --include="*.py" --include="*.md" -l
```

## 2026-04-26 20:02:53

```bash
grep -n "run_hf" /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_temp_sweep.sh /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_phase_diagram.sh /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_pq_sweep.sh /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_scaling_sweep.sh /home/shona/Modeling_of_LLMs_LPT/db/import_existing.py
```

## 2026-04-26 20:03:20

```bash
sed -i 's|runners/run_hf\.py|runners/run_local.py|g' \
  /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_temp_sweep.sh \
  /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_phase_diagram.sh \
  /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_pq_sweep.sh \
  /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_scaling_sweep.sh && \
sed -i 's|run_hf\.py|run_local.py|g' \
  /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_scaling_sweep.sh
```

## 2026-04-26 20:03:24

```bash
grep -n "run_hf" /home/shona/Modeling_of_LLMs_LPT/runners/scripts/*.sh
```

## 2026-04-27 13:37:56

```bash
python3 -c "
import numpy as np

hidden_size = 4096
num_moves   = 3
capture_layers = {'layer_top': -1, 'layer_mid': -16, 'layer_low': -24}

# 正常ケース
hs = {k: np.random.randn(num_moves, hidden_size).astype(np.float32) for k in capture_layers}

# T4-1
assert set(hs.keys()) == set(capture_layers.keys()), 'T4-1 失敗'
print('T4-1 OK')

# T4-2
for k, arr in hs.items():
    assert arr.shape == (num_moves, hidden_size), f'T4-2 失敗: {k}'
print('T4-2 OK')

# T4-3
for k, arr in hs.items():
    assert np.isfinite(arr).all(), f'T4-3 失敗: {k}'
print('T4-3 OK')

# T4-3 NaN ケース
hs_bad = hs.copy()
hs_bad['layer_top'] = hs_bad['layer_top'].copy()
hs_bad['layer_top'][0, 0] = float('nan')
bad_keys = [k for k, arr in hs_bad.items() if not np.isfinite(arr).all()]
assert bad_keys == ['layer_top'], f'NaN 検出失敗: {bad_keys}'
print('T4-3 NaN 検出 OK:', bad_keys)

# T4-4
move_texts = ['Move 1 from A to C', 'Move 2 from A to B', 'Move 1 from C to B']
move_steps = np.array([10, 25, 40], dtype=np.int32)
assert len(move_texts) == move_steps.shape[0] == num_moves
print('T4-4 OK')

# T4-5
assert '__fallback__' not in move_texts
print('T4-5 OK')
"
```

## 2026-04-29 02:02:48

```bash
cat /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_phase_diagram.sh
```

## 2026-04-29 02:02:58

```bash
grep -n "model.id\|model_id\|--model" /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_phase_diagram.sh
```

## 2026-04-29 02:03:01

```bash
grep -n "model\|MODEL" /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_phase_diagram.sh | head -10
```

## 2026-04-29 02:06:05

```bash
cat /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_pq_sweep.sh
```

## 2026-04-29 02:06:14

```bash
cat /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_scaling_sweep.sh && echo "---" && cat /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_temp_sweep.sh
```

## 2026-04-29 02:08:00

```bash
chmod +x /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_full_sweep.sh
```

## 2026-04-29 13:08:57

```bash
find /home/shona/Modeling_of_LLMs_LPT -not -path "*/archive/*" -not -path "*/__pycache__/*" -not -path "*/.git/*" -not -path "*/results/*" -not -path "*/figures/*" \( -name "*.sh" -o -name "*.py" -o -name "*.md" \) | sort
```

## 2026-04-29 13:08:58

```bash
ls /home/shona/Modeling_of_LLMs_LPT/archive/ 2>/dev/null && echo "---" && find /home/shona/Modeling_of_LLMs_LPT/archive -name "*.sh" -o -name "*.py" -o -name "*.md" 2>/dev/null | sort
```

## 2026-04-29 13:09:03

```bash
head -5 /home/shona/Modeling_of_LLMs_LPT/docs/run_hf_design.md && echo "---" && head -5 /home/shona/Modeling_of_LLMs_LPT/docs/test_model_architecture_plan.md && echo "---" && head -3 /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_temp_sweep.sh && echo "---" && head -3 /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_phase_diagram.sh && echo "---" && head -3 /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_pq_sweep.sh
```

## 2026-04-29 13:09:04

```bash
grep -l "run_hf\|run_phase_diagram\|run_pq_sweep\|run_temp_sweep\|run_scaling_sweep" /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_full_sweep.sh /home/shona/Modeling_of_LLMs_LPT/CLAUDE.md /home/shona/Modeling_of_LLMs_LPT/docs/*.md 2>/dev/null
```

## 2026-04-29 13:09:12

```bash
grep -rn "analyze_temp_sweep\|plot_scaling\|analyze_slowing\|import_existing\|sync_one" /home/shona/Modeling_of_LLMs_LPT --include="*.py" --include="*.sh" --include="*.md" | grep -v archive | grep -v "__pycache__"
```

