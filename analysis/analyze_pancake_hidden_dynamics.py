"""Analyze Pancake token-hidden dynamics on the token x layer grid."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def pca_scores(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    centered = x - x.mean(axis=0, keepdims=True)
    u, s, _ = np.linalg.svd(centered, full_matrices=False)
    variance = s * s
    explained = variance / variance.sum()
    return u * s, explained


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return float("nan")
    return float(np.dot(a, b) / denom)


def vector_stats(values: np.ndarray) -> dict[str, float]:
    if values.size == 0:
        return {"mean": float("nan"), "median": float("nan"), "p05": float("nan"), "p95": float("nan")}
    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "p05": float(np.percentile(values, 5)),
        "p95": float(np.percentile(values, 95)),
    }


def first_components_for_threshold(explained: np.ndarray, threshold: float) -> int | None:
    hits = np.flatnonzero(np.cumsum(explained) >= threshold)
    if hits.size == 0:
        return None
    return int(hits[0] + 1)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_inputs(hidden_npz: Path, events_json: Path) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    with np.load(hidden_npz, allow_pickle=False) as z:
        data = {key: z[key] for key in z.files}
    events = json.loads(events_json.read_text(encoding="utf-8"))
    return data, events


def analyze(hidden_npz: Path, events_json: Path, output_dir: Path) -> dict[str, Any]:
    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=True)
    data, joined = load_inputs(hidden_npz, events_json)

    hidden = data["hidden"].astype(np.float32)
    token_positions = data["token_positions"].astype(int)
    token_source = data["token_source"].astype(str)
    is_think = data["is_think_token"].astype(bool)
    layer_ids = data["layer_ids"].astype(int)
    capture_meta = json.loads(str(data["capture_meta"].item()))
    token_series = joined["token_series"]

    generated_mask = token_source == "generated"
    gen_rows = np.flatnonzero(generated_mask)
    h_gen_original_order = hidden[generated_mask]
    pos_gen = token_positions[generated_mask]
    think_gen = is_think[generated_mask]

    # Store layers in computational depth order: low -> mid -> top.
    depth_order = np.argsort(layer_ids)
    layer_ids_depth = layer_ids[depth_order]
    h_gen = h_gen_original_order[:, depth_order, :]

    n_tokens, n_layers, hidden_dim = h_gen.shape
    flat = h_gen.reshape(n_tokens * n_layers, hidden_dim)

    # PCA is diagnostic only. For the layer-token grid, z-score per layer first so
    # the top layer's larger norm does not dominate the geometry.
    standardized = np.empty_like(h_gen)
    for li in range(n_layers):
        x = h_gen[:, li, :]
        mu = x.mean(axis=0, keepdims=True)
        sigma = x.std(axis=0, keepdims=True)
        standardized[:, li, :] = (x - mu) / np.maximum(sigma, 1e-6)
    flat_standardized = standardized.reshape(n_tokens * n_layers, hidden_dim)
    flat_scores, flat_explained = pca_scores(flat_standardized)

    token_scores_by_layer: dict[str, np.ndarray] = {}
    token_explained_by_layer: dict[str, np.ndarray] = {}
    for li, layer_id in enumerate(layer_ids_depth):
        scores, explained = pca_scores(h_gen[:, li, :])
        token_scores_by_layer[str(int(layer_id))] = scores
        token_explained_by_layer[str(int(layer_id))] = explained

    rows = []
    for ti, source_row in enumerate(gen_rows):
        for li, layer_id in enumerate(layer_ids_depth):
            x = h_gen[ti, li, :]
            token_drift = None
            token_cos = None
            depth_drift = None
            depth_cos = None
            if ti > 0:
                token_drift = float(np.linalg.norm(h_gen[ti, li, :] - h_gen[ti - 1, li, :]))
                token_cos = cosine(h_gen[ti, li, :], h_gen[ti - 1, li, :])
            if li > 0:
                depth_drift = float(np.linalg.norm(h_gen[ti, li, :] - h_gen[ti, li - 1, :]))
                depth_cos = cosine(h_gen[ti, li, :], h_gen[ti, li - 1, :])
            flat_index = ti * n_layers + li
            rows.append(
                {
                    "generated_index": ti,
                    "t_row": int(source_row),
                    "token_position": int(pos_gen[ti]),
                    "is_think_token": bool(think_gen[ti]),
                    "layer_depth_index": li,
                    "layer_id": int(layer_id),
                    "norm": float(np.linalg.norm(x)),
                    "token_drift_from_prev": token_drift,
                    "token_cos_from_prev": token_cos,
                    "depth_drift_from_prev_layer": depth_drift,
                    "depth_cos_from_prev_layer": depth_cos,
                    "grid_pc1": float(flat_scores[flat_index, 0]),
                    "grid_pc2": float(flat_scores[flat_index, 1]),
                }
            )
    write_csv(output_dir / "token_layer_grid_metrics.csv", rows)

    event_rows = []
    event_row_to_generated = {int(row): i for i, row in enumerate(gen_rows)}
    for ev in joined["events"]:
        t_row = ev.get("t_row")
        generated_index = event_row_to_generated.get(int(t_row)) if t_row is not None else None
        base = {
            "move_index": ev.get("move_index"),
            "move": ev.get("move"),
            "t_row": t_row,
            "generated_index": generated_index,
            "token_position": ev.get("token_position"),
            "state_before": ev.get("state_before"),
            "state_after": ev.get("state_after"),
            "distance_before": ev.get("distance_before"),
            "distance_after": ev.get("distance_after"),
            "delta_distance": ev.get("delta_distance"),
        }
        if generated_index is None:
            event_rows.append({**base, "top_pc1": None, "top_pc2": None})
            continue
        top_layer_id = str(int(layer_ids_depth[-1]))
        top_scores = token_scores_by_layer[top_layer_id]
        event_rows.append(
            {
                **base,
                "top_pc1": float(top_scores[generated_index, 0]),
                "top_pc2": float(top_scores[generated_index, 1]),
            }
        )
    write_csv(output_dir / "move_events_layer_token.csv", event_rows)

    token_drift_summary: dict[str, Any] = {}
    for li, layer_id in enumerate(layer_ids_depth):
        x = h_gen[:, li, :]
        drift = np.linalg.norm(np.diff(x, axis=0), axis=1)
        cosines = np.asarray([cosine(x[i], x[i - 1]) for i in range(1, n_tokens)])
        speed_by_distance: dict[str, Any] = {}
        distance_values = np.asarray(
            [token_series["distance_to_goal"][int(row)] for row in gen_rows],
            dtype=float,
        )
        for distance in sorted(set(distance_values[1:].tolist())):
            mask = distance_values[1:] == distance
            speed_by_distance[str(int(distance))] = vector_stats(drift[mask])
        token_drift_summary[str(int(layer_id))] = {
            "drift": vector_stats(drift),
            "cosine": vector_stats(cosines),
            "speed_by_distance_after": speed_by_distance,
            "pca_explained_first10": [float(x) for x in token_explained_by_layer[str(int(layer_id))][:10]],
            "pca_components_for_80pct": first_components_for_threshold(
                token_explained_by_layer[str(int(layer_id))], 0.80
            ),
            "pca_components_for_90pct": first_components_for_threshold(
                token_explained_by_layer[str(int(layer_id))], 0.90
            ),
            "pca_components_for_95pct": first_components_for_threshold(
                token_explained_by_layer[str(int(layer_id))], 0.95
            ),
            "pca_variance_first40": float(np.sum(token_explained_by_layer[str(int(layer_id))][:40])),
        }

    depth_segments = []
    for li in range(1, n_layers):
        delta = h_gen[:, li, :] - h_gen[:, li - 1, :]
        depth_segments.append(
            {
                "from_layer": int(layer_ids_depth[li - 1]),
                "to_layer": int(layer_ids_depth[li]),
                "drift": vector_stats(np.linalg.norm(delta, axis=1)),
                "cosine": vector_stats(
                    np.asarray([cosine(h_gen[i, li, :], h_gen[i, li - 1, :]) for i in range(n_tokens)])
                ),
            }
        )

    # Alignment between same-layer token velocity and the next within-token depth update.
    alignments = []
    for li in range(n_layers - 1):
        vals = []
        for ti in range(1, n_tokens):
            token_velocity = h_gen[ti, li, :] - h_gen[ti - 1, li, :]
            depth_update = h_gen[ti, li + 1, :] - h_gen[ti, li, :]
            vals.append(cosine(token_velocity, depth_update))
        alignments.append(
            {
                "layer_id": int(layer_ids_depth[li]),
                "next_layer_id": int(layer_ids_depth[li + 1]),
                "cos_token_velocity_with_depth_update": vector_stats(np.asarray(vals)),
            }
        )

    grid_summary = {
        "hidden_npz": str(hidden_npz),
        "events_json": str(events_json),
        "generated_only": True,
        "token_layer_order": "for each generated token, layers are ordered low -> mid -> top",
        "generated_rows": int(n_tokens),
        "layer_ids_original_file_order": [int(x) for x in layer_ids.tolist()],
        "layer_ids_depth_order": [int(x) for x in layer_ids_depth.tolist()],
        "hidden_dim": int(hidden_dim),
        "capture_meta": capture_meta,
        "join_ok": joined.get("join_ok"),
        "boundary_ok": joined.get("boundary_ok"),
        "outcome_label": joined.get("outcome_label"),
        "events_total": len(joined["events"]),
        "events_mapped": sum(1 for ev in joined["events"] if ev.get("t_row") is not None),
        "grid_pca_explained_first10": [float(x) for x in flat_explained[:10]],
        "grid_pca_components_for_80pct": first_components_for_threshold(flat_explained, 0.80),
        "grid_pca_components_for_90pct": first_components_for_threshold(flat_explained, 0.90),
        "grid_pca_components_for_95pct": first_components_for_threshold(flat_explained, 0.95),
        "grid_pca_variance_first40": float(np.sum(flat_explained[:40])),
        "token_drift_by_layer": token_drift_summary,
        "depth_drift_between_layers": depth_segments,
        "token_depth_alignment": alignments,
    }
    (output_dir / "layer_token_dynamics_summary.json").write_text(
        json.dumps(grid_summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # Diagnostic plot: layer-token grid PCA, with within-token depth segments.
    fig, ax = plt.subplots(figsize=(7.5, 5.5), dpi=160)
    colors = {0: "tab:blue", 1: "tab:orange", 2: "tab:green"}
    for li, layer_id in enumerate(layer_ids_depth):
        idx = np.arange(li, n_tokens * n_layers, n_layers)
        ax.scatter(
            flat_scores[idx, 0],
            flat_scores[idx, 1],
            s=10,
            alpha=0.65,
            label=f"layer {int(layer_id)}",
            color=colors.get(li),
        )
    for ti in range(n_tokens):
        idx = slice(ti * n_layers, ti * n_layers + n_layers)
        ax.plot(flat_scores[idx, 0], flat_scores[idx, 1], color="0.75", linewidth=0.5, alpha=0.5)
    for ev in joined["events"]:
        r = ev.get("t_row")
        if r is None or int(r) not in event_row_to_generated:
            continue
        ti = event_row_to_generated[int(r)]
        flat_index = ti * n_layers + (n_layers - 1)
        marker = "o" if ev.get("delta_distance", 0) < 0 else "x"
        color = "tab:green" if ev.get("delta_distance", 0) < 0 else "tab:red"
        ax.scatter([flat_scores[flat_index, 0]], [flat_scores[flat_index, 1]], marker=marker, s=55, c=color)
        ax.text(flat_scores[flat_index, 0], flat_scores[flat_index, 1], str(ev.get("move_index")), fontsize=7)
    ax.set_title("Generated token x layer grid PCA (z-scored per layer)")
    ax.set_xlabel(f"PC1 ({flat_explained[0] * 100:.1f}%)")
    ax.set_ylabel(f"PC2 ({flat_explained[1] * 100:.1f}%)")
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_dir / "layer_token_grid_pca.png")

    fig, ax = plt.subplots(figsize=(7.5, 4.0), dpi=160)
    for li, layer_id in enumerate(layer_ids_depth):
        drift = np.linalg.norm(np.diff(h_gen[:, li, :], axis=0), axis=1)
        ax.plot(pos_gen[1:], drift, label=f"layer {int(layer_id)}", linewidth=1.1)
    for ev in joined["events"]:
        if ev.get("token_position") is None:
            continue
        ax.axvline(ev["token_position"], color="tab:green" if ev["delta_distance"] < 0 else "tab:red", alpha=0.18)
    ax.set_title("Same-layer token drift, generated token:8")
    ax.set_xlabel("prompt+generated token position")
    ax.set_ylabel("||h[t,l]-h[t-1,l]||")
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_dir / "token_drift_by_layer.png")

    return grid_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hidden-npz", type=Path, required=True)
    parser.add_argument("--events-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = analyze(args.hidden_npz, args.events_json, args.output_dir)
    print(json.dumps({
        "output_dir": str(args.output_dir),
        "generated_rows": summary["generated_rows"],
        "layer_ids_depth_order": summary["layer_ids_depth_order"],
        "events_mapped": summary["events_mapped"],
        "events_total": summary["events_total"],
        "grid_pca_variance_first40": summary["grid_pca_variance_first40"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
