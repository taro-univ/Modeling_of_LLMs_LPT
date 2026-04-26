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

