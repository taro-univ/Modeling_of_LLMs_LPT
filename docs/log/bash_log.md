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

## 2026-04-30 18:40:13

```bash
for f in results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b/N3_T*/summary.json; do echo "=== $f ==="; cat "$f" | python3 -c "
import json,sys
data=json.load(sys.stdin)
early_stops=[d.get('early_stop') for d in data]
from collections import Counter
c=Counter(early_stops)
print('early_stop counts:', dict(c))
print('num_moves mean:', round(sum(d.get('num_moves',0) for d in data)/len(data),1))
"; done 2>/dev/null
```

## 2026-04-30 18:40:17

```bash
cat results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b/N3_T2_5/summary.json 2>/dev/null | python3 -c "
import json,sys
data=json.load(sys.stdin)
from collections import Counter
c=Counter(d.get('early_stop') for d in data)
print('T=2.5 early_stop:', dict(c))
" 2>/dev/null || echo "T2_5: summary.json not yet available"
```

## 2026-04-30 18:40:38

```bash
for f in results/hanoi/deepseek-r1-distill-qwen-7b/N3_*/summary.json; do
  T=$(echo $f | grep -oP 'T[\d_]+' | head -1)
  echo -n "$T: "
  cat "$f" | python3 -c "
import json,sys
data=json.load(sys.stdin)
from collections import Counter
c=Counter(d.get('early_stop') for d in data)
print(dict(c))
"
done 2>/dev/null | sort
```

## 2026-04-30 18:40:45

```bash
python3 -c "
import json, glob
from collections import Counter

files = sorted(glob.glob('results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/N3_T*/summary.json'))
files += sorted(glob.glob('results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b/N3_T*/summary.json'))

print(f'{'T':>6}  {'loop':>5}  {'no_move':>7}  {'goal':>5}  {'none':>5}  {'n':>4}')
print('-'*45)
for f in files:
    T_str = f.split('N3_T')[1].split('/')[0].replace('_','.')
    try:
        T = float(T_str)
    except:
        continue
    data = json.load(open(f))
    c = Counter(d.get('early_stop') for d in data)
    n = len(data)
    print(f'{T:>6.1f}  {c[\"move_loop_repeat\"]:>5}  {c[\"no_move_catchall\"]:>7}  {c[\"goal_reached\"]:>5}  {c[None]:>5}  {n:>4}')
"

```

## 2026-04-30 18:45:10

```bash
python3 -c "
import json, glob
from collections import Counter

files = sorted(glob.glob('results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/N3_T*/summary.json'))
files += sorted(glob.glob('results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b/N3_T*/summary.json'))

print(f'{'T':>5}  {'p_goal':>7}  {'p_loop':>7}  {'p_PM':>7}  notes')
print('-'*55)
for f in files:
    T_str = f.split('N3_T')[1].split('/')[0].replace('_','.')
    try: T = float(T_str)
    except: continue
    data = json.load(open(f))
    c = Counter(d.get('early_stop') for d in data)
    n = len(data)
    # Noneのnum_moves分布確認
    none_moves = [d.get('num_moves',0) for d in data if d.get('early_stop') is None]
    avg_none_moves = sum(none_moves)/len(none_moves) if none_moves else 0
    p_goal = c['goal_reached']/n
    p_loop = c['move_loop_repeat']/n
    p_pm = (c['no_move_catchall'] + c[None])/n  # NoneはPM扱い仮定
    note = f'none_avg_moves={avg_none_moves:.1f}' if none_moves else ''
    print(f'{T:>5.1f}  {p_goal:>7.3f}  {p_loop:>7.3f}  {p_pm:>7.3f}  {note}')
"

```

## 2026-04-30 18:47:24

```bash
ls docs/
```

## 2026-04-30 21:37:58

```bash
python3 -m py_compile analysis/analyze_pq.py && echo "OK"
```

## 2026-04-30 21:41:34

```bash
python3 -m py_compile analysis/analyze_pq.py && echo "OK"
```

## 2026-05-01 09:21:13

```bash
docker compose ps 2>/dev/null && docker compose exec hanoi-minimal bash -c "ps aux | grep python | grep -v grep" 2>/dev/null || echo "コンテナ未起動またはエラー"
```

## 2026-05-01 09:22:14

```bash
docker compose exec hanoi-minimal bash -c "nvidia-smi" 2>/dev/null
```

## 2026-05-01 09:22:24

```bash
docker compose exec hanoi-minimal bash -c "ls -lt results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b/N6_T1_5/ 2>/dev/null | head -5"
```

## 2026-05-01 09:22:25

```bash
grep -r "device_map\|load_in\|torch_dtype\|use_cache" /home/shona/Modeling_of_LLMs_LPT/runners/run_local.py 2>/dev/null | head -20
```

## 2026-05-01 09:22:30

```bash
grep -n "device_map\|load_in\|device\|BitsAndBytes\|quantization" /home/shona/Modeling_of_LLMs_LPT/runners/run_local.py | head -30
```

## 2026-05-01 17:46:17

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b/ | head -20
```

## 2026-05-01 17:46:22

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b/N3_T1_1/
```

## 2026-05-01 17:46:29

```bash
python3 -c "
import numpy as np
d = np.load('results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b/N3_T1_1/trial_001_hidden.npz', allow_pickle=True)
print('Keys:', list(d.keys()))
"
```

## 2026-05-01 17:53:01

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b/N4_T1_1/ && echo "---" && ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b/N3_T1_3/
```

## 2026-05-01 17:53:03

```bash
python3 -c "
import numpy as np
from pathlib import Path
base = Path('results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b')
for tag in ['N3_T1_1','N3_T1_3','N3_T1_4','N3_T1_8','N3_T2_5','N3_T3_0']:
    npzs = list((base/tag).glob('trial_*_hidden.npz'))
    if npzs:
        d = np.load(npzs[0], allow_pickle=True)
        print(tag, 'keys:', list(d.keys()))
    else:
        print(tag, 'NO NPZ')
"
```

## 2026-05-01 17:55:12

```bash
python3 -c "
import numpy as np
from pathlib import Path
base = Path('results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b')
# N4の確認
d = np.load(base/'N4_T1_1/trial_001_hidden.npz', allow_pickle=True)
print('N4 keys:', list(d.keys()))
# load_conditionのシミュレーション
for N in [3,4,5,6]:
    tag = '1_1'
    cdir = base / f'N{N}_T{tag}'
    npzs = sorted(cdir.glob('trial_*_hidden.npz'))
    hidden = []
    for npz in npzs:
        d = np.load(npz, allow_pickle=True)
        if 'layer_mid' not in d:
            print(f'N{N} T1_1: layer_mid MISSING in', npz.name)
        else:
            hidden.append(d['layer_mid'].shape)
    print(f'N{N} T1_1: {len(hidden)} trials loaded')
"
```

## 2026-05-01 17:55:12

```bash
stat -c "%y %n" /home/shona/Modeling_of_LLMs_LPT/figures/pq_dist.png /home/shona/Modeling_of_LLMs_LPT/figures/pq_summary.png
```

## 2026-05-01 17:55:55

```bash
python3 -c "
import json, sys
sys.path.insert(0, '.')
from pathlib import Path
import numpy as np

base = Path('results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b')
ns = [3,4,5,6]
ts = [1.1,1.2,1.3,1.4,1.5,1.8,2.0,2.5,3.0]

for N in ns:
    for T in ts:
        tag = f'{T:.1f}'.replace('.','_')
        cdir = base / f'N{N}_T{tag}'
        if not cdir.exists():
            print(f'N{N} T{T}: DIR MISSING ({cdir.name})')
            continue
        npzs = sorted(cdir.glob('trial_*_hidden.npz'))
        if not npzs:
            print(f'N{N} T{T}: NO NPZ')
            continue
        d = np.load(npzs[0], allow_pickle=True)
        has_layer = 'layer_mid' in d
        print(f'N{N} T{T}: {len(npzs)} npz, layer_mid={has_layer}')
"

```

## 2026-05-01 17:56:21

```bash
python3 -c "
import json
from pathlib import Path
base = Path('results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b')
for N in [3,4,5,6]:
    s = json.load(open(base/f'N{N}_T1_1/summary.json'))
    acc = sum(r['accuracy'] for r in s)/len(s)
    es = [r.get('early_stop') for r in s]
    from collections import Counter
    print(f'N{N} T1.1: acc={acc:.2f} early_stop={dict(Counter(es))}')
"

```

## 2026-05-01 20:11:28

```bash
python3 analysis/analyze_pq.py --dir results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b --layer layer_mid --ns 3 4 5 6 --ts 1.1 1.2 1.3 1.4 1.5 1.8 2.0 2.5 3.0 2>&1
```

## 2026-05-01 20:15:19

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b/ | sort
```

## 2026-05-01 20:15:19

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/ 2>/dev/null
```

## 2026-05-01 20:15:21

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/ 2>/dev/null | head -30
```

## 2026-05-01 20:15:22

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/phase_diagram/ 2>/dev/null | sort | head -30
```

## 2026-05-01 20:15:25

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/phase_diagram/ | sort | tail -20
```

## 2026-05-01 20:15:25

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/ | sort
```

## 2026-05-01 20:16:00

```bash
ls /home/shona/Modeling_of_LLMs_LPT/analysis/
```

## 2026-05-01 20:16:01

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/pq_sweep/ 2>/dev/null | sort
```

## 2026-05-01 20:16:19

```bash
grep -n "Tc\|T_c\|boundary\|threshold\|0\.5\|interpolat" /home/shona/Modeling_of_LLMs_LPT/analysis/analyze_phase_diagram.py | head -40
```

## 2026-05-01 20:16:38

```bash
grep -n "dir\|path\|full_sweep\|phase_diagram\|collapse" /home/shona/Modeling_of_LLMs_LPT/analysis/analyze_phase_diagram.py | head -20
```

## 2026-05-01 20:16:39

```bash
grep -n "load\|summary\|accuracy" /home/shona/Modeling_of_LLMs_LPT/analysis/analyze_phase_diagram.py | head -20
```

## 2026-05-01 20:16:59

```bash
for N in 4 5 6; do
  echo "=== N=$N ==="
  for dir in /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/N${N}_T*/; do
    T=$(basename $dir | sed 's/N[0-9]*_T//' | sed 's/_/./')
    if [ -f "$dir/summary.json" ]; then
      acc=$(python3 -c "import json; d=json.load(open('$dir/summary.json')); print(f'T={$T}: acc={sum(r[\"accuracy\"] for r in d)/len(d):.2f} n={len(d)}')" 2>/dev/null)
      echo "  $acc"
    fi
  done
done
```

## 2026-05-01 20:23:32

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b/N3_T1_1/ 2>/dev/null
```

## 2026-05-01 20:23:33

```bash
python3 -c "
import json
from pathlib import Path

base = Path('results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b')
d = json.load(open(base / 'N3_T1_1/summary.json'))
print(d[0])
"
```

## 2026-05-01 20:23:37

```bash
python3 -c "
import numpy as np
d = np.load('results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b/N3_T1_1/trial_001_hidden.npz', allow_pickle=True)
print(list(d.keys()))
"
```

## 2026-05-01 20:23:38

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/N3_T0_1/
```

## 2026-05-01 20:23:42

```bash
python3 -c "
import numpy as np
d = np.load('results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/N3_T0_1/trial_001_hidden.npz', allow_pickle=True)
print(list(d.keys()))
"
```

## 2026-05-01 20:23:43

```bash
python3 -c "
import numpy as np
d = np.load('results/hanoi/pq_sweep/N3_T0_2/trial_001_hidden.npz', allow_pickle=True)
print(list(d.keys()))
"
```

## 2026-05-01 20:23:53

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b/ | grep N2
```

## 2026-05-01 20:23:53

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/ | grep N2
```

## 2026-05-01 20:25:24

```bash
python3 -c "
import json
from pathlib import Path
from collections import Counter

# collapse_phase の early_stop 種別を確認
base = Path('results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b')
es_counts = Counter()
for p in base.glob('*/summary.json'):
    d = json.load(open(p))
    for r in d:
        es_counts[str(r.get('early_stop'))] += 1
print('collapse_phase early_stop:', dict(es_counts))

# full_sweep の early_stop 種別を確認
base2 = Path('results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b')
es2 = Counter()
for p in base2.glob('*/summary.json'):
    d = json.load(open(p))
    for r in d:
        es2[str(r.get('early_stop'))] += 1
print('full_sweep early_stop:', dict(es2))
"

```

## 2026-05-01 20:25:34

```bash
python3 -c "
import json
from pathlib import Path

# None の early_stop の内訳を確認
base = Path('results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b')
none_cases = []
for p in sorted(base.glob('*/summary.json'))[:5]:
    d = json.load(open(p))
    for r in d:
        if r.get('early_stop') is None:
            none_cases.append({'N': r.get('N'), 'T': r.get('temperature'), 'acc': r.get('accuracy'), 'moves': r.get('num_moves')})
for c in none_cases[:5]:
    print(c)
"
```

## 2026-05-01 20:27:58

```bash
python3 -c "
import numpy as np
d = np.load('results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b/N3_T1_1/trial_001_hidden.npz', allow_pickle=True)
print('layer_mid shape:', d['layer_mid'].shape)
print('move_texts:', list(d['move_texts'])[:3])
"
```

## 2026-05-01 20:30:05

```bash
docker compose exec hanoi-minimal python3 analysis/analyze_integrated.py 2>&1
```

## 2026-05-01 20:31:10

```bash
python3 -c "
import json
import numpy as np
from pathlib import Path

base = Path('results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b')
for T_str in ['N2_T0_1','N2_T0_3','N2_T0_5','N2_T0_6','N2_T0_7','N2_T0_8','N2_T0_9','N2_T1_0']:
    p = base / T_str / 'summary.json'
    d = json.load(open(p))
    acc = np.mean([r['accuracy'] for r in d])
    T = T_str.split('_T')[1].replace('_','.')
    print(f'T={T}: acc={acc:.2f}')
"
```

## 2026-05-01 20:31:19

```bash
python3 -c "
import json, numpy as np
from pathlib import Path
base = Path('results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b')
for T_str in ['N3_T0_1','N3_T0_2','N3_T0_3','N3_T0_4','N3_T0_5']:
    d = json.load(open(base/T_str/'summary.json'))
    T = T_str.split('_T')[1].replace('_','.')
    print(f'T={T}: acc={np.mean([r[\"accuracy\"] for r in d]):.2f}')
"
```

## 2026-05-06 09:34:42

```bash
docker compose -f /home/shona/Modeling_of_LLMs_LPT/docker-compose.yml ps 2>/dev/null || docker compose -f /home/shona/Modeling_of_LLMs_LPT/compose.yml ps 2>/dev/null || docker compose ps
```

## 2026-05-06 09:35:15

```bash
find /home -name "*.json" -path "*/deepseek*14*" 2>/dev/null | head -5; ls ~/.cache/huggingface/hub/ 2>/dev/null | grep -i "14\|deepseek" | head -10
```

## 2026-05-06 09:35:28

```bash
grep -E "gpu|nvidia|deploy|runtime|shm" /home/shona/Modeling_of_LLMs_LPT/docker-compose.yml
```

## 2026-05-06 09:35:33

```bash
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>/dev/null
```

## 2026-05-06 09:41:52

```bash
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu --format=csv,noheader,nounits
```

## 2026-05-06 09:54:38

```bash
grep -n "calc_num_predict\|calc_think_budget\|num_predict\|output_hidden_states" /home/shona/Modeling_of_LLMs_LPT/runners/run.py | head -40
```

## 2026-05-06 09:54:39

```bash
grep -n "def calc_num_predict\|def calc_think" /home/shona/Modeling_of_LLMs_LPT/runners/run.py
```

## 2026-05-07 00:20:49

```bash
find /home/shona/Modeling_of_LLMs_LPT/results/hanoi -name "summary.json" -path "*14b*" | sort | head -30
```

## 2026-05-07 00:20:50

```bash
find /home/shona/Modeling_of_LLMs_LPT/results/hanoi -name "summary.json" -path "*7b*" -path "*full_sweep*" | sort | head -20
```

## 2026-05-07 00:20:57

```bash
python3 -c "
import json, glob, os

def get_acc(base, model, N):
    rows = []
    for T_str in ['0_1','0_2','0_3','0_4','0_5','0_6','0_7','0_8','0_9','1_0']:
        path = f'{base}/{model}/N{N}_T{T_str}/summary.json'
        if not os.path.exists(path):
            rows.append(f'T={T_str.replace(\"_\",\".\")}:  ---')
            continue
        d = json.load(open(path))
        acc = sum(r['accuracy'] for r in d) / len(d)
        rows.append(f'T={T_str.replace(\"_\",\".\")}:  {acc:.2f}  (n={len(d)})')
    return rows

base = '/home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep'
for N in [3, 4, 5]:
    print(f'=== N={N} ===')
    r7  = get_acc(base, 'deepseek-r1-distill-qwen-7b',  N)
    r14 = get_acc(base, 'deepseek-r1-distill-qwen-14b', N)
    print(f'{'T':>6}  {'7B':>6}  {'14B':>6}')
    for a, b in zip(r7, r14):
        t   = a.split(':')[0]
        v7  = a.split(':')[1].strip().split()[0]
        v14 = b.split(':')[1].strip().split()[0]
        print(f'{t:>6}  {v7:>6}  {v14:>6}')
    print()
"

```

## 2026-05-07 13:29:41

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/ 2>/dev/null && echo "---" && ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/ 2>/dev/null
```

## 2026-05-07 13:29:45

```bash
find /home/shona/Modeling_of_LLMs_LPT/results -name "summary.json" | grep -i "14b" | head -30
```

## 2026-05-07 13:29:45

```bash
find /home/shona/Modeling_of_LLMs_LPT/results -name "summary.json" | grep -i "7b" | sort | head -30
```

## 2026-05-07 13:29:53

```bash
find /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep -name "summary.json" | sort | head -50
```

## 2026-05-07 13:29:54

```bash
find /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep -name "summary.json" | grep "14b" | wc -l && find /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep -name "summary.json" | grep "7b" | wc -l
```

## 2026-05-07 13:30:07

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-14b/ | head -10
```

## 2026-05-07 13:30:17

```bash
python3 - <<'EOF'
import json
import glob
import re

def parse_dir(dir_name):
    # N3_T0_5 -> N=3, T=0.5; N3_T1_0 -> N=3, T=1.0
    m = re.match(r"N(\d+)_T(\d+)_(\d+)$", dir_name)
    if not m:
        return None, None
    N = int(m.group(1))
    T = float(f"{m.group(2)}.{m.group(3)}")
    return N, T

def load_results(base_path):
    data = {}
    for path in glob.glob(f"{base_path}/N*/summary.json"):
        dir_name = path.split("/")[-2]
        N, T = parse_dir(dir_name)
        if N is None:
            continue
        with open(path) as f:
            summary = json.load(f)
        trials = summary if isinstance(summary, list) else summary.get("trials", [])
        accs = [t["accuracy"] for t in trials if "accuracy" in t]
        if accs:
            data[(N, T)] = (sum(accs) / len(accs), len(accs))
    return data

base_7b  = "results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b"
base_14b = "results/hanoi/full_sweep/deepseek-r1-distill-qwen-14b"

d7  = load_results(base_7b)
d14 = load_results(base_14b)

all_keys = sorted(set(d7.keys()) | set(d14.keys()))

print(f"{'N':>2}  {'T':>5}  {'7B acc':>7}  {'14B acc':>8}  {'Δ(14B-7B)':>10}")
print("-" * 46)
prev_N = None
for N, T in all_keys:
    if prev_N is not None and N != prev_N:
        print()
    a7  = d7.get((N, T), (None, 0))[0]
    a14 = d14.get((N, T), (None, 0))[0]
    s7  = f"{a7:.3f}" if a7 is not None else "  N/A "
    s14 = f"{a14:.3f}" if a14 is not None else "  N/A "
    diff = f"{a14-a7:+.3f}" if (a7 is not None and a14 is not None) else "   N/A"
    print(f"{N:>2}  {T:>5.1f}  {s7:>7}  {s14:>8}  {diff:>10}")
    prev_N = N

# Tc estimation: last T where acc > 0.5
print("\n--- Estimated Tc (last T with mean_acc > 0.5) ---")
for N in sorted(set(k[0] for k in all_keys)):
    tc7 = max((T for (n,T), (acc,_) in d7.items() if n == N and acc > 0.5), default=None)
    tc14 = max((T for (n,T), (acc,_) in d14.items() if n == N and acc > 0.5), default=None)
    print(f"  N={N}: 7B Tc~{tc7}  14B Tc~{tc14}")
EOF

```

## 2026-05-07 13:30:31

```bash
python3 - <<'EOF'
import json
import glob
import re
from collections import Counter

def parse_dir(dir_name):
    m = re.match(r"N(\d+)_T(\d+)_(\d+)$", dir_name)
    if not m:
        return None, None
    return int(m.group(1)), float(f"{m.group(2)}.{m.group(3)}")

def load_early_stop(base_path):
    data = {}
    for path in glob.glob(f"{base_path}/N*/summary.json"):
        dir_name = path.split("/")[-2]
        N, T = parse_dir(dir_name)
        if N is None:
            continue
        with open(path) as f:
            summary = json.load(f)
        trials = summary if isinstance(summary, list) else summary.get("trials", [])
        stops = Counter(t.get("early_stop", "none") for t in trials)
        data[(N, T)] = stops
    return data

def dominant(stops):
    total = sum(stops.values())
    if total == 0:
        return "N/A"
    top = stops.most_common(1)[0]
    return f"{top[0]}({top[1]/total:.0%})"

d7  = load_early_stop("results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b")
d14 = load_early_stop("results/hanoi/full_sweep/deepseek-r1-distill-qwen-14b")

all_keys = sorted(set(d7.keys()) | set(d14.keys()))
print(f"{'N':>2}  {'T':>4}  {'7B dominant stop':>25}  {'14B dominant stop':>25}")
print("-"*65)
prev_N = None
for N, T in all_keys:
    if prev_N is not None and N != prev_N:
        print()
    s7  = dominant(d7.get((N,T), Counter()))
    s14 = dominant(d14.get((N,T), Counter()))
    print(f"{N:>2}  {T:>4.1f}  {s7:>25}  {s14:>25}")
    prev_N = N
EOF

```

## 2026-05-07 23:34:02

```bash
python3 -c "
import json, os, glob

base_fs = '/home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-14b'
base_cp = '/home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b'

print('=== full_sweep (T=0.1~1.0) ===')
for N in [2,3,4,5,6]:
    row = []
    for T_str in ['0_1','0_2','0_3','0_4','0_5','0_6','0_7','0_8','0_9','1_0']:
        p = f'{base_fs}/N{N}_T{T_str}/summary.json'
        if os.path.exists(p):
            d = json.load(open(p))
            row.append(f'{len(d):>3}')
        else:
            row.append('  -')
    print(f'N={N}: {\" \".join(row)}')

print()
print('=== collapse_phase (T=1.1~3.0) ===')
ts = ['1_1','1_2','1_3','1_4','1_5','1_6','1_7','1_8','1_9',
      '2_0','2_1','2_2','2_3','2_4','2_5','2_6','2_7','2_8','2_9','3_0']
for N in [2,3,4,5,6]:
    row = []
    for T_str in ts:
        p = f'{base_cp}/N{N}_T{T_str}/summary.json'
        if os.path.exists(p):
            d = json.load(open(p))
            row.append(f'{len(d):>3}')
        else:
            row.append('  -')
    print(f'N={N}: {\" \".join(row)}')
" 2>/dev/null

```

## 2026-05-07 23:34:03

```bash
ls /home/shona/Modeling_of_LLMs_LPT/analysis/
```

## 2026-05-07 23:34:14

```bash
head -60 /home/shona/Modeling_of_LLMs_LPT/analysis/analyze_phase_diagram.py
```

## 2026-05-07 23:34:14

```bash
head -60 /home/shona/Modeling_of_LLMs_LPT/analysis/analyze_integrated.py
```

## 2026-05-07 23:34:24

```bash
grep -n "argparse\|add_argument\|def main" /home/shona/Modeling_of_LLMs_LPT/analysis/analyze_phase_diagram.py | head -30
```

## 2026-05-07 23:34:25

```bash
grep -n "argparse\|add_argument\|def main" /home/shona/Modeling_of_LLMs_LPT/analysis/analyze_integrated.py | head -30
```

## 2026-05-07 23:34:48

```bash
mkdir -p /home/shona/Modeling_of_LLMs_LPT/figures/integrated/deepseek-r1-distill-qwen-14b && python3 analysis/analyze_integrated.py --model deepseek-r1-distill-qwen-14b --layer layer_top 2>&1
```

## 2026-05-07 23:37:33

```bash
docker compose ps
```

## 2026-05-07 23:37:33

```bash
nvidia-smi --query-gpu=memory.used,memory.free --format=csv,noheader,nounits
```

## 2026-05-07 23:37:51

```bash
docker compose exec hanoi-minimal bash -c "bash runners/scripts/run_collapse_phase_sweep.sh --models 'deepseek-ai/DeepSeek-R1-Distill-Qwen-14B' --trials 30" > /tmp/collapse_14b.log 2>&1
```

## 2026-05-08 05:09:14

```bash
tail -30 /tmp/collapse_14b.log
```

## 2026-05-08 05:09:16

```bash
find /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b -name "summary.json" 2>/dev/null | wc -l
```

## 2026-05-09 00:53:38

```bash
tail -15 /tmp/collapse_14b.log && echo "---" && find /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b -name "summary.json" 2>/dev/null | sort
```

## 2026-05-09 00:54:21

```bash
python3 -c "
import json, os

base = '/home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b'
ts = ['1_1','1_2','1_3','1_4','1_5','1_8','2_0','2_5','3_0']
t_labels = ['1.1','1.2','1.3','1.4','1.5','1.8','2.0','2.5','3.0']

for N in [3, 4, 5]:
    print(f'=== N={N} ===')
    print(f'  {\"T\":>5}  {\"acc\":>5}  {\"goal\":>5}  {\"SG(loop)\":>9}  {\"PM(no_mv)\":>9}  {\"other\":>6}')
    for t_str, t_lab in zip(ts, t_labels):
        p = f'{base}/N{N}_T{t_str}/summary.json'
        if not os.path.exists(p):
            print(f'  {t_lab:>5}  ---')
            continue
        d = json.load(open(p))
        n = len(d)
        acc = sum(r[\"accuracy\"] for r in d) / n
        es = {}
        for r in d:
            k = r.get(\"early_stop\") or \"none\"
            es[k] = es.get(k, 0) + 1
        goal  = es.get(\"goal_reached\", 0)
        sg    = es.get(\"move_loop_repeat\", 0) + es.get(\"move_loop_reverse\", 0)
        pm    = es.get(\"no_move_catchall\", 0) + es.get(\"move_ceiling\", 0)
        other = n - goal - sg - pm
        print(f'  {t_lab:>5}  {acc:>5.2f}  {goal:>5}  {sg:>9}  {pm:>9}  {other:>6}')
    print()
"

```

## 2026-05-09 00:55:13

```bash
python3 -c "
import json, os
from collections import Counter

base = '/home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b'
ts = ['1_1','1_2','1_3','1_4','1_5','1_8','2_0','2_5','3_0']
t_labels = ['1.1','1.2','1.3','1.4','1.5','1.8','2.0','2.5','3.0']

for N in [3, 4, 5]:
    print(f'=== N={N} ===')
    for t_str, t_lab in zip(ts, t_labels):
        p = f'{base}/N{N}_T{t_str}/summary.json'
        if not os.path.exists(p): continue
        d = json.load(open(p))
        known = {'goal_reached','move_loop_repeat','move_loop_reverse','no_move_catchall','move_ceiling'}
        others = Counter()
        for r in d:
            k = r.get('early_stop') or 'none(null)'
            if k not in known:
                others[k] += 1
        if others:
            print(f'  T={t_lab}: {dict(others)}')
    print()
"

```

## 2026-05-09 00:56:01

```bash
grep -n "classify\|none\|null\|early_stop\|phase\|mixed\|paramagnetic\|spin_glass\|ordered" /home/shona/Modeling_of_LLMs_LPT/analysis/analyze_integrated.py | head -60
```

## 2026-05-09 07:18:08

```bash
tail -5 /tmp/collapse_14b.log && echo "---" && find /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b -name "summary.json" 2>/dev/null | wc -l
```

## 2026-05-09 21:19:21

```bash
find /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b -name "summary.json" 2>/dev/null | wc -l && echo "---" && tail -3 /tmp/collapse_14b.log
```

## 2026-05-09 21:24:03

```bash
find /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b -name "summary.json" 2>/dev/null | wc -l && tail -3 /tmp/collapse_14b.log
```

## 2026-05-09 21:28:03

```bash
find /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b -name "summary.json" 2>/dev/null | wc -l && tail -5 /tmp/collapse_14b.log
```

## 2026-05-09 21:28:14

```bash
python3 -c "
import os
base = '/home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b'
ts = ['1_1','1_2','1_3','1_4','1_5','1_8','2_0','2_5','3_0']
t_labels = ['1.1','1.2','1.3','1.4','1.5','1.8','2.0','2.5','3.0']
for N in [3,4,5,6]:
    missing = []
    for t_str, t_lab in zip(ts, t_labels):
        if not os.path.exists(f'{base}/N{N}_T{t_str}/summary.json'):
            missing.append(t_lab)
    status = '✓' if not missing else f'残り {missing}'
    print(f'N={N}: {status}')
"
```

## 2026-05-09 21:33:03

```bash
find /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b -name "summary.json" 2>/dev/null | wc -l
```

## 2026-05-09 21:33:07

```bash
tail -8 /tmp/collapse_14b.log
```

## 2026-05-09 21:38:05

```bash
find /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b -name "summary.json" 2>/dev/null | wc -l && tail -3 /tmp/collapse_14b.log
```

## 2026-05-09 21:38:11

```bash
docker compose exec hanoi-minimal ps aux | grep python | grep -v grep
```

## 2026-05-09 21:38:11

```bash
wc -l /tmp/collapse_14b.log && tail -20 /tmp/collapse_14b.log
```

## 2026-05-09 21:39:44

```bash
python3 analysis/analyze_integrated.py --model deepseek-r1-distill-qwen-14b --layer layer_top 2>&1 | tail -10
```

## 2026-05-09 21:43:05

```bash
find /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b -name "summary.json" 2>/dev/null | wc -l && tail -5 /tmp/collapse_14b.log
```

## 2026-05-10 06:30:15

```bash
wc -l /tmp/collapse_14b.log && docker compose exec hanoi-minimal ps aux | grep python | grep -v grep | awk '{print $1,$2,$11,$12,$13,$14}'
```

## 2026-05-10 06:30:26

```bash
find /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b -name "summary.json" | wc -l
```

## 2026-05-10 06:30:37

```bash
python3 analysis/analyze_integrated.py --model deepseek-r1-distill-qwen-14b --layer layer_top 2>&1 | tail -10
```

## 2026-05-10 06:31:00

```bash
grep -n "boundary\|bc_ns\|bc_Tc\|T_c\|BOUNDARY\|threshold" /home/shona/Modeling_of_LLMs_LPT/analysis/analyze_integrated.py | head -30
```

## 2026-05-10 06:31:28

```bash
python3 -c "
import json, os

base = '/home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-14b'
ts = [0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0]
print(f'  N  |  ' + '  '.join(f'T={t:.1f}' for t in ts))
print('-'*90)
for N in [2,3,4,5,6]:
    accs = []
    for T in ts:
        t_str = f'{T:.1f}'.replace('.','_')
        p = f'{base}/N{N}_T{t_str}/summary.json'
        if os.path.exists(p):
            d = json.load(open(p))
            accs.append(f'{sum(r[\"accuracy\"] for r in d)/len(d):.2f}')
        else:
            accs.append(' --- ')
    print(f'  N={N} | ' + '  '.join(accs))
"
```

## 2026-05-10 06:34:18

```bash
python3 analysis/analyze_integrated.py --model deepseek-r1-distill-qwen-14b --layer layer_top 2>&1 | tail -8
```

## 2026-05-10 06:35:07

```bash
python3 -c "
import json, os
import numpy as np

base_fs = '/home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-14b'
base_cp = '/home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b'
ts_full = [0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0]
ts_cp   = [1.1,1.2,1.3,1.4,1.5,1.8,2.0,2.5,3.0]

TC_THRESHOLD = 0.15

for N in [2,3,4,5,6]:
    ts_v, acc_v = [], []
    for T in ts_full:
        t_str = f'{T:.1f}'.replace('.','_')
        p = f'{base_fs}/N{N}_T{t_str}/summary.json'
        if os.path.exists(p):
            d = json.load(open(p))
            ts_v.append(T); acc_v.append(sum(r['accuracy'] for r in d)/len(d))
    for T in ts_cp:
        t_str = f'{T:.1f}'.replace('.','_')
        p = f'{base_cp}/N{N}_T{t_str}/summary.json'
        if os.path.exists(p):
            d = json.load(open(p))
            ts_v.append(T); acc_v.append(sum(r['accuracy'] for r in d)/len(d))
    Tc = None
    for j in range(len(ts_v)-1):
        if acc_v[j] >= TC_THRESHOLD > acc_v[j+1]:
            slope = (acc_v[j+1]-acc_v[j])/(ts_v[j+1]-ts_v[j])
            Tc = ts_v[j] + (TC_THRESHOLD - acc_v[j])/slope
            break
    print(f'N={N}: T_c={Tc:.3f} (crossing: T={ts_v[j]:.1f} acc={acc_v[j]:.2f} → T={ts_v[j+1]:.1f} acc={acc_v[j+1]:.2f})' if Tc else f'N={N}: T_c=None')

# スケーリング則フィット
ns  = [3, 4]
tcs = []
for N in ns:
    ts_v, acc_v = [], []
    for T in ts_full + ts_cp:
        t_str = f'{T:.1f}'.replace('.','_')
        for base in [base_fs, base_cp]:
            p = f'{base}/N{N}_T{t_str}/summary.json'
            if os.path.exists(p):
                d = json.load(open(p))
                ts_v.append(T); acc_v.append(sum(r['accuracy'] for r in d)/len(d))
                break
    for j in range(len(ts_v)-1):
        if acc_v[j] >= TC_THRESHOLD > acc_v[j+1]:
            slope = (acc_v[j+1]-acc_v[j])/(ts_v[j+1]-ts_v[j])
            tcs.append(ts_v[j] + (TC_THRESHOLD - acc_v[j])/slope)
            break

if len(tcs)==2:
    coeffs = np.polyfit(np.log(ns), np.log(tcs), 1)
    alpha = -coeffs[0]; A = np.exp(coeffs[1])
    print(f'フィット: T_c = {A:.3f} * N^(-{alpha:.3f})')
"

```

## 2026-05-10 06:35:46

```bash
python3 analysis/analyze_integrated.py --model deepseek-r1-distill-qwen-14b --layer layer_top 2>&1 | tail -5
```

## 2026-05-10 06:35:59

```bash
python3 -c "
import json, os, numpy as np

base_fs = '/home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-14b'
base_cp = '/home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b'
ts_all = [0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0,1.1,1.2,1.3,1.4,1.5,1.8,2.0,2.5,3.0]
TC_THRESHOLD = 0.15

tcs = {}
for N in [3,4]:
    ts_v, acc_v = [], []
    for T in ts_all:
        t_str = f'{T:.1f}'.replace('.','_')
        for base in [base_fs, base_cp]:
            p = f'{base}/N{N}_T{t_str}/summary.json'
            if os.path.exists(p):
                d = json.load(open(p))
                ts_v.append(T); acc_v.append(sum(r['accuracy'] for r in d)/len(d))
                break
    for j in range(len(ts_v)-1, 0, -1):
        if acc_v[j-1] >= TC_THRESHOLD > acc_v[j]:
            slope = (acc_v[j]-acc_v[j-1])/(ts_v[j]-ts_v[j-1])
            Tc = ts_v[j-1] + (TC_THRESHOLD - acc_v[j-1])/slope
            tcs[N] = Tc
            print(f'N={N}: T_c={Tc:.3f}  (T={ts_v[j-1]:.1f} acc={acc_v[j-1]:.2f} → T={ts_v[j]:.1f} acc={acc_v[j]:.2f})')
            break

ns = list(tcs.keys()); Tc_arr = [tcs[n] for n in ns]
coeffs = np.polyfit(np.log(ns), np.log(Tc_arr), 1)
print(f'スケーリング則: T_c = {np.exp(coeffs[1]):.3f} * N^(-{-coeffs[0]:.3f})')
"

```

## 2026-05-10 18:32:40

```bash
ls -la /home/shona/Modeling_of_LLMs_LPT/
```

## 2026-05-10 18:32:40

```bash
find /home/shona/Modeling_of_LLMs_LPT -maxdepth 2 -type d | head -50
```

## 2026-05-10 18:32:47

```bash
ls /home/shona/Modeling_of_LLMs_LPT/runners/ /home/shona/Modeling_of_LLMs_LPT/runners/scripts/ /home/shona/Modeling_of_LLMs_LPT/analysis/ /home/shona/Modeling_of_LLMs_LPT/db/ /home/shona/Modeling_of_LLMs_LPT/envs/ /home/shona/Modeling_of_LLMs_LPT/tests/ /home/shona/Modeling_of_LLMs_LPT/docs/
```

## 2026-05-10 18:33:05

```bash
head -50 /home/shona/Modeling_of_LLMs_LPT/runners/test_model_architecture.py
```

## 2026-05-10 18:33:07

```bash
head -40 /home/shona/Modeling_of_LLMs_LPT/analysis/analyze_phase_diagram.py /home/shona/Modeling_of_LLMs_LPT/analysis/analyze_pq.py /home/shona/Modeling_of_LLMs_LPT/analysis/analyze_integrated.py
```

## 2026-05-10 18:33:12

```bash
ls /home/shona/Modeling_of_LLMs_LPT/runners/scripts/ && head -50 /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_collapse_phase_sweep.sh && echo '---' && head -50 /home/shona/Modeling_of_LLMs_LPT/runners/scripts/run_scaling_sweep.sh
```

## 2026-05-10 18:33:13

```bash
ls /home/shona/Modeling_of_LLMs_LPT/docs/ /home/shona/Modeling_of_LLMs_LPT/docs/log/ /home/shona/Modeling_of_LLMs_LPT/docs/Programming_Guide/
```

## 2026-05-10 19:18:13

```bash
nvidia-smi
```

## 2026-05-10 19:25:49

```bash
ls -la /home/shona/Modeling_of_LLMs_LPT/research_state 2>/dev/null; ls /home/shona/Modeling_of_LLMs_LPT/todo.md /home/shona/Modeling_of_LLMs_LPT/open_questions.md 2>/dev/null; echo "---"; wc -l /home/shona/Modeling_of_LLMs_LPT/CLAUDE.md
```

## 2026-05-10 20:02:37

```bash
mkdir -p /home/shona/Modeling_of_LLMs_LPT/research_state
```

## 2026-05-10 20:14:45

```bash
ls -la /home/shona/Modeling_of_LLMs_LPT/.claude/ 2>/dev/null; echo "---"; ls /home/shona/Modeling_of_LLMs_LPT/.claude/agents/ 2>/dev/null; echo "---global---"; ls /home/shona/.claude/agents/ 2>/dev/null | head -20
```

## 2026-05-10 20:16:09

```bash
mkdir -p /home/shona/Modeling_of_LLMs_LPT/.claude/agents
```

## 2026-05-10 21:06:04

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/ 2>/dev/null | head -5; echo "---"; find /home/shona/Modeling_of_LLMs_LPT/results -name "*.npz" 2>/dev/null | head -3; echo "---npz inspect---"; python3 -c "
import numpy as np, sys, glob
files = sorted(glob.glob('/home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/*/N3_T0_6/*.npz'))[:1]
if files:
    f = files[0]
    print('file:', f)
    d = np.load(f)
    for k in d.files:
        print(f'  {k}: shape={d[k].shape}, dtype={d[k].dtype}')
" 2>&1 | head -30
```

## 2026-05-10 21:06:05

```bash
grep -rn "layer_top\|layer_mid\|layer_low\|make_capture_layers" /home/shona/Modeling_of_LLMs_LPT/runners/ /home/shona/Modeling_of_LLMs_LPT/analysis/ 2>/dev/null | head -20
```

## 2026-05-10 21:08:04

```bash
PYTHONPATH=/app python3 analysis/cosine_sim_phase.py 2>&1 | head -200
```

## 2026-05-12 10:25:18

```bash
cat /home/shona/Modeling_of_LLMs_LPT/open_questions.md && echo "===" && cat /home/shona/Modeling_of_LLMs_LPT/research_state/hypotheses.md
```

## 2026-05-21 12:34:08

```bash
find /home/shona/Modeling_of_LLMs_LPT -name "*.md" | grep -E "(research_state|todo|open_questions)" | head -20
```

## 2026-05-21 12:34:08

```bash
find /home/shona/Modeling_of_LLMs_LPT -name "*.py" | grep -v archive | grep -v __pycache__ | sort
```

## 2026-05-21 12:34:32

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/ 2>/dev/null | head -20 && echo "---" && ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/ 2>/dev/null | head -10
```

## 2026-05-21 12:34:32

```bash
ls /home/shona/Modeling_of_LLMs_LPT/runners/scripts/ 2>/dev/null
```

## 2026-05-21 12:34:36

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/ | head -20 && echo "---" && ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-14b/ | head -20
```

## 2026-05-21 12:34:37

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/ 2>/dev/null | head -10 && echo "---" && ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b/ 2>/dev/null | head -20
```

## 2026-05-21 12:34:41

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/ | wc -l && ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-14b/ | wc -l && ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b/ | wc -l
```

## 2026-05-21 12:34:43

```bash
# 14B full_sweep の各セルにsummary.jsonが存在するか確認
find /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-14b -name "summary.json" | wc -l
# 14B collapse_phase
find /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b -name "summary.json" | wc -l
```

## 2026-05-21 12:35:03

```bash
# 14B full_sweep の missing cells（summary.jsonなし）を確認
for d in /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-14b/*/; do
  if [ ! -f "$d/summary.json" ]; then
    echo "MISSING: $d"
  fi
done
```

## 2026-05-21 12:35:04

```bash
# 7B full_sweep の全セル確認
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/ | tail -20
```

## 2026-05-21 12:35:07

```bash
# 7B full_sweep の全セルにsummary.jsonがあるか確認
find /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b -name "summary.json" | wc -l
# collapse_phase 7B
find /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b -name "summary.json" | wc -l
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b/ | wc -l
```

## 2026-05-21 12:35:08

```bash
# 14B collapse_phase の missing cells
for d in /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b/*/; do
  if [ ! -f "$d/summary.json" ]; then
    echo "MISSING: $d"
  fi
done
```

## 2026-05-21 12:35:12

```bash
# collapse_phase 14B の全セルリスト（T > 1.0 のみ期待）
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b/

# 14B collapse_phase の最大N/T確認
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b/ | tail -20
```

## 2026-05-21 12:35:51

```bash
# 各モデルのスイープ完成状況を一覧化
echo "=== 7B full_sweep ==="
echo "  ディレクトリ数: $(ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/ | wc -l)"
echo "  summary.json数: $(find /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b -name summary.json | wc -l)"

echo "=== 7B collapse_phase ==="
echo "  ディレクトリ数: $(ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b/ | wc -l)"
echo "  summary.json数: $(find /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b -name summary.json | wc -l)"

echo "=== 14B full_sweep ==="
echo "  ディレクトリ数: $(ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-14b/ | wc -l)"
echo "  summary.json数: $(find /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-14b -name summary.json | wc -l)"
echo "  missing:"
for d in /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-14b/*/; do
  [ ! -f "$d/summary.json" ] && echo "    $(basename $d)"
done

echo "=== 14B collapse_phase ==="
echo "  ディレクトリ数: $(ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b/ | wc -l)"
echo "  summary.json数: $(find /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-14b -name summary.json | wc -l)"
```

## 2026-05-21 12:36:04

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-14b/N6_T0_8/ 2>&1 || echo "ディレクトリが存在しないかエラー"
```

## 2026-05-21 12:36:07

```bash
# collapse_phase 7B の missing: N3_T1_0 の状況確認
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/collapse_phase/deepseek-r1-distill-qwen-7b/N3_T1_0/ 2>&1 || echo "ディレクトリなし"
```

## 2026-05-21 12:36:10

```bash
# 解析スクリプトの簡易確認
head -5 /home/shona/Modeling_of_LLMs_LPT/analysis/analyze_pq.py
head -5 /home/shona/Modeling_of_LLMs_LPT/analysis/analyze_integrated.py
head -5 /home/shona/Modeling_of_LLMs_LPT/analysis/analyze_slowing.py
head -5 /home/shona/Modeling_of_LLMs_LPT/analysis/cosine_sim_phase.py
head -5 /home/shona/Modeling_of_LLMs_LPT/analysis/plot_scaling.py
```

## 2026-05-21 12:39:01

```bash
git diff --stat
```

## 2026-05-21 12:57:18

```bash
find /home/shona/Modeling_of_LLMs_LPT -name "*.pdf" 2>/dev/null && find /home/shona -maxdepth 3 -name "*.pdf" 2>/dev/null | head -20
```

## 2026-05-21 12:57:28

```bash
sudo apt-get install -y poppler-utils 2>&1 | tail -5
```

## 2026-05-21 12:57:32

```bash
# pdftotext で テキスト抽出を試みる
which pdftotext 2>/dev/null || echo "not found"
# python で抽出できるか
python3 -c "import PyPDF2; print('ok')" 2>/dev/null || echo "no PyPDF2"
python3 -c "import pdfplumber; print('ok')" 2>/dev/null || echo "no pdfplumber"
python3 -c "import pymupdf; print('ok')" 2>/dev/null || echo "no pymupdf"
python3 -c "import fitz; print('ok')" 2>/dev/null || echo "no fitz"
```

## 2026-05-21 12:57:35

```bash
pip install pymupdf --quiet 2>&1 | tail -3
```

## 2026-05-21 12:57:39

```bash
pip install pymupdf --quiet --break-system-packages 2>&1 | tail -5
```

## 2026-05-21 12:57:44

```bash
python3 - <<'EOF'
import fitz  # pymupdf

for fname in ["第4回AI開発演習#2-1.pdf", "第4回AI開発演習#2-2.pdf"]:
    path = f"/home/shona/Modeling_of_LLMs_LPT/{fname}"
    doc = fitz.open(path)
    print(f"\n{'='*60}")
    print(f"FILE: {fname}  ({doc.page_count} pages)")
    print('='*60)
    for i, page in enumerate(doc):
        text = page.get_text()
        if text.strip():
            print(f"\n--- Page {i+1} ---")
            print(text)
    doc.close()
EOF
```

## 2026-05-21 12:57:47

```bash
cat /home/shona/.claude/projects/-home-shona-Modeling-of-LLMs-LPT/4040832c-ac2b-411f-8300-c8131f1e505b/tool-results/b2ha6fftd.txt
```

## 2026-05-21 12:57:53

```bash
python3 - <<'EOF'
import fitz

for fname in ["第4回AI開発演習#2-1.pdf", "第4回AI開発演習#2-2.pdf"]:
    path = f"/home/shona/Modeling_of_LLMs_LPT/{fname}"
    doc = fitz.open(path)
    print(f"\n{'='*60}")
    print(f"FILE: {fname}  ({doc.page_count} pages)")
    print('='*60)
    for i, page in enumerate(doc):
        text = page.get_text()
        if text.strip():
            print(f"\n--- Page {i+1} ---")
            # 長いページは最初の1000文字だけ表示
            print(text[:1500])
    doc.close()
EOF
```

## 2026-05-21 12:58:02

```bash
python3 - <<'EOF'
import fitz

path = "/home/shona/Modeling_of_LLMs_LPT/第4回AI開発演習#2-1.pdf"
doc = fitz.open(path)
print(f"総ページ数: {doc.page_count}")

# まずページタイトル行だけ抜き出して全体構造を把握
for i, page in enumerate(doc):
    lines = [l.strip() for l in page.get_text().split('\n') if l.strip()]
    # 最初の3行だけ（タイトル相当）
    preview = ' / '.join(lines[:3])
    print(f"  p{i+1:02d}: {preview[:100]}")
doc.close()
EOF
```

## 2026-05-21 12:58:08

```bash
python3 - <<'EOF'
import fitz

path = "/home/shona/Modeling_of_LLMs_LPT/第4回AI開発演習#2-2.pdf"
doc = fitz.open(path)
print(f"総ページ数: {doc.page_count}")

for i, page in enumerate(doc):
    lines = [l.strip() for l in page.get_text().split('\n') if l.strip()]
    preview = ' / '.join(lines[:3])
    print(f"  p{i+1:02d}: {preview[:100]}")
doc.close()
EOF
```

## 2026-05-21 12:58:17

```bash
python3 - <<'EOF'
import fitz

# コード整理に直接関係するページを詳読
# 2-1: p23-37 (リファクタリング・コード整理系)
# 2-2: p21-45 (AI駆動開発・インナーソース・エージェント系)

path1 = "/home/shona/Modeling_of_LLMs_LPT/第4回AI開発演習#2-1.pdf"
doc1 = fitz.open(path1)

print("=== 2-1: コード整理・リファクタリング関連 (p23-37) ===")
for i in range(22, 37):  # 0-indexed
    page = doc1[i]
    text = page.get_text()
    if text.strip():
        print(f"\n--- Page {i+1} ---")
        print(text)
doc1.close()
EOF
```

## 2026-05-21 12:58:30

```bash
python3 - <<'EOF'
import fitz

path2 = "/home/shona/Modeling_of_LLMs_LPT/第4回AI開発演習#2-2.pdf"
doc2 = fitz.open(path2)

# コード整理・インナーソース・エージェント関連ページを詳読
# p2-p15: 生成AIメリデメ・協働
# p21-p45: ユースケース・インナーソース・エージェント
target_pages = list(range(1, 16)) + list(range(20, 45))  # 0-indexed

for i in target_pages:
    if i >= doc2.page_count:
        break
    page = doc2[i]
    text = page.get_text()
    if text.strip():
        print(f"\n--- Page {i+1} ---")
        print(text)
doc2.close()
EOF
```

## 2026-05-21 12:58:39

```bash
python3 - <<'EOF'
import fitz

path2 = "/home/shona/Modeling_of_LLMs_LPT/第4回AI開発演習#2-2.pdf"
doc2 = fitz.open(path2)

# インナーソース・エージェント・カスタマイズ関連 (p21-45)
for i in range(20, 45):
    if i >= doc2.page_count:
        break
    page = doc2[i]
    text = page.get_text()
    if text.strip():
        print(f"\n--- Page {i+1} ---")
        print(text)
doc2.close()
EOF
```

## 2026-05-21 12:58:45

```bash
python3 - <<'EOF'
import fitz

path2 = "/home/shona/Modeling_of_LLMs_LPT/第4回AI開発演習#2-2.pdf"
doc2 = fitz.open(path2)

# インナーソース p30-45
for i in range(29, 45):
    page = doc2[i]
    text = page.get_text()
    if text.strip():
        print(f"\n--- Page {i+1} ---")
        print(text)
doc2.close()
EOF
```

## 2026-05-21 13:02:17

```bash
find /home/shona/Modeling_of_LLMs_LPT -not -path "*/.*" -not -path "*/archive/*" -not -path "*/__pycache__/*" | sort | head -120
```

## 2026-05-21 13:02:20

```bash
find /home/shona/Modeling_of_LLMs_LPT -not -path "*/.*" -not -path "*/archive/*" -not -path "*/__pycache__/*" -not -path "*/results/*" -not -path "*/figures/*" | sort
```

## 2026-05-21 13:02:23

```bash
cat /home/shona/Modeling_of_LLMs_LPT/.gitignore 2>/dev/null || echo "(no .gitignore)"
```

## 2026-05-21 13:02:27

```bash
# results直下の生成ファイル種別を確認
find /home/shona/Modeling_of_LLMs_LPT/results -type f | sed 's/.*\.//' | sort | uniq -c | sort -rn
echo "---"
find /home/shona/Modeling_of_LLMs_LPT/figures -type f | sed 's/.*\.//' | sort | uniq -c | sort -rn
echo "---"
# ルート直下の散在ファイル
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/ | head -5
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/results_N2_main.json 2>/dev/null && echo "ルート直下json発見"
```

## 2026-05-21 13:02:32

```bash
# resultsの中の古い散在ファイル/ディレクトリを確認
ls -la /home/shona/Modeling_of_LLMs_LPT/results/hanoi/
echo "---"
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/results_N2_hf/ 2>/dev/null | head -5
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/phase_diagram/ 2>/dev/null | head -5
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/pq_sweep/ 2>/dev/null | head -5
```

## 2026-05-21 13:02:35

```bash
# refactoring.md の内容確認
cat /home/shona/Modeling_of_LLMs_LPT/refactoring.md
```

## 2026-05-21 13:02:37

```bash
# figures/ 以下の構造
find /home/shona/Modeling_of_LLMs_LPT/figures -type f | sort
echo "---"
# figures/integrated/ の中身
ls /home/shona/Modeling_of_LLMs_LPT/figures/integrated/deepseek-r1-distill-qwen-14b/ 2>/dev/null
```

## 2026-05-21 13:05:16

```bash
ls /home/shona/Modeling_of_LLMs_LPT/archive/
echo "---"
# gitで追跡されているファイルのうち、今回操作対象のものを確認
cd /home/shona/Modeling_of_LLMs_LPT
git ls-files results/hanoi/ | grep -v '\.npz' | head -30
echo "---"
git ls-files refactoring.md 第4回AI開発演習#2-1.pdf 第4回AI開発演習#2-2.pdf
```

## 2026-05-21 13:05:22

```bash
cd /home/shona/Modeling_of_LLMs_LPT
# 旧形式ファイルがgitで追跡されているか確認
git ls-files results/hanoi/results_N2_main.json results/hanoi/results_N3_main.json results/hanoi/results_N4_main.json
git ls-files results/hanoi/phase_diagram/ | head -5
git ls-files results/hanoi/pq_sweep/ | head -5
git ls-files results/hanoi/temp_sweep/ | head -5
git ls-files results/hanoi/results_N2_hf/ results/hanoi/results_N3_hf/
```

## 2026-05-21 13:05:37

```bash
cd /home/shona/Modeling_of_LLMs_LPT

# assets/ 新設してPDFを移動（git未追跡なので通常mv後にgit add）
mkdir -p assets
mv "第4回AI開発演習#2-1.pdf" assets/
mv "第4回AI開発演習#2-2.pdf" assets/
git add assets/

# refactoring.md は中身が空なので削除
rm refactoring.md

echo "Phase 1 完了"
ls assets/
```

## 2026-05-21 13:06:28

```bash
cd /home/shona/Modeling_of_LLMs_LPT

mkdir -p archive/results_legacy

# 単発JSONファイル3本
git mv results/hanoi/results_N2_main.json archive/results_legacy/
git mv results/hanoi/results_N3_main.json archive/results_legacy/
git mv results/hanoi/results_N4_main.json archive/results_legacy/

echo "単発JSON移動完了"
```

## 2026-05-21 13:06:31

```bash
ls -la /home/shona/Modeling_of_LLMs_LPT/results/hanoi/results_N2_main.json
# ownerがrootになっているか確認
stat /home/shona/Modeling_of_LLMs_LPT/results/hanoi/results_N2_main.json | head -5
```

## 2026-05-21 13:07:21

```bash
ls -la /home/shona/Modeling_of_LLMs_LPT/figures/ | head -5
stat /home/shona/Modeling_of_LLMs_LPT/archive | grep Uid
```

## 2026-05-21 13:07:28

```bash
cd /home/shona/Modeling_of_LLMs_LPT

# archive/ は shona 所有で書き込み可 → legacy results を cp してから git index を操作

# --- 単発JSON (3本) ---
cp results/hanoi/results_N2_main.json archive/results_legacy/
cp results/hanoi/results_N3_main.json archive/results_legacy/
cp results/hanoi/results_N4_main.json archive/results_legacy/
git add archive/results_legacy/
git rm --cached results/hanoi/results_N2_main.json results/hanoi/results_N3_main.json results/hanoi/results_N4_main.json
echo "単発JSON完了"
```

## 2026-05-21 13:07:35

```bash
cd /home/shona/Modeling_of_LLMs_LPT

# --- phase_diagram/ (全 summary.json を cp) ---
mkdir -p archive/results_legacy/phase_diagram
find results/hanoi/phase_diagram -name "summary.json" | while read f; do
  subdir=$(dirname "$f" | sed 's|results/hanoi/phase_diagram/||')
  mkdir -p "archive/results_legacy/phase_diagram/$subdir"
  cp "$f" "archive/results_legacy/phase_diagram/$subdir/"
done
git add archive/results_legacy/phase_diagram/
git ls-files results/hanoi/phase_diagram/ | xargs git rm --cached
echo "phase_diagram 完了: $(git ls-files archive/results_legacy/phase_diagram/ | wc -l) 件"
```

## 2026-05-21 13:07:45

```bash
cd /home/shona/Modeling_of_LLMs_LPT

# --- pq_sweep/ ---
mkdir -p archive/results_legacy/pq_sweep
find results/hanoi/pq_sweep -name "summary.json" | while read f; do
  subdir=$(dirname "$f" | sed 's|results/hanoi/pq_sweep/||')
  mkdir -p "archive/results_legacy/pq_sweep/$subdir"
  cp "$f" "archive/results_legacy/pq_sweep/$subdir/"
done
git add archive/results_legacy/pq_sweep/
git ls-files results/hanoi/pq_sweep/ | xargs git rm --cached
echo "pq_sweep 完了"

# --- temp_sweep/ ---
mkdir -p archive/results_legacy/temp_sweep
find results/hanoi/temp_sweep -name "summary.json" | while read f; do
  subdir=$(dirname "$f" | sed 's|results/hanoi/temp_sweep/||')
  mkdir -p "archive/results_legacy/temp_sweep/$subdir"
  cp "$f" "archive/results_legacy/temp_sweep/$subdir/"
done
git add archive/results_legacy/temp_sweep/
git ls-files results/hanoi/temp_sweep/ | xargs git rm --cached
echo "temp_sweep 完了"

# --- results_N2_hf/, results_N3_hf/ ---
mkdir -p archive/results_legacy/results_N2_hf archive/results_legacy/results_N3_hf
cp results/hanoi/results_N2_hf/summary.json archive/results_legacy/results_N2_hf/
cp results/hanoi/results_N3_hf/summary.json archive/results_legacy/results_N3_hf/
git add archive/results_legacy/results_N2_hf/ archive/results_legacy/results_N3_hf/
git rm --cached results/hanoi/results_N2_hf/summary.json results/hanoi/results_N3_hf/summary.json
echo "results_N*_hf 完了"
```

## 2026-05-21 13:08:02

```bash
cd /home/shona/Modeling_of_LLMs_LPT

# legacy/ にモデル名なし・旧命名を退避
mkdir -p figures/legacy

# モデル名なしのルート直下 png
mv figures/phase_diagram.png   figures/legacy/
mv figures/pq_dist.png         figures/legacy/
mv figures/pq_summary.png      figures/legacy/
mv figures/scaling.png         figures/legacy/
mv figures/slowing_combined.png    figures/legacy/
mv figures/slowing_fallback_rate.png figures/legacy/
mv figures/slowing_tau_imputed.png  figures/legacy/
mv figures/slowing_tau_valid.png    figures/legacy/

# 旧命名（-distill- 欠落）
mv "figures/deepseek-r1-qwen-7b_phase_diagram.png" figures/legacy/
mv "figures/deepseek-r1-qwen-7b_pq_dist.png"       figures/legacy/
mv "figures/deepseek-r1-qwen-7b_pq_summary.png"    figures/legacy/

echo "legacy 退避完了"

# integrated/ 以下を統一構造に整理
# ルート直下の integrated_*.png → figures/integrated/<slug>/
mkdir -p figures/integrated/deepseek-r1-distill-qwen-7b
mkdir -p figures/integrated/deepseek-r1-distill-qwen-14b

mv figures/deepseek-r1-distill-qwen-7b_integrated_phase.png  figures/integrated/deepseek-r1-distill-qwen-7b/phase.png
mv figures/deepseek-r1-distill-qwen-7b_integrated_pq_dist.png figures/integrated/deepseek-r1-distill-qwen-7b/pq_dist.png
mv figures/deepseek-r1-distill-qwen-7b_integrated_summary.png figures/integrated/deepseek-r1-distill-qwen-7b/summary.png

mv figures/deepseek-r1-distill-qwen-14b_integrated_phase.png  figures/integrated/deepseek-r1-distill-qwen-14b/phase.png
mv figures/deepseek-r1-distill-qwen-14b_integrated_pq_dist.png figures/integrated/deepseek-r1-distill-qwen-14b/pq_dist.png
mv figures/deepseek-r1-distill-qwen-14b_integrated_summary.png figures/integrated/deepseek-r1-distill-qwen-14b/summary.png

echo "integrated 整理完了"

# 空ディレクトリ削除（以前の空フォルダ）
rmdir figures/integrated/deepseek-r1-distill-qwen-14b 2>/dev/null && echo "空dir削除" || echo "空dirなし（既に使用中）"

echo "---"
find figures/ -type f | sort
```

## 2026-05-21 13:08:25

```bash
cd /home/shona/Modeling_of_LLMs_LPT
# *test* のパターンを削除したので test_early_stop.py が誤って除外されていないか確認
git check-ignore -v tests/test_early_stop.py 2>&1 || echo "追跡対象 (ignore されていない) ✓"
# assets/ が除外されていないか確認
git check-ignore -v assets/第4回AI開発演習#2-1.pdf 2>&1 || echo "assets/ 追跡対象 ✓"
```

## 2026-05-21 13:08:38

```bash
cd /home/shona/Modeling_of_LLMs_LPT
git status --short
```

## 2026-05-21 13:08:54

```bash
cd /home/shona/Modeling_of_LLMs_LPT

# 未追跡の新規ファイルもステージング
git add .gitignore CLAUDE.md research_state/results_summary.md open_questions.md

git commit -m "refactor: separate static/dynamic files and archive legacy results

- Add assets/ for reference PDFs (第4回AI開発演習)
- Remove empty refactoring.md
- Archive legacy results to archive/results_legacy/:
    phase_diagram/ (38 cells), pq_sweep/ (17), temp_sweep/ (5),
    results_N2/3/4_main.json, results_N2/3_hf/ → all superseded by full_sweep/
- Reorganize figures/ into <sweep_type>/<slug>/ structure;
    nameless/old-named PNGs → figures/legacy/
    integrated PNGs → figures/integrated/<slug>/
- Update .gitignore: add legacy result paths, remove *test* glob
- Update CLAUDE.md: document static/dynamic separation and figures structure

Physical files in results/hanoi/ remain (Docker root-owned, cannot mv);
covered by .gitignore entries added above.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

## 2026-05-21 13:11:51

```bash
cd /home/shona/Modeling_of_LLMs_LPT
# radon が使えるか確認（循環的複雑度・認知的複雑度の標準ツール）
python3 -c "import radon; print('radon ok')" 2>/dev/null || echo "radon なし"
# 標準ライブラリだけで計測できる範囲を確認
python3 -c "import ast; print('ast ok')"
```

## 2026-05-21 13:11:55

```bash
pip install radon --quiet --break-system-packages 2>&1 | tail -3
```

## 2026-05-21 13:12:13

```bash
cd /home/shona/Modeling_of_LLMs_LPT
export PATH="$PATH:/home/shona/.local/bin"

# 対象ファイル一覧
PY_FILES=$(find . -name "*.py" \
  -not -path "*/archive/*" \
  -not -path "*/__pycache__/*" \
  -not -path "*/.venv/*" \
  | sort)

echo "=== LOC (総行数 / コード行 / コメント行 / 空行) ==="
python3 - <<'PYEOF'
import ast, re
from pathlib import Path

files = sorted(Path(".").rglob("*.py"))
files = [f for f in files if not any(p in f.parts for p in ("archive", "__pycache__", ".venv"))]

print(f"{'ファイル':<55} {'LOC':>5} {'コード':>5} {'コメント':>5} {'空行':>5}")
print("-" * 80)
totals = [0, 0, 0, 0]
for f in files:
    lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
    loc   = len(lines)
    blank = sum(1 for l in lines if l.strip() == "")
    comment = sum(1 for l in lines if l.strip().startswith("#"))
    code  = loc - blank - comment
    totals[0] += loc; totals[1] += code; totals[2] += comment; totals[3] += blank
    print(f"{str(f):<55} {loc:>5} {code:>5} {comment:>5} {blank:>5}")
print("-" * 80)
print(f"{'合計':<55} {totals[0]:>5} {totals[1]:>5} {totals[2]:>5} {totals[3]:>5}")
PYEOF
```

## 2026-05-21 13:12:26

```bash
cd /home/shona/Modeling_of_LLMs_LPT
export PATH="$PATH:/home/shona/.local/bin"

echo "=== 循環的複雑度（Cyclomatic Complexity）関数別 Top20 ==="
python3 - <<'PYEOF'
from radon.complexity import cc_visit
from radon.metrics import mi_visit
from pathlib import Path

results = []
files = sorted(Path(".").rglob("*.py"))
files = [f for f in files if not any(p in f.parts for p in ("archive", "__pycache__", ".venv"))]

for f in files:
    src = f.read_text(encoding="utf-8", errors="ignore")
    try:
        blocks = cc_visit(src)
        for b in blocks:
            results.append((b.complexity, str(f), b.name, b.lineno))
    except:
        pass

results.sort(reverse=True)
print(f"{'CC':>4} {'ファイル':<45} {'関数/クラス':<35} {'行'}")
print("-" * 95)
for cc, fname, name, lineno in results[:20]:
    rank = "🔴" if cc >= 10 else ("🟡" if cc >= 5 else "🟢")
    print(f"{cc:>4} {rank} {fname:<43} {name:<35} L{lineno}")
PYEOF
```

## 2026-05-21 13:12:52

```bash
cd /home/shona/Modeling_of_LLMs_LPT
export PATH="$PATH:/home/shona/.local/bin"

echo "=== ファイル別サマリー（CC合計・平均・メソッド数・保守性指数） ==="
python3 - <<'PYEOF'
from radon.complexity import cc_visit, cc_rank
from radon.metrics import mi_visit
from pathlib import Path

files = sorted(Path(".").rglob("*.py"))
files = [f for f in files if not any(p in f.parts for p in ("archive", "__pycache__", ".venv"))
         and f.stat().st_size > 0]

print(f"{'ファイル':<45} {'LOC':>5} {'CC合計':>7} {'CC最大':>7} {'CC平均':>7} {'関数数':>6} {'MI':>5}")
print("-" * 95)

for f in files:
    src = f.read_text(encoding="utf-8", errors="ignore")
    lines = src.splitlines()
    loc = len(lines)
    try:
        blocks = cc_visit(src)
        if blocks:
            cc_total = sum(b.complexity for b in blocks)
            cc_max   = max(b.complexity for b in blocks)
            cc_avg   = cc_total / len(blocks)
            n_funcs  = len(blocks)
        else:
            cc_total = cc_max = cc_avg = n_funcs = 0
        mi = mi_visit(src, multi=True)
    except:
        cc_total = cc_max = cc_avg = n_funcs = mi = 0

    flag = "🔴" if cc_max >= 10 else ("🟡" if cc_max >= 5 else "🟢")
    print(f"{flag} {str(f):<43} {loc:>5} {cc_total:>7} {cc_max:>7} {cc_avg:>7.1f} {n_funcs:>6} {mi:>5.1f}")
PYEOF
```

## 2026-05-21 13:16:05

```bash
cd /home/shona/Modeling_of_LLMs_LPT
python3 - <<'PYEOF'
import ast
from pathlib import Path

files = sorted(Path(".").rglob("*.py"))
files = [f for f in files if not any(p in f.parts for p in ("archive", "__pycache__", ".venv"))
         and f.stat().st_size > 0]

# プロジェクト内モジュールのセット（importで参照される名前）
project_modules = {
    "envs.hanoi_env": "envs/hanoi_env.py",
    "envs": "envs/__init__.py",
    "runners.run": "runners/run.py",
    "runners.run_local": "runners/run_local.py",
    "runners": "runners/__init__.py",
    "analysis": "analysis/__init__.py",
}

for f in files:
    src = f.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(src)
    except:
        continue

    imports_internal = []
    imports_external = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports_external.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [a.name for a in node.names]
            # プロジェクト内かどうか判定
            is_internal = (
                module.startswith("envs") or
                module.startswith("runners") or
                module.startswith("analysis") or
                module.startswith("db") or
                module.startswith("tests")
            )
            if is_internal:
                imports_internal.append(f"from {module} import {', '.join(names)}")
            else:
                imports_external.append(f"{module}.{names[0]}" if names else module)

    print(f"\n=== {f} ===")
    if imports_internal:
        print("  [内部依存]")
        for i in imports_internal:
            print(f"    {i}")
    if imports_external:
        # よく使うもだけ表示
        ext_filtered = [e for e in imports_external if not e.startswith("_")]
        print(f"  [外部ライブラリ] {', '.join(sorted(set(ext_filtered)))}")
PYEOF
```

## 2026-05-21 13:16:17

```bash
cd /home/shona/Modeling_of_LLMs_LPT
# 各ファイルの主要クラス・関数・定数のエクスポート一覧を抽出
python3 - <<'PYEOF'
import ast
from pathlib import Path

targets = [
    "envs/hanoi_env.py",
    "runners/run.py",
    "runners/run_local.py",
    "runners/test_model_architecture.py",
    "analysis/analyze_integrated.py",
    "analysis/analyze_phase_diagram.py",
    "analysis/analyze_pq.py",
    "analysis/analyze_slowing.py",
    "analysis/cosine_sim_phase.py",
    "analysis/plot_scaling.py",
    "db/sync_one.py",
    "tests/test_early_stop.py",
]

for fpath in targets:
    f = Path(fpath)
    src = f.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(src)
    except:
        continue
    classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    funcs   = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")]
    priv    = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name.startswith("_") and n.name != "__init__"]
    assigns = [n.targets[0].id for n in ast.walk(tree)
               if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
               and n.targets[0].id.isupper()]
    print(f"\n{fpath}")
    if classes: print(f"  classes : {classes}")
    if funcs:   print(f"  funcs   : {funcs}")
    if priv:    print(f"  private : {priv}")
    if assigns: print(f"  consts  : {assigns}")
PYEOF
```

## 2026-05-21 13:24:20

```bash
find /home/shona/Modeling_of_LLMs_LPT -name "analyze_slowing.py" 2>/dev/null
```

## 2026-05-21 13:24:30

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/ 2>/dev/null | head -5
```

## 2026-05-21 13:24:32

```bash
ls /home/shona/Modeling_of_LLMs_LPT/results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b/ | head -8
```

## 2026-05-21 13:25:16

```bash
mkdir -p /home/shona/Modeling_of_LLMs_LPT/tools && ls /home/shona/Modeling_of_LLMs_LPT/tools/ 2>/dev/null || echo "(empty)"
```

## 2026-05-21 13:26:10

```bash
python3 -m radon --version 2>/dev/null || echo "radon not installed"
```

## 2026-05-21 13:29:32

```bash
python3 -m radon cc -s runners/run_local.py | grep -E "generate_with_hidden_states|_prepare_input_ids|_apply_repetition_penalty|_sample_next_token|_capture_new_move_hidden_states|_is_disk_loop_confirmed|_check_early_stop_with_disk_verify|_finalize_hidden_states"
```

## 2026-05-21 13:30:28

```bash
python3 -m radon cc -s runners/run_local.py | grep -E "generate_with_hidden_states|_prepare_input_ids|_apply_repetition_penalty|_sample_next_token|_capture_new_move|_is_disk_loop|_check_early_stop_with|_finalize_hidden_states|_handle_new_moves|_build_reasoning|_should_check"
```

## 2026-05-21 13:31:05

```bash
python3 -m radon cc -s runners/run_local.py | grep generate_with_hidden_states
```

## 2026-05-21 13:31:08

```bash
python3 -m pytest tests/test_early_stop.py -v --tb=short 2>&1 | tail -30
```

## 2026-05-21 13:31:15

```bash
python3 -m radon cc -s runners/run_local.py 2>&1 | grep -E "^ +F "
```

## 2026-05-21 13:31:21

```bash
python3 -m py_compile runners/run_local.py && echo "syntax OK"
```

## 2026-05-21 13:31:28

```bash
python3 -m radon cc -s runners/run_local.py | grep generate_with_hidden_states && python3 -m pytest tests/test_early_stop.py -v --tb=short 2>&1 | tail -20
```

## 2026-05-21 13:32:10

```bash
python3 -m radon cc -s runners/run_local.py | grep -E "(generate_with_hidden_states|CC|grade)" | head -20
```

## 2026-05-21 13:32:13

```bash
python3 -m pytest tests/test_early_stop.py -v --tb=short 2>&1 | tail -15
```

## 2026-05-21 13:34:29

```bash
grep -n "generate_with_hidden_states\|_resolve_profile\|_resolve_capture\|_estimate_reasoning_tokens\b" /home/shona/Modeling_of_LLMs_LPT/runners/run_local.py | head -30
```

## 2026-05-21 13:34:32

```bash
grep -n "generate_with_hidden_states" /home/shona/Modeling_of_LLMs_LPT/runners/test_model_architecture.py | head -10
```

## 2026-05-21 13:34:38

```bash
grep -n "profile=\|capture_layers=" /home/shona/Modeling_of_LLMs_LPT/runners/test_model_architecture.py | head -20
```

## 2026-05-21 13:34:41

```bash
grep -n "profile " /home/shona/Modeling_of_LLMs_LPT/runners/test_model_architecture.py | head -10
```

## 2026-05-21 13:34:45

```bash
grep -n "capture_layers " /home/shona/Modeling_of_LLMs_LPT/runners/test_model_architecture.py | head -10
```

## 2026-05-21 13:35:22

```bash
python3 -m pytest tests/test_early_stop.py -q 2>&1 | tail -5 && python3 -m radon cc -s runners/run_local.py | grep -E "^\s+[A-F] " | head -5
```

## 2026-05-21 13:35:39

```bash
python3 tools/measure_quality.py 2>&1 | tail -25
```

## 2026-05-21 13:35:47

```bash
python3 tools/measure_quality.py --verbose 2>&1 | grep -A 10 "run_local"
```

## 2026-05-21 13:36:21

```bash
grep -n "^\(import os\|import sys\|from dataclasses import.*field\)\|[^_]os\.\|[^_]sys\.\|field(" /home/shona/Modeling_of_LLMs_LPT/runners/run_local.py | head -20
```

## 2026-05-21 13:36:24

```bash
grep -n "\bos\.\|sys\.\|field(" /home/shona/Modeling_of_LLMs_LPT/runners/run_local.py | head -20
```

## 2026-05-21 13:36:30

```bash
grep -cn "\bos\b\|\bsys\b\|\bfield\b" /home/shona/Modeling_of_LLMs_LPT/runners/run_local.py
```

## 2026-05-21 13:36:34

```bash
grep -n "\bos\b\|\bsys\b\|\bfield\b" /home/shona/Modeling_of_LLMs_LPT/runners/run_local.py
```

## 2026-05-21 13:36:44

```bash
python3 -m pytest tests/test_early_stop.py -q 2>&1 | tail -3
```

## 2026-05-21 13:37:16

```bash
python3 -m radon cc -s analysis/analyze_integrated.py
```

## 2026-05-21 13:39:09

```bash
python3 -m radon cc -s analysis/analyze_integrated.py | head -20
```

## 2026-05-21 13:39:14

```bash
python3 -m radon cc -s /home/shona/Modeling_of_LLMs_LPT/analysis/analyze_integrated.py 2>/dev/null
```

## 2026-05-21 13:39:42

```bash
python3 -m radon cc -s /home/shona/Modeling_of_LLMs_LPT/analysis/analyze_integrated.py 2>/dev/null
```

## 2026-05-21 13:39:46

```bash
python3 -m pytest tests/test_early_stop.py -q 2>&1 | tail -5
```

## 2026-05-21 13:39:49

```bash
python3 -c "from analysis.analyze_integrated import plot_phase_diagram, plot_summary, load_condition; print('import OK')"
```

## 2026-05-21 13:40:21

```bash
python3 -m radon cc -s analysis/analyze_integrated.py | grep -E "^\s+[ABCDEF] " | head -15 && python3 -m pytest tests/test_early_stop.py -q 2>&1 | tail -3
```

## 2026-05-21 13:40:28

```bash
python3 tools/measure_quality.py 2>&1 | grep -E "(ファイル|CC ≥|MI <|⚠ CC|✅|❌|スキャン)" | head -25
```

## 2026-05-21 13:40:31

```bash
python3 tools/measure_quality.py 2>&1 | grep -E "^\s+\S" | head -30
```

## 2026-05-21 13:41:21

```bash
python3 -m radon cc -s tools/measure_quality.py | grep -E "^\s+[A-F] " | head -10 && python3 tools/measure_quality.py 2>&1 | tail -5
```

## 2026-05-21 13:43:14

```bash
python3 -m radon cc -s analysis/analyze_phase_diagram.py | grep -E "^\s+[A-F] " | head -10 && python3 -m pytest tests/test_early_stop.py -q 2>&1 | tail -3
```

## 2026-05-21 13:43:19

```bash
python3 tools/measure_quality.py 2>&1 | grep -E "^\s+\S.*⚠|CC ≥|❌|✅|スキャン"
```

## 2026-05-21 13:43:31

```bash
python3 -m radon cc -s analysis/analyze_pq.py | grep -E "^\s+[A-F] " | grep -v "A (" | head -10
```

## 2026-05-21 13:43:53

```bash
python3 -m radon cc -s analysis/analyze_pq.py
```

## 2026-05-21 13:45:40

```bash
python3 -m radon cc -s analysis/analyze_pq.py
```

## 2026-05-21 13:45:47

```bash
python3 -m pytest tests/test_early_stop.py -q 2>&1 | tail -3
```

## 2026-05-21 13:45:54

```bash
python3 -c "import sys; sys.path.insert(0, '/home/shona/Modeling_of_LLMs_LPT'); import analysis.analyze_pq as m; print('import OK'); print('public API:', [f for f in dir(m) if not f.startswith('__')])"
```

## 2026-05-21 13:45:57

```bash
python3 -m radon cc -s analysis/analyze_pq.py | grep -E "^\s+[C-F] "
```

## 2026-05-21 13:46:01

```bash
python3 -m radon cc -s /home/shona/Modeling_of_LLMs_LPT/analysis/analyze_pq.py | grep -E "^\s+[CDEF] "
```

## 2026-05-21 13:46:05

```bash
python3 -m radon cc -s /home/shona/Modeling_of_LLMs_LPT/analysis/analyze_pq.py | grep " - C \| - D \| - E \| - F "
```

## 2026-05-21 13:46:41

```bash
python3 -m radon cc -s analysis/analyze_pq.py | grep -E "^\s+[C-F] " | head -5 && python3 -m pytest tests/test_early_stop.py -q 2>&1 | tail -3
```

## 2026-05-21 13:46:47

```bash
python3 tools/measure_quality.py 2>&1 | grep -E "(⚠|CC ≥|❌|✅|スキャン)" | head -15
```

## 2026-05-21 13:47:54

```bash
python3 -m radon cc -s analysis/cosine_sim_phase.py | grep -E "^\s+[A-F] " && python3 -m pytest tests/test_early_stop.py -q 2>&1 | tail -3
```

## 2026-05-21 13:47:58

```bash
python3 -m radon cc -s analysis/analyze_slowing.py | grep -E "^\s+[B-F] " | grep -v "A (" | head -8
```

## 2026-05-21 13:49:00

```bash
python3 -m radon cc -s analysis/analyze_slowing.py | grep -E "^\s+[B-F] " | head -10 && python3 -m pytest tests/test_early_stop.py -q 2>&1 | tail -3
```

## 2026-05-21 13:49:30

```bash
python3 -m radon cc -s analysis/analyze_slowing.py | grep -E "collect_all|_collect_from" && python3 -m pytest tests/test_early_stop.py -q 2>&1 | tail -3
```

## 2026-05-21 13:49:34

```bash
python3 tools/measure_quality.py 2>&1 | grep -E "(⚠|CC ≥|❌|✅|スキャン)"
```

## 2026-05-21 13:50:31

```bash
python3 -m radon cc -s runners/run.py | grep -E "check_early_stop|_check_" && python3 -m pytest tests/test_early_stop.py -v --tb=short 2>&1 | tail -15
```

## 2026-05-21 13:50:36

```bash
python3 tools/measure_quality.py --verbose 2>&1 | grep -E "(⚠|CC ≥|❌|✅|スキャン|\bCC=)" | head -20
```

## 2026-05-21 13:51:14

```bash
python3 -m radon cc -s analysis/analyze_integrated.py | grep -E "classify_phase|_is_" && python3 -m pytest tests/test_early_stop.py -q 2>&1 | tail -3
```

## 2026-05-21 13:51:44

```bash
python3 -m radon cc -s runners/test_model_architecture.py | grep -E "^\s+[B-F] " | grep -v "A (" | head -8
```

## 2026-05-21 13:52:01

```bash
python3 tools/measure_quality.py 2>&1 | grep -E "(⚠|CC ≥|❌|✅|スキャン|\bCC=)" | head -15
```

## 2026-05-21 13:52:58

```bash
python3 -m radon cc -s runners/run_local.py | grep -E "main|_build_early|_resolve_output|_write_meta" && python3 -m pytest tests/test_early_stop.py -q 2>&1 | tail -3
```

## 2026-05-21 13:53:40

```bash
grep -n "_capture_layers\|_profile\b" /home/shona/Modeling_of_LLMs_LPT/runners/run_local.py | grep -v "def \|#" | head -20
```

## 2026-05-21 13:54:01

```bash
python3 -m radon cc -s runners/run_local.py | grep generate_with && python3 -m pytest tests/test_early_stop.py -q 2>&1 | tail -3
```

## 2026-05-21 13:54:05

```bash
python3 tools/measure_quality.py 2>&1 | grep -E "(⚠|CC ≥|❌|✅|スキャン)"
```

