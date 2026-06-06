"""
Track B Part 2: H-3, H-2, L-1, Q1
  H-3: recitation-only q_EA(T) vs p_recit(T) -- temperature alignment check
  H-2: basin count (clustering) for recitation hidden states
  L-1: N=4,5 recitation window confirmation
  Q1:  Omega proxy -- covariance log-volume / participation ratio
"""
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import json, os, glob
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import pdist

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

def pairwise_q(vecs):
    if len(vecs)<2: return np.array([])
    V = np.stack(vecs)
    V /= np.linalg.norm(V,axis=1,keepdims=True)+1e-9
    G = V @ V.T
    i,j = np.triu_indices(len(V),k=1)
    return G[i,j]

def q_ea_for_group(slug, N, T, target_phase):
    meta, hidden = load_cell(slug,N,T)
    if meta is None: return np.nan, 0
    vecs = [final_vec(h) for m,h in zip(meta,hidden)
            if classify(m)==target_phase and final_vec(h) is not None]
    if len(vecs)<2: return np.nan, len(vecs)
    mu = np.mean(np.stack(vecs),axis=0)
    centered = [v-mu for v in vecs]
    qs = pairwise_q(centered)
    return float(np.mean(qs)) if len(qs)>0 else np.nan, len(vecs)

# ===========================================================================
# H-3: recitation q_EA(T) vs p_recit(T)
# ===========================================================================
print('H-3: recitation q_EA vs p_recit...')
fig, axes = plt.subplots(1,2,figsize=(13,5))
fig.suptitle(
    r'H-3: recitation-group $q_\mathrm{EA}(T)$ vs $p_\mathrm{recit}(T)$  '
    r'(alignment confirms inverse-melting temperature)',
    fontsize=11, fontweight='bold')

for ax, slug, display in [
    (axes[0],'qwen3-14b','Qwen3-14B'),
    (axes[1],'deepseek-r1-distill-qwen-7b','DeepSeek-7B'),
]:
    for N, col in zip([3,4,5],['#1565C0','#E65100','#388E3C']):
        T_pts, qea_pts, pr_pts = [],[],[]
        for T in T_ALL:
            meta, hidden = load_cell(slug,N,T)
            if meta is None: continue
            phases = [classify(m) for m in meta]
            p_rec = phases.count('recitation')/len(phases)
            qea, n = q_ea_for_group(slug,N,T,'recitation')
            if n>=2:
                T_pts.append(T); qea_pts.append(qea); pr_pts.append(p_rec)
        if not T_pts: continue
        ax.plot(T_pts, qea_pts, 'o-', color=col, lw=1.8, ms=4,
                label=f'N={N} $q_{{EA}}$')
        ax2 = ax.twinx() if N==3 else ax.twinx()
        ax.plot(T_pts, pr_pts, 's--', color=col, lw=1.2, ms=3,
                alpha=0.55, label=f'N={N} $p_{{recit}}$')
    ax.axhline(0,color='gray',lw=0.7,ls='--')
    ax.set_xlabel('Temperature T',fontsize=10)
    ax.set_ylabel(r'$q_\mathrm{EA}$ / $p_\mathrm{recit}$',fontsize=9)
    ax.set_title(display,fontsize=11,fontweight='bold')
    ax.legend(fontsize=7,ncol=2,loc='upper left')
    ax.set_xlim(0,3.2)

plt.tight_layout()
plt.savefig(f'{OUT_DIR}/h3_qea_vs_precit.png',dpi=150,bbox_inches='tight',facecolor='white')
plt.close()
print('  Saved: h3_qea_vs_precit.png')

# ===========================================================================
# H-2: basin count via hierarchical clustering on recitation hidden states
# ===========================================================================
print('H-2: basin count clustering...')
SLUG = 'qwen3-14b'
N_H2 = 3
T_H2_LIST = [1.3, 1.5, 2.0]

fig, axes = plt.subplots(1, len(T_H2_LIST)+1, figsize=(16,5))
fig.suptitle(
    r'H-2: recitation basin structure  (hierarchical clustering, cosine dist)',
    fontsize=11, fontweight='bold')

omega_data = {}
for ax, T in zip(axes[:len(T_H2_LIST)], T_H2_LIST):
    meta, hidden = load_cell(SLUG, N_H2, T)
    if meta is None:
        ax.set_title(f'T={T}\n[no data]'); continue

    rec_vecs = [final_vec(h) for m,h in zip(meta,hidden)
                if classify(m)=='recitation' and final_vec(h) is not None]
    rea_vecs = [final_vec(h) for m,h in zip(meta,hidden)
                if classify(m)=='reasoning' and final_vec(h) is not None]

    if len(rec_vecs)<2:
        ax.set_title(f'T={T}\n(n_recit={len(rec_vecs)}<2)'); continue

    V = np.stack(rec_vecs)
    V /= np.linalg.norm(V,axis=1,keepdims=True)+1e-9
    cos_dist = pdist(V,'cosine')
    Z = linkage(cos_dist,'ward')
    # count clusters at distance threshold 0.15
    for thresh in [0.05, 0.10, 0.15, 0.20]:
        labels = fcluster(Z, t=thresh, criterion='distance')
        n_clust = len(set(labels))
        if n_clust > 1:
            break

    labels_plot = fcluster(Z, t=0.10, criterion='distance')
    n_clust = len(set(labels_plot))
    omega_data[T] = {'n_clust': n_clust, 'n_recit': len(rec_vecs),
                     'n_reason': len(rea_vecs)}

    q_within, q_between = [], []
    for c in set(labels_plot):
        idx = np.where(labels_plot==c)[0]
        if len(idx)>=2:
            sub = V[idx]
            G = sub @ sub.T
            ii,jj = np.triu_indices(len(idx),k=1)
            q_within.extend(G[ii,jj].tolist())
        for c2 in set(labels_plot):
            if c2<=c: continue
            idx2 = np.where(labels_plot==c2)[0]
            cross = V[idx] @ V[idx2].T
            q_between.extend(cross.flatten().tolist())

    bins = np.linspace(-1,1,30)
    if q_within:
        ax.hist(q_within, bins=bins, density=True, color='#1565C0',
                alpha=0.6, label=f'within-basin (n={len(q_within)})')
    if q_between:
        ax.hist(q_between, bins=bins, density=True, color='#E65100',
                alpha=0.6, label=f'between-basin (n={len(q_between)})')
    ax.axvline(0,color='gray',lw=0.8,ls='--')
    ax.set_title(f'T={T}  n_recit={len(rec_vecs)}\nΩ≈{n_clust} basins',fontsize=9)
    ax.set_xlabel(r'$q_{ab}$ (raw cosine)',fontsize=8)
    ax.legend(fontsize=7)

ax_sum = axes[-1]
if omega_data:
    Ts = sorted(omega_data.keys())
    ns = [omega_data[t]['n_clust'] for t in Ts]
    ax_sum.bar([str(t) for t in Ts], ns, color='#9C27B0', alpha=0.7)
    ax_sum.set_ylabel('Estimated Ω (basin count)',fontsize=10)
    ax_sum.set_xlabel('Temperature T',fontsize=10)
    ax_sum.set_title('Qwen3-14B N=3\nΩ estimate',fontsize=10)
    for i,(t,n) in enumerate(zip(Ts,ns)):
        ax_sum.text(i, n+0.05, str(n), ha='center', fontsize=11, fontweight='bold')

plt.tight_layout()
plt.savefig(f'{OUT_DIR}/h2_basin_count.png',dpi=150,bbox_inches='tight',facecolor='white')
plt.close()
print('  Saved: h2_basin_count.png')

# ===========================================================================
# L-1 + Q1: N=4,5 window & Omega proxy (participation ratio)
# ===========================================================================
print('L-1 / Q1: N scan + participation ratio...')

def participation_ratio(vecs):
    if len(vecs)<3: return np.nan
    V = np.stack(vecs).astype(np.float32)
    V -= V.mean(axis=0)
    k = min(len(vecs)-1, 30)
    _, s, _ = np.linalg.svd(V, full_matrices=False)
    s = s[:k]**2
    s = s[s>1e-12]
    if len(s)==0: return np.nan
    return float((s.sum()**2) / (s**2).sum())

fig, axes = plt.subplots(2, 2, figsize=(13,9))
fig.suptitle(
    'L-1 / Q1: recitation window across N and Ω proxy (participation ratio)',
    fontsize=11, fontweight='bold')

for row, slug, display in [
    (0,'qwen3-14b','Qwen3-14B'),
    (1,'deepseek-r1-distill-qwen-7b','DeepSeek-7B'),
]:
    ax_pr  = axes[row,0]
    ax_prx = axes[row,1]
    colors = plt.cm.viridis(np.linspace(0.1,0.85,5))

    for N_idx, (N, col) in enumerate(zip([2,3,4,5,6], colors)):
        T_pts_rec, pr_rec = [],[]
        T_pts_rea, pr_rea = [],[]
        T_pts_sg,  pr_sg  = [],[]

        for T in T_ALL:
            meta, hidden = load_cell(slug,N,T)
            if meta is None: continue

            groups = {'recitation':[],'reasoning':[],'move_loop':[]}
            for m,h in zip(meta,hidden):
                ph = classify(m)
                fv = final_vec(h)
                if ph in groups and fv is not None:
                    groups[ph].append(fv)

            p_rec  = len(groups['recitation'])
            p_rea  = len(groups['reasoning'])
            p_loop = len(groups['move_loop'])
            total  = sum(len(v) for v in groups.values()) or 1

            T_pts_rec.append(T); pr_rec.append(p_rec/total)
            T_pts_rea.append(T); pr_rea.append(p_rea/total)
            T_pts_sg.append(T);  pr_sg.append(p_loop/total)

        ax_pr.plot(T_pts_rec, pr_rec, 'o-', color=col, lw=1.6, ms=3,
                   label=f'N={N}' if row==0 else '')

        T_pts_prx, prx_rec, prx_rea = [],[],[]
        for T in T_ALL:
            meta, hidden = load_cell(slug,N,T)
            if meta is None: continue
            rv = [final_vec(h) for m,h in zip(meta,hidden)
                  if classify(m)=='recitation' and final_vec(h) is not None]
            av = [final_vec(h) for m,h in zip(meta,hidden)
                  if classify(m)=='reasoning' and final_vec(h) is not None]
            pr_r = participation_ratio(rv)
            pr_a = participation_ratio(av)
            if not (np.isnan(pr_r) and np.isnan(pr_a)):
                T_pts_prx.append(T)
                prx_rec.append(pr_r)
                prx_rea.append(pr_a)
        if T_pts_prx:
            rec_clean = [(t,p) for t,p in zip(T_pts_prx,prx_rec) if not np.isnan(p)]
            rea_clean = [(t,p) for t,p in zip(T_pts_prx,prx_rea) if not np.isnan(p)]
            if rec_clean:
                ax_prx.plot(*zip(*rec_clean), 'o-', color=col, lw=1.4, ms=3,
                            label=f'N={N} recit' if row==0 else '')
            if rea_clean:
                ax_prx.plot(*zip(*rea_clean), 's--', color=col, lw=1.0, ms=2.5,
                            alpha=0.5, label=f'N={N} reason' if row==0 else '')

    ax_pr.axvline(1.0,color='gray',lw=0.8,ls=':',alpha=0.4)
    ax_pr.set_xlabel('Temperature T',fontsize=9)
    ax_pr.set_ylabel(r'$p_\mathrm{recit}(T)$',fontsize=9)
    ax_pr.set_title(f'{display}  —  recitation fraction',fontsize=10)
    ax_pr.legend(fontsize=7,ncol=2)
    ax_pr.set_xlim(0,3.2); ax_pr.set_ylim(-0.02,1.02)

    ax_prx.axvline(1.0,color='gray',lw=0.8,ls=':',alpha=0.4)
    ax_prx.set_xlabel('Temperature T',fontsize=9)
    ax_prx.set_ylabel('Participation ratio (Ω proxy)',fontsize=9)
    ax_prx.set_title(f'{display}  —  Q1 Ω proxy',fontsize=10)
    if row==0: ax_prx.legend(fontsize=7,ncol=2)
    ax_prx.set_xlim(0,3.2)

plt.tight_layout()
plt.savefig(f'{OUT_DIR}/l1q1_n_scan_omega.png',dpi=150,bbox_inches='tight',facecolor='white')
plt.close()
print('  Saved: l1q1_n_scan_omega.png')

print('Track B Part 2 complete.')
