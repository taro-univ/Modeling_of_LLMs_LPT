"""
H-3 fix: raw cosine approach
  - q_EA_raw = mean pairwise cosine BEFORE centering (recitation group)
  - p_recit(T) on same axis
  - Also: cross-group cosine (recitation vs reasoning) to check separation
"""
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import json, os

OUT_DIR = 'figures/l2_order_param'
os.makedirs(OUT_DIR, exist_ok=True)
LAYER = 'layer_mid'

T_ALL = [0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,
         1.0,1.1,1.2,1.3,1.4,1.5,1.8,2.0,2.5,3.0]

def t_tag(T):
    return str(round(T,2)).replace('.','_')

def load_cell(slug, N, T):
    for sweep in ('full_sweep','collapse_phase'):
        d = f'results/hanoi/{sweep}/{slug}/N{N}_T{t_tag(T)}'
        s = f'{d}/summary.json'
        if not os.path.exists(s):
            continue
        with open(s) as f:
            meta = json.load(f)
        hidden = []
        for m in meta:
            idx = m['trial']
            p = f'{d}/trial_{idx:03d}_hidden.npz'
            if not os.path.exists(p):
                p = f'{d}/trial_{idx}_hidden.npz'
            hidden.append(np.load(p,allow_pickle=True)[LAYER].astype(np.float32)
                          if os.path.exists(p) else None)
        return meta, hidden
    return None, None

def classify(m):
    acc = m.get('accuracy',0)
    es  = m.get('early_stop')
    nm  = max(m.get('num_moves',1) or 1, 1)
    tpm = m.get('total_tokens',0) / nm
    if acc==1: return 'recitation' if tpm<15 else 'reasoning'
    if es in ('move_loop_repeat','move_loop_reverse'): return 'move_loop'
    if es=='think_budget': return 'censored'
    return 'pm'

def final_vec(h):
    return h[-1] if h is not None and len(h)>0 else None

def normed(v):
    return v / (np.linalg.norm(v) + 1e-9)

def raw_pairwise_q(vecs):
    if len(vecs) < 2: return np.nan, 0
    V = np.stack([normed(v) for v in vecs])
    G = V @ V.T
    n = len(V)
    i, j = np.triu_indices(n, k=1)
    qs = G[i, j]
    return float(np.mean(qs)), len(qs)

def cross_group_q(vecs_a, vecs_b):
    if len(vecs_a) == 0 or len(vecs_b) == 0: return np.nan
    A = np.stack([normed(v) for v in vecs_a])
    B = np.stack([normed(v) for v in vecs_b])
    return float(np.mean(A @ B.T))

# -----------------------------------------------------------------------
# Compute xi^1 from low-T reasoning trials
# -----------------------------------------------------------------------
def compute_xi1(slug, N_list, T_list):
    vecs = []
    for T in T_list:
        for N in N_list:
            meta, hidden = load_cell(slug, N, T)
            if meta is None: continue
            for m, h in zip(meta, hidden):
                fv = final_vec(h)
                if classify(m) == 'reasoning' and fv is not None:
                    vecs.append(normed(fv))
    if not vecs: return None
    xi = np.mean(np.stack(vecs), axis=0)
    return normed(xi)

# -----------------------------------------------------------------------
# Fig 1: raw q_EA(T) for recitation group + p_recit(T) — Qwen3-14B
# -----------------------------------------------------------------------
SLUG = 'qwen3-14b'
xi1 = compute_xi1(SLUG, [3,4], [0.1, 0.2, 0.3])
print(f'xi^1 computed: {xi1 is not None}')

fig, axes = plt.subplots(2, 2, figsize=(14, 9))
fig.suptitle(
    r'H-3 (raw cosine): recitation $q_\mathrm{EA}^\mathrm{raw}(T)$ vs $p_\mathrm{recit}(T)$'
    '\nQwen3-14B  (no mean-centering — avoids single-basin artifact)',
    fontsize=11, fontweight='bold')

N_LIST = [3, 4]
colors = {'3': '#1565C0', '4': '#E65100', '5': '#388E3C'}

for row, N in enumerate(N_LIST):
    ax_q  = axes[row, 0]
    ax_xi = axes[row, 1]

    T_pts, qea_raw, p_rec, cross_qr = [], [], [], []
    proj_rec, proj_rea = [], []

    for T in T_ALL:
        meta, hidden = load_cell(SLUG, N, T)
        if meta is None: continue

        rec_vecs, rea_vecs, all_vecs = [], [], []
        for m, h in zip(meta, hidden):
            ph = classify(m)
            fv = final_vec(h)
            if fv is None or ph == 'censored': continue
            all_vecs.append(fv)
            if ph == 'recitation': rec_vecs.append(fv)
            elif ph == 'reasoning': rea_vecs.append(fv)

        n_total = len(all_vecs) or 1
        p_rec.append(len(rec_vecs) / n_total)

        q_raw, npairs = raw_pairwise_q(rec_vecs)
        qea_raw.append(q_raw)

        cq = cross_group_q(rec_vecs, rea_vecs)
        cross_qr.append(cq)

        if xi1 is not None:
            pr_m = float(np.mean([np.dot(normed(v), xi1) for v in rec_vecs])) \
                   if rec_vecs else np.nan
            pa_m = float(np.mean([np.dot(normed(v), xi1) for v in rea_vecs])) \
                   if rea_vecs else np.nan
            proj_rec.append(pr_m)
            proj_rea.append(pa_m)
        else:
            proj_rec.append(np.nan)
            proj_rea.append(np.nan)

        T_pts.append(T)

    col = colors[str(N)]
    ax_twin = ax_q.twinx()

    mask_q = [not np.isnan(q) for q in qea_raw]
    T_q  = [T_pts[i] for i in range(len(T_pts)) if mask_q[i]]
    q_ok = [qea_raw[i] for i in range(len(qea_raw)) if mask_q[i]]
    if T_q:
        ax_q.plot(T_q, q_ok, 'o-', color=col, lw=2, ms=5,
                  label=r'$q_\mathrm{EA}^\mathrm{raw}$ (recit group)')

    ax_twin.plot(T_pts, p_rec, 's--', color=col, lw=1.5, ms=4, alpha=0.65,
                 label=r'$p_\mathrm{recit}$')
    ax_twin.set_ylabel(r'$p_\mathrm{recit}$', color=col, fontsize=9)
    ax_twin.set_ylim(-0.02, 1.05)

    mask_c = [not np.isnan(c) for c in cross_qr]
    T_c = [T_pts[i] for i in range(len(T_pts)) if mask_c[i]]
    c_ok= [cross_qr[i] for i in range(len(cross_qr)) if mask_c[i]]
    if T_c:
        ax_q.plot(T_c, c_ok, '^:', color='gray', lw=1.2, ms=3, alpha=0.6,
                  label='recit×reason cross-q')

    ax_q.axhline(0, color='gray', lw=0.7, ls='--')
    ax_q.set_xlim(0, 3.2)
    ax_q.set_xlabel('Temperature T', fontsize=9)
    ax_q.set_ylabel(r'$q_{ab}$ (raw cosine)', fontsize=9)
    ax_q.set_title(f'N={N}  raw $q_\mathrm{{EA}}$ + cross-group', fontsize=10)
    lines1, labs1 = ax_q.get_legend_handles_labels()
    lines2, labs2 = ax_twin.get_legend_handles_labels()
    ax_q.legend(lines1+lines2, labs1+labs2, fontsize=7, loc='lower left')

    if xi1 is not None:
        mask_p = [not np.isnan(v) for v in proj_rec]
        T_p = [T_pts[i] for i in range(len(T_pts)) if mask_p[i]]
        pr_ok = [proj_rec[i] for i in range(len(proj_rec)) if mask_p[i]]
        pa_ok = [proj_rea[i] for i in range(len(proj_rea)) if mask_p[i]]
        if T_p:
            ax_xi.plot(T_p, pr_ok, 'o-', color='#00ACC1', lw=2, ms=5,
                       label=r'recitation $\langle h\cdot\hat\xi^1\rangle$')
            ax_xi.plot(T_p, pa_ok, 's--', color='#1565C0', lw=1.5, ms=4,
                       alpha=0.65, label=r'reasoning $\langle h\cdot\hat\xi^1\rangle$')
        ax_xi.axhline(0, color='gray', lw=0.7, ls='--')
        ax_xi2 = ax_xi.twinx()
        ax_xi2.plot(T_pts, p_rec, '^:', color='red', lw=1.2, ms=3,
                    alpha=0.55, label=r'$p_\mathrm{recit}$')
        ax_xi2.set_ylabel(r'$p_\mathrm{recit}$', color='red', fontsize=9)
        ax_xi2.set_ylim(-0.02, 1.05)
        ax_xi.set_xlim(0, 3.2)
        ax_xi.set_xlabel('Temperature T', fontsize=9)
        ax_xi.set_ylabel(r'$m = \langle h\cdot\hat\xi^1\rangle$', fontsize=9)
        ax_xi.set_title(f'N={N}  xi^1 projection', fontsize=10)
        lines1, labs1 = ax_xi.get_legend_handles_labels()
        lines2, labs2 = ax_xi2.get_legend_handles_labels()
        ax_xi.legend(lines1+lines2, labs1+labs2, fontsize=7, loc='lower left')

plt.tight_layout()
out = f'{OUT_DIR}/h3_raw_cosine.png'
plt.savefig(out, dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print(f'Saved: {out}')
