"""
Hysteresis / first-order transition analysis
  - Fine T scan: T=1.10-1.55 (existing + new midpoints)
  - p_recit(T) shape: sharp step vs smooth sigmoid
  - Within-cell tpm bimodality: first-order signature
  - Move-loop vs no_move fractions
"""
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import json, os
from scipy.optimize import curve_fit

OUT_DIR = 'figures/l2_order_param'
os.makedirs(OUT_DIR, exist_ok=True)

SLUG = 'qwen3-14b'
T_FINE = sorted([1.10,1.15,1.20,1.25,1.30,1.35,1.40,1.45,1.50,1.55,
                 1.80,2.00,2.50,3.00])
N_LIST = [3, 4]

def t_tag(T):
    return str(round(T, 2)).replace('.', '_')

def load_summary(slug, N, T):
    for sweep in ('collapse_phase', 'full_sweep'):
        p = f'results/hanoi/{sweep}/{slug}/N{N}_T{t_tag(T)}/summary.json'
        if os.path.exists(p):
            with open(p) as f:
                return json.load(f)
    return None

def classify(m):
    acc = m.get('accuracy', 0)
    es  = m.get('early_stop')
    nm  = max(m.get('num_moves', 1) or 1, 1)
    tpm = m.get('total_tokens', 0) / nm
    if acc == 1:
        return 'recitation' if tpm < 15 else 'reasoning'
    if es in ('move_loop_repeat', 'move_loop_reverse'):
        return 'move_loop'
    if es == 'think_budget':
        return 'censored'
    return 'pm'

def sigmoid(T, k, Tc):
    return 1.0 / (1.0 + np.exp(-k * (T - Tc)))

# -----------------------------------------------------------------------
# Per-cell statistics
# -----------------------------------------------------------------------
def cell_stats(slug, N, T):
    trials = load_summary(slug, N, T)
    if trials is None:
        return None
    phases = [classify(m) for m in trials]
    tpm_all = [m.get('total_tokens',0)/max(m.get('num_moves',1) or 1,1)
               for m in trials]
    n = len(trials)
    p_rec  = phases.count('recitation') / n
    p_rea  = phases.count('reasoning')  / n
    p_loop = phases.count('move_loop')  / n
    p_pm   = phases.count('pm')         / n
    tpm_rec  = [tpm_all[i] for i,ph in enumerate(phases) if ph=='recitation']
    tpm_rea  = [tpm_all[i] for i,ph in enumerate(phases) if ph=='reasoning']
    tpm_fail = [tpm_all[i] for i,ph in enumerate(phases)
                if ph in ('move_loop','pm')]
    return dict(p_rec=p_rec, p_rea=p_rea, p_loop=p_loop, p_pm=p_pm,
                tpm_rec=tpm_rec, tpm_rea=tpm_rea, tpm_fail=tpm_fail, n=n)

# -----------------------------------------------------------------------
# Fig 1: p_recit(T) fine scan + sigmoid fit
# -----------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle(
    'Hysteresis scan: $p_\\mathrm{recit}(T)$ fine resolution  '
    '(T=1.10–3.0, step 0.05–0.10)\nSharp step → first-order; '
    'smooth sigmoid → continuous',
    fontsize=11, fontweight='bold')

for ax, N in zip(axes, N_LIST):
    data = {T: cell_stats(SLUG, N, T) for T in T_FINE if cell_stats(SLUG, N, T)}
    Ts   = sorted(data.keys())
    p_rec  = [data[T]['p_rec']  for T in Ts]
    p_rea  = [data[T]['p_rea']  for T in Ts]
    p_loop = [data[T]['p_loop'] for T in Ts]
    p_pm   = [data[T]['p_pm']   for T in Ts]

    ax.stackplot(Ts, p_rea, p_rec, p_loop, p_pm,
                 labels=['reasoning', 'recitation', 'move_loop', 'PM'],
                 colors=['#1565C0','#00ACC1','#E65100','#B71C1C'],
                 alpha=0.75)

    # Sigmoid fit to p_recit
    try:
        T_fit = np.array(Ts)
        y_fit = np.array(p_rec)
        mask  = y_fit > 0.02
        if mask.sum() >= 4:
            p0 = [5.0, float(T_fit[mask][0])]
            popt, _ = curve_fit(sigmoid, T_fit[mask], y_fit[mask],
                                p0=p0, maxfev=2000)
            T_dense = np.linspace(min(Ts), max(Ts), 200)
            ax.plot(T_dense, sigmoid(T_dense, *popt), 'w--',
                    lw=1.8, label=f'sigmoid fit\n$T_c$={popt[1]:.2f}, k={popt[0]:.1f}')
    except Exception:
        pass

    ax.set_xlim(min(Ts), max(Ts))
    ax.set_ylim(0, 1)
    ax.set_xlabel('Temperature T', fontsize=10)
    ax.set_ylabel('Fraction of trials', fontsize=10)
    ax.set_title(f'N={N}', fontsize=11, fontweight='bold')
    ax.legend(fontsize=8, loc='upper right')
    ax.axvline(1.1, color='white', lw=0.8, ls=':', alpha=0.5)

plt.tight_layout()
plt.savefig(f'{OUT_DIR}/hysteresis_stack.png', dpi=150,
            bbox_inches='tight', facecolor='white')
plt.close()
print('Saved: hysteresis_stack.png')

# -----------------------------------------------------------------------
# Fig 2: tpm distribution at transition zone — bimodality check
# -----------------------------------------------------------------------
T_TRANSITION = [1.20, 1.25, 1.30, 1.35, 1.40, 1.45, 1.50, 1.55]

fig, axes = plt.subplots(2, len(T_TRANSITION)//2, figsize=(16, 8))
fig.suptitle(
    'tpm distribution in transition zone  '
    '(bimodal → first-order; unimodal → continuous)\n'
    f'Qwen3-14B  N=3',
    fontsize=11, fontweight='bold')

N_BIM = 3
for ax, T in zip(axes.flat, T_TRANSITION):
    st = cell_stats(SLUG, N_BIM, T)
    if st is None:
        ax.set_title(f'T={T}\n[no data]')
        continue
    trials = load_summary(SLUG, N_BIM, T)
    tpm_all = [m.get('total_tokens',0)/max(m.get('num_moves',1) or 1,1)
               for m in trials if classify(m) != 'censored']
    ax.hist(tpm_all, bins=20, range=(0, 100), color='#9C27B0',
            alpha=0.75, edgecolor='white', linewidth=0.4)
    ax.axvline(15, color='white', lw=1.5, ls='--',
               label='tpm=15\n(recit threshold)')
    n_rec  = sum(1 for x in tpm_all if x < 15)
    n_else = len(tpm_all) - n_rec
    ax.set_title(f'T={T}  (recit={n_rec}, other={n_else})', fontsize=9)
    ax.set_xlabel('tokens/move', fontsize=8)
    ax.set_ylabel('count', fontsize=8)
    if T == T_TRANSITION[0]:
        ax.legend(fontsize=7)

plt.tight_layout()
plt.savefig(f'{OUT_DIR}/hysteresis_tpm_dist.png', dpi=150,
            bbox_inches='tight', facecolor='white')
plt.close()
print('Saved: hysteresis_tpm_dist.png')

# -----------------------------------------------------------------------
# Fig 3: dp_recit/dT — sharpness of transition
# -----------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle(
    r'$dp_\mathrm{recit}/dT$: transition sharpness  '
    '(large peak → first-order candidate)',
    fontsize=11, fontweight='bold')

for ax, N in zip(axes, N_LIST):
    data = {T: cell_stats(SLUG, N, T) for T in T_FINE if cell_stats(SLUG, N, T)}
    Ts  = np.array(sorted(data.keys()))
    pr  = np.array([data[T]['p_rec'] for T in Ts])

    ax.plot(Ts, pr, 'o-', color='#00ACC1', lw=2, ms=5,
            label=r'$p_\mathrm{recit}$')

    if len(Ts) >= 3:
        dpr = np.gradient(pr, Ts)
        ax2 = ax.twinx()
        ax2.bar(Ts, dpr, width=0.03, color='#E65100', alpha=0.55,
                label=r'$dp/dT$')
        ax2.set_ylabel(r'$dp_\mathrm{recit}/dT$', color='#E65100', fontsize=9)
        ax2.tick_params(axis='y', labelcolor='#E65100')
        lines2, labs2 = ax2.get_legend_handles_labels()
    else:
        lines2, labs2 = [], []

    ax.axhline(0, color='gray', lw=0.7, ls='--')
    ax.set_xlim(1.0, 3.2)
    ax.set_ylim(-0.02, 1.0)
    ax.set_xlabel('Temperature T', fontsize=10)
    ax.set_ylabel(r'$p_\mathrm{recit}$', fontsize=10)
    ax.set_title(f'N={N}', fontsize=11, fontweight='bold')
    lines1, labs1 = ax.get_legend_handles_labels()
    ax.legend(lines1+lines2, labs1+labs2, fontsize=8)

plt.tight_layout()
plt.savefig(f'{OUT_DIR}/hysteresis_dpdt.png', dpi=150,
            bbox_inches='tight', facecolor='white')
plt.close()
print('Saved: hysteresis_dpdt.png')

# -----------------------------------------------------------------------
# Print summary table
# -----------------------------------------------------------------------
print('\n=== Hysteresis Summary (Qwen3-14B) ===')
print(f'{"T":>6}  {"N":>2}  {"p_recit":>8}  {"p_loop":>8}  {"p_pm":>8}  {"n":>4}')
for N in N_LIST:
    for T in T_FINE:
        st = cell_stats(SLUG, N, T)
        if st:
            print(f'{T:6.2f}  {N:2d}  {st["p_rec"]:8.3f}  '
                  f'{st["p_loop"]:8.3f}  {st["p_pm"]:8.3f}  {st["n"]:4d}')
    print()
