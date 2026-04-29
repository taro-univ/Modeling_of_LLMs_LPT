## 2026-04-29 13:11:09

```bash
\
mkdir -p archive/runners/scripts archive/docs/log archive/analysis archive/db && \
mv runners/scripts/run_phase_diagram.sh archive/runners/scripts/ && \
mv runners/scripts/run_pq_sweep.sh      archive/runners/scripts/ && \
mv runners/scripts/run_temp_sweep.sh    archive/runners/scripts/ && \
mv docs/run_hf_design.md               archive/docs/ && \
mv docs/test_model_architecture_plan.md archive/docs/ && \
mv analysis/analyze_temp_sweep.py       archive/analysis/ && \
mv db/import_existing.py                archive/db/ && \
mv docs/log/bash_log.md                archive/docs/log/ && \
mv docs/log/python_log.md              archive/docs/log/ && \
mv docs/log/shell_script_log.md        archive/docs/log/ && \
mv docs/log/sql_log.md                 archive/docs/log/ && \
echo "完了"
```

## 2026-04-29 13:12:47

```bash
git commit -m "$(cat <<'EOF'
refactor: archive obsolete scripts/docs and add full_sweep runner

- Add runners/scripts/run_full_sweep.sh integrating phase diagram and P(q) sweep with model sweep support
- Archive run_phase_diagram.sh, run_pq_sweep.sh, run_temp_sweep.sh (superseded by run_full_sweep.sh)
- Archive docs/run_hf_design.md (run_hf.py never existed; replaced by run_local.py)
- Archive docs/test_model_architecture_plan.md (plan executed; runbook is the living doc)
- Archive analysis/analyze_temp_sweep.py, db/import_existing.py, docs/log/*.md
- Fix torchvision CUDA version mismatch: cu128 -> cu130 in Dockerfile
- Pin transformers<5.0.0 in requirements.txt to avoid breaking changes
- Fix run_local.py: add trust_remote_code=True, dtype kwarg, disable_goal_stop flag
- Fix test_model_architecture.py: disable goal_reached stop in shared trial
- Add experiment_ideas.md entries for Algorithm E and Collapse-Phase Sweep
- Add initial full_sweep results for DeepSeek-R1-Distill-Qwen-7B (N=2,3 summary/meta)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

## 2026-04-29 13:16:34

```bash
git add README.md && git commit -m "$(cat <<'EOF'
docs: rewrite README with current experiment status and fixed table rendering

- Fix LaTeX math in table header causing render error (use backtick instead)
- Update experiment status: N=2 complete (acc=0.80), N=3 in progress (acc=0.52)
- Reflect current design: n-shot=0, T=0.1-1.0, run_full_sweep.sh as main runner
- Add all 5 tested models with VRAM info
- Update file structure to match archive cleanup
- Add phased roadmap (Phase 1-3) and implementation candidates

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)" && git push
```

