"""
L2 order parameter analysis
  - Proper per-trial replica pair q_ab  (Problem 1)
  - Per-move time-direction overlap      (Problem 2)
  - m = h . xi^1                         (Problem 3)
  - P(q) comparison across phases
"""
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import json, os, glob

OUT_DIR = 'figures/l2_order_param'
os.makedirs(OUT_DIR, exist_ok=True)

LAYER = 'layer_mid'

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def t_tag(T):
    return str(round(T, 2)).replace('.', '_')

def load_cell(slug, N, T):
    """Returns (trials_meta, hidden_list) or (None, None)."""
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
                npz = np.load(p, allow_pickle=True)
                hidden.append(npz[LAYER].astype(np.float32))
            else:
                hidden.append(None)
        return meta, hidden
    return None, None

def classify_trial(m):
    acc = m.get('accuracy', 0)
    es  = m.get('early_stop')
    nm  = m.get('num_moves', 0) or 1
    tpm = m.get('total_tokens', 0) / nm
    if acc == 1:
        return 'recitation' if tpm < 15 else 'reasoning'
    if es in ('move_loop_repeat', 'move_loop_reverse'):
        return 'move_loop'
    if es == 'think_budget':
        return 'censored'
    return 'pm'

def final_vec(h_array):
    """Last-move hidden state vector."""
    if h_array is None or len(h_array) == 0:
        return None
    return h_array[-1]

def pairwise_cosine(vecs):
    """All pairwise cosine similarities; returns flat array."""
    if len(vecs) < 2:
        return np.array([])
    V = np.stack(vecs)
    norms = np.linalg.norm(V, axis=1, keepdims=True) + 1e-9
    V = V / norms
    G = V @ V.T
    n = len(vecs)
    idx = np.triu_indices(n, k=1)
    return G[idx]

def mean_center(vecs_list):
    """Subtract cell-level mean from a list of vectors."""
    all_v = [v for v in vecs_list if v is not None]
    if not all_v:
        return vecs_list
    mu = np.mean(np.stack(all_v), axis=0)
    return [v - mu if v is not None else None for v in vecs_list]

def compute_xi1(slug, N_list, T_list):
    """xi^1 = mean final-move h of reasoning trials at low T."""
    vecs = []
    for T in T_list:
        for N in N_list:
            meta, hidden = load_cell(slug, N, T)
            if meta is None:
                continue
            for m, h in zip(meta, hidden):
                if classify_trial(m) == 'reasoning' and h is not None:
                    vecs.append(final_vec(h))
    if not vecs:
        return None
    xi = np.mean(np.stack(vecs), axis=0)
    xi /= np.linalg.norm(xi) + 1e-9
    return xi

def proj_onto(vecs, ref):
    """Cosine projection of each vec onto ref."""
    ref_n = ref / (np.linalg.norm(ref) + 1e-9)
    return [float(np.dot(v, ref_n) / (np.linalg.norm(v) + 1e-9))
            if v is not None else None for v in vecs]

# ---------------------------------------------------------------------------
# figure 1: P(q) per phase -- qwen3-14b vs deepseek-7b
# ---------------------------------------------------------------------------

CELLS = [
    # (slug,        N, T,   label)
    ('qwen3-14b',                    3, 0.6,  'Qwen3-14B  N=3 T=0.6\n(reasoning zone)'),
    ('qwen3-14b',                    3, 1.5,  'Qwen3-14B  N=3 T=1.5\n(recitation zone)'),
    ('qwen3-14b',                    3, 2.5,  'Qwen3-14B  N=3 T=2.5\n(PM zone)'),
    ('deepseek-r1-distill-qwen-7b',  3, 0.6,  'DeepSeek-7B  N=3 T=0.6\n(reasoning zone)'),
    ('deepseek-r1-distill-qwen-7b',  3, 1.1,  'DeepSeek-7B  N=3 T=1.1\n(SG/PM boundary)'),
    ('deepseek-r1-distill-qwen-7b',  3, 1.5,  'DeepSeek-7B  N=3 T=1.5\n(PM zone)'),
]

PHASE_COLORS = {
    'reasoning':  '#1565C0',
    'recitation': '#00ACC1',
    'move_loop':  '#E65100',
    'pm':         '#B71C1C',
}

fig, axes = plt.subplots(2, 3, figsize=(15, 8))
fig.suptitle(
    r'$P(q)$ from per-trial replica pairs  (cell-mean-centered, final-move $h$)',
    fontsize=13, fontweight='bold'
)

for ax, (slug, N, T, label) in zip(axes.flat, CELLS):
    meta, hidden = load_cell(slug, N, T)
    if meta is None:
        ax.set_title(label + '\n[no data]'); continue

    by_phase = {'reasoning': [], 'recitation': [], 'move_loop': [], 'pm': []}
    for m, h in zip(meta, hidden):
        ph = classify_trial(m)
        if ph in by_phase:
            fv = final_vec(h)
            if fv is not None:
                by_phase[ph].append(fv)

    all_vecs = [v for ph_vecs in by_phase.values() for v in ph_vecs]
    all_vecs_c = mean_center(all_vecs)
    offset = 0
    centered_by_phase = {}
    for ph, vl in by_phase.items():
        centered_by_phase[ph] = all_vecs_c[offset:offset+len(vl)]
        offset += len(vl)

    has_data = False
    for ph, col in PHASE_COLORS.items():
        vl = centered_by_phase[ph]
        if len(vl) < 2:
            continue
        qs = pairwise_cosine(vl)
        if len(qs) == 0:
            continue
        ax.hist(qs, bins=20, range=(-1, 1), density=True,
                color=col, alpha=0.65, label=f'{ph} (n={len(vl)})', edgecolor='none')
        q_ea = float(np.mean(qs))
        ax.axvline(q_ea, color=col, linewidth=1.5, linestyle='--', alpha=0.8)
        has_data = True

    ax.set_xlim(-1.1, 1.1)
    ax.set_xlabel(r'$q_{ab}$ (cosine)', fontsize=9)
    ax.set_ylabel('density', fontsize=9)
    ax.set_title(label, fontsize=9, pad=4)
    ax.axvline(0, color='black', linewidth=0.8, alpha=0.4)
    if has_data:
        ax.legend(fontsize=7, framealpha=0.85)

plt.tight_layout()
plt.savefig(f'{OUT_DIR}/pq_per_phase.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print('Saved: pq_per_phase.png')

# ---------------------------------------------------------------------------
# figure 2: per-move overlap matrix (time direction)
# ---------------------------------------------------------------------------

fig, axes = plt.subplots(2, 3, figsize=(14, 8))
fig.suptitle(
    r'Per-move overlap $C(t_1, t_2)$ within trial  (cell-mean-centered)',
    fontsize=13, fontweight='bold'
)

OVERLAP_CELLS = [
    ('qwen3-14b', 3, 0.6,  'Qwen3-14B N=3 T=0.6\nreasoning',    'reasoning'),
    ('qwen3-14b', 3, 1.5,  'Qwen3-14B N=3 T=1.5\nrecitation',   'recitation'),
    ('qwen3-14b', 3, 1.5,  'Qwen3-14B N=3 T=1.5\nmove_loop',    'move_loop'),
    ('deepseek-r1-distill-qwen-7b', 3, 0.6,  'DeepSeek-7B N=3 T=0.6\nreasoning', 'reasoning'),
    ('deepseek-r1-distill-qwen-7b', 3, 1.1,  'DeepSeek-7B N=3 T=1.1\nmove_loop', 'move_loop'),
    ('deepseek-r1-distill-qwen-7b', 3, 1.1,  'DeepSeek-7B N=3 T=1.1\npm',        'pm'),
]

for ax, (slug, N, T, label, target_ph) in zip(axes.flat, OVERLAP_CELLS):
    meta, hidden = load_cell(slug, N, T)
    if meta is None:
        ax.set_title(label + '\n[no data]'); continue

    trial_vecs = []
    for m, h in zip(meta, hidden):
        if classify_trial(m) == target_ph and h is not None and len(h) >= 2:
            trial_vecs.append(h.astype(np.float32))

    if len(trial_vecs) == 0:
        ax.set_title(label + '\n[no trials]'); continue

    max_moves = min(max(len(v) for v in trial_vecs), 12)
    acc_mat = np.zeros((max_moves, max_moves))
    cnt_mat = np.zeros((max_moves, max_moves))

    for h_trial in trial_vecs:
        T_len = min(len(h_trial), max_moves)
        sub = h_trial[:T_len].copy()
        sub -= sub.mean(axis=0)
        norms = np.linalg.norm(sub, axis=1, keepdims=True) + 1e-9
        sub_n = sub / norms
        G = sub_n @ sub_n.T
        acc_mat[:T_len, :T_len] += G
        cnt_mat[:T_len, :T_len] += 1

    with np.errstate(invalid='ignore'):
        mean_mat = np.where(cnt_mat > 0, acc_mat / cnt_mat, np.nan)

    valid = ~np.isnan(mean_mat)
    vmin, vmax = -1, 1

    im = ax.imshow(mean_mat, vmin=vmin, vmax=vmax, cmap='RdBu_r',
                   aspect='auto', interpolation='nearest')
    ax.set_title(label + f'\n(n={len(trial_vecs)} trials)', fontsize=9, pad=4)
    ax.set_xlabel('move step $t_2$', fontsize=8)
    ax.set_ylabel('move step $t_1$', fontsize=8)
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

plt.tight_layout()
plt.savefig(f'{OUT_DIR}/per_move_overlap.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print('Saved: per_move_overlap.png')

# ---------------------------------------------------------------------------
# figure 3: m = h . xi^1  vs  accuracy
# ---------------------------------------------------------------------------

print('Computing xi^1 for qwen3-14b (low-T reasoning trials)...')
xi1_qwen = compute_xi1('qwen3-14b', [3, 4], [0.1, 0.2, 0.3])
xi1_dsq7 = compute_xi1('deepseek-r1-distill-qwen-7b', [3, 4], [0.1, 0.2, 0.3])

SCAN_CELLS = [
    ('qwen3-14b', 3,
     [0.1, 0.3, 0.6, 0.9, 1.1, 1.3, 1.5, 1.8, 2.0, 2.5, 3.0], xi1_qwen),
    ('deepseek-r1-distill-qwen-7b', 3,
     [0.1, 0.3, 0.6, 0.9, 1.1, 1.3, 1.5, 1.8, 2.0, 2.5, 3.0], xi1_dsq7),
]

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle(
    r'$m = \langle h_\mathrm{final} \cdot \hat\xi^1 \rangle$  vs  accuracy  (N=3 scan)',
    fontsize=12, fontweight='bold'
)

for ax, (slug, N, T_list, xi1) in zip(axes, SCAN_CELLS):
    if xi1 is None:
        ax.set_title(f'{slug}\n[xi^1 not available]'); continue

    T_vals, m_means, m_stds, accs = [], [], [], []
    m_by_phase = {ph: {'T': [], 'm': []} for ph in PHASE_COLORS}

    for T in T_list:
        meta, hidden = load_cell(slug, N, T)
        if meta is None:
            continue
        m_vals = []
        for m_trial, h in zip(meta, hidden):
            fv = final_vec(h)
            if fv is None:
                continue
            ph = classify_trial(m_trial)
            proj = float(np.dot(fv / (np.linalg.norm(fv) + 1e-9), xi1))
            m_vals.append(proj)
            if ph in m_by_phase:
                m_by_phase[ph]['T'].append(T)
                m_by_phase[ph]['m'].append(proj)

        if m_vals:
            T_vals.append(T)
            m_means.append(np.mean(m_vals))
            m_stds.append(np.std(m_vals))
            acc = np.mean([mt.get('accuracy', 0) for mt in meta])
            accs.append(acc)

    for ph, col in PHASE_COLORS.items():
        pd = m_by_phase[ph]
        if pd['T']:
            ax.scatter(pd['T'], pd['m'], color=col, alpha=0.35, s=12,
                       zorder=2, label=f'_{ph}')

    ax.errorbar(T_vals, m_means, yerr=m_stds, fmt='ko-',
                capsize=3, linewidth=1.5, markersize=4, label=r'$\langle m \rangle \pm \sigma$',
                zorder=5)

    ax2 = ax.twinx()
    ax2.plot(T_vals, accs, 'r--', linewidth=1.5, label='accuracy', alpha=0.7)
    ax2.set_ylabel('accuracy (symmetric)', color='red', fontsize=9)
    ax2.tick_params(axis='y', labelcolor='red')
    ax2.set_ylim(-0.05, 1.05)

    ax.axhline(0, color='gray', linewidth=0.8, linestyle='--')
    ax.set_xlabel('Temperature T', fontsize=10)
    ax.set_ylabel(r'$m = h_\mathrm{final} \cdot \hat\xi^1$', fontsize=10)
    short = slug.split('/')[-1].replace('deepseek-r1-distill-qwen-', 'DS-').replace('qwen3-', 'Qwen3-')
    ax.set_title(f'{short}  N={N}', fontsize=10)
    ax.set_xlim(0, 3.2)

    handles1, labels1 = ax.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    leg_h = [h for h, l in zip(handles1, labels1) if not l.startswith('_')]
    leg_l = [l for l in labels1 if not l.startswith('_')]
    ax.legend(leg_h + handles2, leg_l + labels2, fontsize=8, loc='upper right')

plt.tight_layout()
plt.savefig(f'{OUT_DIR}/m_vs_accuracy.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print('Saved: m_vs_accuracy.png')

# ---------------------------------------------------------------------------
# figure 4: q_EA(T) curve  -- foundation for phase boundary
# ---------------------------------------------------------------------------

MODELS_SCAN = [
    ('qwen3-14b',                    'Qwen3-14B',   '#9C27B0'),
    ('deepseek-r1-distill-qwen-7b',  'DeepSeek-7B', '#1565C0'),
]
T_FULL = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
T_COLL = [1.1, 1.2, 1.3, 1.4, 1.5, 1.8, 2.0, 2.5, 3.0]
T_ALL  = T_FULL + T_COLL
N_SCAN = [3, 4, 5]

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle(
    r'$q_\mathrm{EA}(T)$ from per-trial replica pairs  '
    r'(= $\overline{q_{ab}}$, cell-mean-centered)',
    fontsize=12, fontweight='bold'
)

for ax, (slug, display, _) in zip(axes, MODELS_SCAN):
    for N, ls in zip(N_SCAN, ('-', '--', '-.')):
        T_pts, qEA_pts = [], []
        for T in T_ALL:
            meta, hidden = load_cell(slug, N, T)
            if meta is None:
                continue
            fvecs = []
            for m, h in zip(meta, hidden):
                if classify_trial(m) != 'censored':
                    fv = final_vec(h)
                    if fv is not None:
                        fvecs.append(fv)
            if len(fvecs) < 2:
                continue
            fvecs_c = mean_center(fvecs)
            qs = pairwise_cosine(fvecs_c)
            if len(qs) == 0:
                continue
            T_pts.append(T)
            qEA_pts.append(float(np.mean(qs)))

        if T_pts:
            ax.plot(T_pts, qEA_pts, marker='o', markersize=4, linestyle=ls,
                    linewidth=1.8, label=f'N={N}')

    ax.axhline(0, color='gray', linewidth=0.8, linestyle='--', alpha=0.6)
    ax.axvline(1.0, color='gray', linewidth=0.8, linestyle=':', alpha=0.5)
    ax.set_xlabel('Temperature T', fontsize=10)
    ax.set_ylabel(r'$q_\mathrm{EA} = \langle q_{ab} \rangle$', fontsize=10)
    ax.set_title(display, fontsize=11, fontweight='bold')
    ax.legend(fontsize=9)
    ax.set_xlim(0, 3.2)

plt.tight_layout()
plt.savefig(f'{OUT_DIR}/qea_vs_T.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print('Saved: qea_vs_T.png')

print('All figures saved to', OUT_DIR)
