"""
Analyze cosine similarity of hidden state vectors, comparing SG (move_loop_repeat) vs PM (null) trials.
Focuses on N=6, T=0.1 and T=0.2 where both phases are observed.
"""

import json
import numpy as np
from pathlib import Path
from scipy.spatial.distance import cosine


def cosine_sim(a, b):
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return float("nan")
    return float(np.dot(a, b) / (norm_a * norm_b))


def analyze_trial(npz_path, layer="layer_top"):
    d = np.load(npz_path, allow_pickle=True)
    vecs = d[layer]  # shape: (num_moves, dim)
    if len(vecs) < 2:
        return {"mean_consec": float("nan"), "mean_all_pairs": float("nan"),
                "mean_to_centroid": float("nan"), "n_steps": len(vecs)}

    # Consecutive cosine similarity
    consec = [cosine_sim(vecs[i], vecs[i + 1]) for i in range(len(vecs) - 1)]
    consec = [x for x in consec if not np.isnan(x)]

    # All-pair mean (sample up to 20 pairs for speed)
    n = len(vecs)
    pairs = []
    for i in range(min(n, 20)):
        for j in range(i + 1, min(n, 20)):
            pairs.append(cosine_sim(vecs[i], vecs[j]))
    pairs = [x for x in pairs if not np.isnan(x)]

    # Self-similarity: mean cosine sim to centroid
    centroid = vecs.mean(axis=0)
    to_centroid = [cosine_sim(v, centroid) for v in vecs]
    to_centroid = [x for x in to_centroid if not np.isnan(x)]

    return {
        "mean_consec": float(np.mean(consec)) if consec else float("nan"),
        "mean_all_pairs": float(np.mean(pairs)) if pairs else float("nan"),
        "mean_to_centroid": float(np.mean(to_centroid)) if to_centroid else float("nan"),
        "n_steps": n,
    }


def collect(base_dir, condition_dirs, layer="layer_top"):
    results = {"move_loop_repeat": [], "pm_null": []}

    for cond_dir in condition_dirs:
        summary_path = cond_dir / "summary.json"
        if not summary_path.exists():
            continue
        with open(summary_path) as f:
            trials = json.load(f)

        for t in trials:
            trial_num = t["trial"]
            npz_path = cond_dir / f"trial_{trial_num:03d}_hidden.npz"
            if not npz_path.exists():
                continue

            early_stop = t.get("early_stop")
            num_moves = t.get("num_moves", 0)

            stats = analyze_trial(npz_path, layer=layer)
            stats["trial"] = trial_num
            stats["temperature"] = t.get("temperature")
            stats["N"] = t.get("N")
            stats["early_stop"] = early_stop
            stats["num_moves"] = num_moves

            if early_stop == "move_loop_repeat":
                results["move_loop_repeat"].append(stats)
            elif early_stop is None:
                results["pm_null"].append(stats)

    return results


def summarize(group_name, items):
    if not items:
        print(f"  {group_name}: no data")
        return
    vals_consec = [x["mean_consec"] for x in items if not np.isnan(x["mean_consec"])]
    vals_pairs = [x["mean_all_pairs"] for x in items if not np.isnan(x["mean_all_pairs"])]
    vals_centroid = [x["mean_to_centroid"] for x in items if not np.isnan(x["mean_to_centroid"])]
    print(f"  {group_name} (n={len(items)}):")
    if vals_consec:
        print(f"    mean_consec_sim  : {np.mean(vals_consec):.4f} ± {np.std(vals_consec):.4f}  "
              f"[min={np.min(vals_consec):.4f}, max={np.max(vals_consec):.4f}]")
    if vals_pairs:
        print(f"    mean_allpair_sim : {np.mean(vals_pairs):.4f} ± {np.std(vals_pairs):.4f}")
    if vals_centroid:
        print(f"    mean_to_centroid : {np.mean(vals_centroid):.4f} ± {np.std(vals_centroid):.4f}")


def main():
    base = Path("results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b")
    n6_dirs = sorted([d for d in base.iterdir() if d.name.startswith("N6_")])

    print("=" * 60)
    print("N=6 hidden state cosine similarity: SG vs PM")
    print("=" * 60)

    for layer in ["layer_top", "layer_mid", "layer_low"]:
        print(f"\n--- Layer: {layer} ---")
        results = collect(base, n6_dirs, layer=layer)
        summarize("SG (move_loop_repeat)", results["move_loop_repeat"])
        summarize("PM (null early_stop) ", results["pm_null"])

    # Per-temperature breakdown (layer_top only)
    print("\n" + "=" * 60)
    print("Per-temperature breakdown (layer_top)")
    print("=" * 60)
    for temp_label in ["T0_1", "T0_2"]:
        dirs = [d for d in n6_dirs if temp_label in d.name]
        if not dirs:
            continue
        results = collect(base, dirs, layer="layer_top")
        print(f"\nT={temp_label}:")
        summarize("SG", results["move_loop_repeat"])
        summarize("PM", results["pm_null"])

    # Show per-trial detail for N6_T0_1
    print("\n" + "=" * 60)
    print("Per-trial detail: N6_T0_1 (layer_top)")
    print("=" * 60)
    cond_dir = base / "N6_T0_1"
    summary_path = cond_dir / "summary.json"
    with open(summary_path) as f:
        trials = json.load(f)
    print(f"{'trial':>6} {'early_stop':>20} {'n_moves':>8} {'consec':>8} {'all_pair':>9} {'centroid':>9}")
    for t in trials:
        npz_path = cond_dir / f"trial_{t['trial']:03d}_hidden.npz"
        if not npz_path.exists():
            continue
        stats = analyze_trial(npz_path)
        es = t.get("early_stop") or "null"
        print(f"{t['trial']:>6} {es:>20} {t['num_moves']:>8} "
              f"{stats['mean_consec']:>8.4f} {stats['mean_all_pairs']:>9.4f} {stats['mean_to_centroid']:>9.4f}")


if __name__ == "__main__":
    main()
