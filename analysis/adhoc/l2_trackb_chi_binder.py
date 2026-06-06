"""
Track B: goal-peg stratified q_ab, chi_SG, Binder cumulant
"""
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import json, os, glob

OUT_DIR = 'figures/l2_order_param'
os.makedirs(OUT_DIR, exist_ok=True)
LAYER = 'layer_mid'

T_FULL = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
T_COLL = [1.1, 1.2, 1.3, 1.4, 1.5, 1.8, 2.0, 2.5, 3.0]
T_ALL  = T_FULL + T_COLL
N_VALS = [2, 3, 4, 5, 6]

MODELS = [
    ('qwen3-14b',                   'Qwen3-14B',  '#9C27B0'),
    ('deepseek-r1-distill-qwen-7b', 'DeepSeek-7B','#1565C0'),
]

def t_tag(T):
    return str(round(T, 2)).replace('.', '_')

def load_cell(slug, N, T):
    for sweep in ('full_sweep', 'collapse_phase'):
        d = f'results/hanoi/{sweep}/{slug}/N{N}_T{t_tag(T)}'
        sumf = f'{d}/summary.json'
        if not os.path.exists(sumf):
            continue
        with open(sumf) as f:
            meta = json.load(f)
        hidden = []
        for m in meta:
            idx = m['trial']
            p = f'{d}/trial_{idx:03d}_hidden.npz'
            if not os.path.exists(p):
                p = f'{d}/trial_{idx}_hidden.npz'
            if os.path.exists(p):
                hidden.append(np.load(p, allow_pickle=True)[LAYER].astype(np.float32))
            else:
                hidden.append(None)
        return meta, hidden
    return None, None

def classify_trial(m):
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

def final_vec(h):
    return h[-1] if h is not None and len(h) > 0 else None

def pairwise_q(vecs):
    if len(vecs) < 2:
        return np.array([])
    V = np.stack(vecs)
    V = V / (np.linalg.norm(V, axis=1, keepdims=True) + 1e-9)
    G = V @ V.T
    n = len(V)
    i, j = np.triu_indices(n, k=1)
    return G[i, j]

def cell_metrics(slug, N, T):
    """Returns q_ab array (all non-censored trials, stratified by goal peg)."""
    meta, hidden = load_cell(slug, N, T)
    if meta is None:
        return None

    goal_C, goal_B_est, failed = [], [], []
    for m, h in zip(meta, hidden):
        ph = classify_trial(m)
        if ph == 'censored':
            continue
        fv = final_vec(h)
        if fv is None:
            continue
        acc = m.get('accuracy', 0)
        if acc == 1:
            goal_C.append(fv)
        else:
            failed.append(fv)

    return goal_C, failed

def compute_q_stats(vecs_list):
    """From a list of vecs, compute mean-centered q_ab, then q_EA, chi_SG, g4."""
    if len(vecs_list) < 2:
        return dict(q_ea=np.nan, chi_sg=np.nan, g4=np.nan, n=len(vecs_list))
    mu = np.mean(np.stack(vecs_list), axis=0)
    centered = [v - mu for v in vecs_list]
    qs = pairwise_q(centered)
    if len(qs) == 0:
        return dict(q_ea=np.nan, chi_sg=np.nan, g4=np.nan, n=len(vecs_list))
    q2 = np.mean(qs**2)
    q4 = np.mean(qs**4)
    g4 = 0.5 * (3 - q4 / q2**2) if q2 > 1e-12 else np.nan
    return dict(q_ea=float(np.mean(qs)), chi_sg=float(q2),
                g4=float(g4), n=len(vecs_list))

# ---------------------------------------------------------------------------
# Fig 1: q_EA stratified by goal peg (only C-peg trials)
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle(
    r'$q_\mathrm{EA}(T)$ — C-peg goal-reached only  (removes B/C parity artifact)',
    fontsize=12, fontweight='bold')

for ax, (slug, display, col_base) in zip(axes, MODELS):
    colors = plt.cm.viridis(np.linspace(0.15, 0.85, len(N_VALS)))
    for N, col in zip(N_VALS, colors):
        T_pts, qea_pts = [], []
        for T in T_ALL:
            res = cell_metrics(slug, N, T)
            if res is None:
                continue
            goal_C, _ = res
            stats = compute_q_stats(goal_C)
            if not np.isnan(stats['q_ea']) and stats['n'] >= 2:
                T_pts.append(T)
                qea_pts.append(stats['q_ea'])
        if T_pts:
            ax.plot(T_pts, qea_pts, 'o-', color=col, markersize=4,
                    linewidth=1.6, label=f'N={N}')

    ax.axhline(0, color='gray', lw=0.8, ls='--', alpha=0.5)
    ax.axvline(1.0, color='gray', lw=0.8, ls=':', alpha=0.4)
    ax.set_xlabel('Temperature T', fontsize=10)
    ax.set_ylabel(r'$q_\mathrm{EA}$ (C-peg trials)', fontsize=10)
    ax.set_title(display, fontsize=11, fontweight='bold')
    ax.legend(fontsize=8)
    ax.set_xlim(0, 3.2)

plt.tight_layout()
plt.savefig(f'{OUT_DIR}/qea_stratified.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print('Saved: qea_stratified.png')

# ---------------------------------------------------------------------------
# Fig 2: chi_SG and Binder g4 — all non-censored trials
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle(
    r'Phase boundary metrics: $\chi_\mathrm{SG}(T,N)$ and Binder $g_4(T,N)$',
    fontsize=13, fontweight='bold')

for col_idx, (slug, display, _) in enumerate(MODELS):
    ax_chi  = axes[0, col_idx]
    ax_bind = axes[1, col_idx]
    colors = plt.cm.plasma(np.linspace(0.1, 0.85, len(N_VALS)))

    for N, col in zip(N_VALS, colors):
        T_pts, chi_pts, g4_pts = [], [], []
        for T in T_ALL:
            meta, hidden = load_cell(slug, N, T)
            if meta is None:
                continue
            all_vecs = []
            for m, h in zip(meta, hidden):
                if classify_trial(m) == 'censored':
                    continue
                fv = final_vec(h)
                if fv is not None:
                    all_vecs.append(fv)
            stats = compute_q_stats(all_vecs)
            if stats['n'] < 2:
                continue
            T_pts.append(T)
            chi_pts.append(stats['chi_sg'])
            g4_pts.append(stats['g4'])

        ls = ['-', '--', '-.', ':', (0,(3,1,1,1))][ N_VALS.index(N) ]
        if T_pts:
            ax_chi.plot(T_pts, chi_pts, marker='o', markersize=3.5,
                        linestyle=ls, color=col, linewidth=1.6, label=f'N={N}')
            g4_clean = [g if not np.isnan(g) else None for g in g4_pts]
            T_g4 = [t for t, g in zip(T_pts, g4_clean) if g is not None]
            g4_ok = [g for g in g4_clean if g is not None]
            if T_g4:
                ax_bind.plot(T_g4, g4_ok, marker='s', markersize=3.5,
                             linestyle=ls, color=col, linewidth=1.6, label=f'N={N}')

    for ax, ylabel, title in [
        (ax_chi,  r'$\chi_\mathrm{SG} = \langle q_{ab}^2 \rangle$',
                  f'{display}  —  SG susceptibility'),
        (ax_bind, r'$g_4 = (1/2)(3 - \langle q^4\rangle/\langle q^2\rangle^2)$',
                  f'{display}  —  Binder cumulant'),
    ]:
        ax.axvline(1.0, color='gray', lw=0.8, ls=':', alpha=0.4)
        ax.set_xlabel('Temperature T', fontsize=10)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_title(title, fontsize=10)
        ax.legend(fontsize=8, ncol=2)
        ax.set_xlim(0, 3.2)

    ax_bind.axhline(0, color='gray', lw=0.8, ls='--', alpha=0.5)
    ax_bind.axhline(1, color='gray', lw=0.8, ls='--', alpha=0.3)

plt.tight_layout()
plt.savefig(f'{OUT_DIR}/chi_binder.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print('Saved: chi_binder.png')

# ---------------------------------------------------------------------------
# Fig 3: Binder crossing zoom — N curves on same plot, look for Tc crossing
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle(
    r'Binder cumulant $g_4(T)$ — N crossing indicates $T_c$',
    fontsize=12, fontweight='bold')

for ax, (slug, display, _) in zip(axes, MODELS):
    colors = plt.cm.viridis(np.linspace(0.1, 0.9, len(N_VALS)))
    for N, col in zip(N_VALS, colors):
        T_pts, g4_pts = [], []
        for T in T_ALL:
            meta, hidden = load_cell(slug, N, T)
            if meta is None:
                continue
            all_vecs = [final_vec(h) for m, h in zip(meta, hidden)
                        if classify_trial(m) != 'censored' and final_vec(h) is not None]
            stats = compute_q_stats(all_vecs)
            if stats['n'] >= 2 and not np.isnan(stats['g4']):
                T_pts.append(T)
                g4_pts.append(stats['g4'])
        if T_pts:
            ax.plot(T_pts, g4_pts, 'o-', color=col, markersize=4,
                    linewidth=1.8, label=f'N={N}')

    ax.axhline(0, color='k', lw=1.0, ls='--', alpha=0.4)
    ax.axhline(1, color='k', lw=0.8, ls=':', alpha=0.3)
    ax.set_xlabel('Temperature T', fontsize=10)
    ax.set_ylabel(r'$g_4$', fontsize=10)
    ax.set_title(display, fontsize=11, fontweight='bold')
    ax.legend(fontsize=8)
    ax.set_xlim(0, 3.2)
    ax.set_ylim(-2, 3)

plt.tight_layout()
plt.savefig(f'{OUT_DIR}/binder_crossing.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print('Saved: binder_crossing.png')

print('All Track B figures saved to', OUT_DIR)
