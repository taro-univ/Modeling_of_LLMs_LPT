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

## 2026-04-29 13:11:14

```bash
find /home/shona/Modeling_of_LLMs_LPT/archive -not -path "*/.git/*" | sort
```

## 2026-04-29 13:12:18

```bash
git status && echo "---" && git log --oneline -3
```

## 2026-04-29 13:12:28

```bash
git add -A && git status --short
```

## 2026-04-29 13:12:35

```bash
cat /home/shona/Modeling_of_LLMs_LPT/.gitignore 2>/dev/null || echo "no .gitignore"
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

## 2026-04-29 13:12:51

```bash
git push
```

## 2026-04-29 13:14:50

```bash
python3 -c "
import json, glob
data = []
for f in glob.glob('/home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/**/*.json', recursive=True):
    try:
        rows = json.load(open(f))
        if isinstance(rows, list):
            data.extend(rows)
    except: pass
from collections import defaultdict
by_N = defaultdict(list)
for r in data:
    by_N[r.get('N')].append(r.get('accuracy',0))
print('完了セル数:', len(glob.glob('/home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/**/summary.json', recursive=True)))
print('総試行数:', len(data))
for N in sorted(by_N):
    accs = by_N[N]
    print(f'  N={N}: {len(accs)}試行  avg_acc={sum(accs)/len(accs):.2f}')
"
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

## 2026-04-29 13:49:04

```bash
find /home/shona/Modeling_of_LLMs_LPT/results -name "summary.json" | head -20
```

## 2026-04-29 13:49:08

```bash
find /home/shona/Modeling_of_LLMs_LPT/results -name "summary.json" | grep -E "N5|N4" | head -20
```

## 2026-04-29 13:49:10

```bash
cat /home/shona/Modeling_of_LLMs_LPT/results/hanoi/phase_diagram/N5_T2_0/summary.json | python3 -c "
import json,sys
data=json.load(sys.stdin)
tokens=[d.get('total_tokens',0) for d in data]
thinking=[d.get('reasoning_tokens',0) for d in data]
es=[d.get('early_stop','') for d in data]
print(f'trials={len(data)}')
print(f'total_tokens: min={min(tokens)} avg={sum(tokens)//len(tokens)} max={max(tokens)}')
print(f'thinking_tokens: avg={sum(thinking)//len(thinking)} max={max(thinking)}')
print(f'early_stop counts: {dict((e, es.count(e)) for e in set(es))}')
"
```

## 2026-04-29 14:26:15

```bash
for f in /home/shona/Modeling_of_LLMs_LPT/results/hanoi/phase_diagram/N5_T*/summary.json; do
    T=$(echo $f | grep -oP 'T[\d_]+' | tr '_' '.')
    python3 -c "
import json
data=json.load(open('$f'))
tokens=[d.get('total_tokens',0) for d in data]
acc=[d.get('accuracy',0) for d in data]
es=[str(d.get('early_stop','')) for d in data]
print(f'$T  n={len(data)}  acc={sum(acc)/len(acc):.2f}  tok_max={max(tokens)}  tok_avg={sum(tokens)//len(tokens)}  es={dict((e,es.count(e)) for e in set(es))}')
"
done
```

## 2026-04-29 14:26:28

```bash
for f in /home/shona/Modeling_of_LLMs_LPT/results/hanoi/phase_diagram/N3_T*/summary.json; do
    T=$(echo $f | grep -oP 'T[\d_]+' | tr '_' '.')
    python3 -c "
import json
data=json.load(open('$f'))
# Filter successful trials
success=[d for d in data if d.get('accuracy')==1]
if success:
    tokens=[d.get('total_tokens',0) for d in success]
    print(f'$T  success={len(success)}/{len(data)}  tok_max={max(tokens)}  tok_avg={sum(tokens)//len(tokens)}')
"
done
```

## 2026-04-29 14:26:48

```bash
grep -n "num_predict\|max_new_tokens\|calc_num\|4096\|8192" /home/shona/Modeling_of_LLMs_LPT/runners/run_local.py | head -30
```

## 2026-04-29 17:07:55

```bash
wc -l /home/shona/Modeling_of_LLMs_LPT/docs/Collapse-Phase_Sweep_plan.md && grep "^### Step\|^## " /home/shona/Modeling_of_LLMs_LPT/docs/Collapse-Phase_Sweep_plan.md
```

## 2026-04-30 01:10:37

```bash
grep "TS_STR" /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_full_sweep.sh
```

## 2026-04-30 01:10:39

```bash
find results/hanoi/full_sweep -name "summary.json" | sort | sed 's|results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/||'
```

## 2026-04-30 01:15:09

```bash
ls /home/shona/Research_LLM/envs/
```

## 2026-04-30 01:33:55

```bash
python3 -c "
import math
puzzles = {
    'Hanoi':   {n: 2**n - 1 for n in range(2, 7)},
    'Frog':    {n: n*n + 2*n for n in range(1, 6)},
    'Pancake': {3:3, 4:4, 5:5, 6:7, 7:8, 8:9},  # pancake numbers p(n)
}
print('=== LoCM 対応表 ===')
for puzzle, table in puzzles.items():
    for n, moves in table.items():
        locm = math.log2(moves)
        print(f'{puzzle:8s} N={n}: {moves:3d} moves  LoCM={locm:.2f}')
    print()
"

```

## 2026-04-30 01:39:44

```bash
python3 - <<'EOF'
from collections import deque

def min_moves_river(N, capacity):
    """BFS for missionaries and cannibals"""
    start = (N, N, True)
    goal = (0, 0, False)
    if start == goal:
        return 0
    
    def neighbors(state):
        lm, lc, boat_left = state
        rm, rc = N - lm, N - lc
        nxt = []
        for m in range(capacity + 1):
            for c in range(capacity + 1):
                if m + c == 0 or m + c > capacity:
                    continue
                if boat_left:
                    if m > lm or c > lc: continue
                    nl, nc = lm - m, lc - c
                    nr, nrc = rm + m, rc + c
                    nb = False
                else:
                    if m > rm or c > rc: continue
                    nl, nc = lm + m, lc + c
                    nr, nrc = rm - m, rc - c
                    nb = True
                # safety check
                if nl > 0 and nc > nl: continue
                if nr > 0 and nrc > nr: continue
                nxt.append((nl, nc, nb))
        return nxt
    
    visited = {start}
    q = deque([(start, 0)])
    while q:
        cur, d = q.popleft()
        for nxt in neighbors(cur):
            if nxt == goal: return d + 1
            if nxt not in visited:
                visited.add(nxt)
                q.append((nxt, d + 1))
    return -1  # unsolvable

import math
print("N  cap  moves  LoCM   solvable")
for N in [2, 3, 4, 5]:
    for cap in [2, 3, 4]:
        m = min_moves_river(N, cap)
        if m > 0:
            print(f"N={N}  cap={cap}  moves={m:3d}  LoCM={math.log2(m):.2f}  ✓")
        else:
            print(f"N={N}  cap={cap}  moves= —              ✗ unsolvable")
    print()
EOF

```

## 2026-04-30 07:13:47

```bash
ls results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/ | grep N6
```

## 2026-04-30 07:13:56

```bash
ls results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/N6_T0_3/
```

## 2026-04-30 07:15:59

```bash
python3 -c "
import numpy as np
d = np.load('results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/N6_T0_1/trial_001_hidden.npz', allow_pickle=True)
print('keys:', list(d.keys()))
for k in d.keys():
    arr = d[k]
    print(f'{k}: shape={arr.shape}, dtype={arr.dtype}')
"

```

## 2026-04-30 07:16:58

```bash
python3 analysis/cosine_sim_phase.py
```

## 2026-04-30 13:32:15

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/ | head -30
```

## 2026-04-30 13:32:15

```bash
ls /home/shona/Modeling_of_LLMs_LPT/analysis/
```

## 2026-04-30 13:32:18

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/ | wc -l && ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/ | tail -10
```

## 2026-04-30 13:32:19

```bash
cat /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/N3_T0_7/summary.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d[:2], indent=2))"
```

## 2026-04-30 13:32:30

```bash
grep -n "default\|argparse\|dir\|base_dir" /home/shona/Modeling_of_LLMs_LPT/analysis/analyze_phase_diagram.py | head -20
```

## 2026-04-30 13:32:31

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/N3_T0_7/
```

## 2026-04-30 13:32:50

```bash
docker compose ps
```

## 2026-04-30 13:40:18

```bash
python3 -c "import numpy as np; d = np.load('/home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/N3_T0_7/trial_001_hidden.npz', allow_pickle=True); print(list(d.keys()))"
```

## 2026-04-30 13:49:34

```bash
grep "no_move_ratio" /home/shona/Modeling_of_LLMs_LPT/runners/run.py
```

## 2026-04-30 13:51:41

```bash
grep -n "stagnation" /home/shona/Modeling_of_LLMs_LPT/runners/run.py
```

## 2026-04-30 13:55:08

```bash
grep -n "stagnation\|chunk_count\|last_move_chunk\|prev_n_moves" /home/shona/Modeling_of_LLMs_LPT/runners/run.py
```

## 2026-04-30 13:57:53

```bash
ls /home/shona/Modeling_of_LLMs_LPT/tests/ 2>/dev/null || echo "NOT FOUND"
```

## 2026-04-30 14:01:02

```bash
diff /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_full_sweep.sh /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_collapse_phase_sweep.sh
```

## 2026-04-30 14:05:35

```bash
bash /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_collapse_phase_sweep.sh --dry-run 2>&1 | head -15
```

## 2026-04-30 14:07:04

```bash
bash /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_collapse_phase_sweep.sh --dry-run 2>&1 | head -12
```

