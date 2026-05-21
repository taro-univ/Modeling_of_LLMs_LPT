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


def _consecutive_sims(vecs: np.ndarray) -> list[float]:
    """隣接ベクトル間のコサイン類似度リストを返す（NaN 除外済み）。"""
    raw = [cosine_sim(vecs[i], vecs[i + 1]) for i in range(len(vecs) - 1)]
    return [x for x in raw if not np.isnan(x)]


def _allpair_sims(vecs: np.ndarray, max_count: int = 20) -> list[float]:
    """全ペアコサイン類似度（最大 max_count×max_count/2 ペア）を返す（NaN 除外済み）。"""
    n = min(len(vecs), max_count)
    raw = [cosine_sim(vecs[i], vecs[j]) for i in range(n) for j in range(i + 1, n)]
    return [x for x in raw if not np.isnan(x)]


def _centroid_sims(vecs: np.ndarray) -> list[float]:
    """各ベクトルの重心へのコサイン類似度リストを返す（NaN 除外済み）。"""
    centroid = vecs.mean(axis=0)
    raw = [cosine_sim(v, centroid) for v in vecs]
    return [x for x in raw if not np.isnan(x)]


def analyze_trial(npz_path, layer="layer_top"):
    d    = np.load(npz_path, allow_pickle=True)
    vecs = d[layer]  # shape: (num_moves, dim)
    n    = len(vecs)
    if n < 2:
        return {"mean_consec": float("nan"), "mean_all_pairs": float("nan"),
                "mean_to_centroid": float("nan"), "n_steps": n}

    consec      = _consecutive_sims(vecs)
    pairs       = _allpair_sims(vecs)
    to_centroid = _centroid_sims(vecs)

    return {
        "mean_consec":      float(np.mean(consec))      if consec      else float("nan"),
        "mean_all_pairs":   float(np.mean(pairs))       if pairs       else float("nan"),
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


def _print_metric(label: str, vals: list[float]) -> None:
    """有効値リストの統計を 1 行で出力する。空の場合は何もしない。"""
    if not vals:
        return
    arr = np.array(vals)
    print(f"    {label}: {arr.mean():.4f} ± {arr.std():.4f}"
          + (f"  [min={arr.min():.4f}, max={arr.max():.4f}]" if label.startswith("mean_consec") else ""))


def summarize(group_name, items):
    if not items:
        print(f"  {group_name}: no data")
        return
    valid = lambda key: [x[key] for x in items if not np.isnan(x[key])]
    print(f"  {group_name} (n={len(items)}):")
    _print_metric("mean_consec_sim  ", valid("mean_consec"))
    _print_metric("mean_allpair_sim ", valid("mean_all_pairs"))
    _print_metric("mean_to_centroid ", valid("mean_to_centroid"))


def _print_layer_comparison(base: Path, n6_dirs: list) -> None:
    """全レイヤーで SG vs PM のコサイン類似度を比較して出力する。"""
    for layer in ["layer_top", "layer_mid", "layer_low"]:
        print(f"\n--- Layer: {layer} ---")
        results = collect(base, n6_dirs, layer=layer)
        summarize("SG (move_loop_repeat)", results["move_loop_repeat"])
        summarize("PM (null early_stop) ", results["pm_null"])


def _print_temp_breakdown(base: Path, n6_dirs: list) -> None:
    """温度別 (layer_top) の SG vs PM 内訳を出力する。"""
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


def _print_per_trial_detail(base: Path) -> None:
    """N6_T0_1 の試行別詳細を出力する。"""
    print("\n" + "=" * 60)
    print("Per-trial detail: N6_T0_1 (layer_top)")
    print("=" * 60)
    cond_dir     = base / "N6_T0_1"
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


def main():
    base    = Path("results/hanoi/full_sweep/deepseek-r1-distill-qwen-7b")
    n6_dirs = sorted([d for d in base.iterdir() if d.name.startswith("N6_")])

    print("=" * 60)
    print("N=6 hidden state cosine similarity: SG vs PM")
    print("=" * 60)
    _print_layer_comparison(base, n6_dirs)
    _print_temp_breakdown(base, n6_dirs)
    _print_per_trial_detail(base)


if __name__ == "__main__":
    main()
