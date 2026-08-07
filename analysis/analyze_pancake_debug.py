"""Analyze Pancake Sorting debug_prompt outputs.

The main mode summarizes a directory of debug.json files by N/temperature.
Passing one debug.json still prints a detailed per-mention trajectory report.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from envs.pancake_env import PancakeSortingEnv


LOOP_TRAP_THRESHOLD = 0.3


def parse_state(value: str) -> tuple[int, ...]:
    """Parse the tuple-like state strings written by runners/debug_prompt.py."""
    parsed = json.loads(value.replace("(", "[").replace(")", "]"))
    return tuple(int(item) for item in parsed)


def snippet(text: str, pos: int, window: int) -> str:
    start = max(0, pos - window)
    end = min(len(text), pos + window)
    return " ".join(text[start:end].split())


def analyze_single_debug_json(debug_json: Path, context_chars: int) -> dict:
    data = json.loads(debug_json.read_text(encoding="utf-8"))
    initial = parse_state(data["initial_state"])
    env = PancakeSortingEnv(N=int(data["N"]), initial_state=initial)
    text = data["generated_text"]
    moves_with_pos = env.extract_moves_with_position(text)

    rows = []
    state = env.initial_state
    previous_distance = env._distance[state]
    reached_at = None

    for idx, (move, pos) in enumerate(moves_with_pos, start=1):
        before = state
        state = env._apply_move_if_legal(state, move)
        distance = env._distance[state]
        delta = distance - previous_distance
        if state == env.goal_state and reached_at is None:
            reached_at = idx
        rows.append(
            {
                "i": idx,
                "move": move,
                "char_pos": pos,
                "before": list(before),
                "after": list(state),
                "distance_to_goal": distance,
                "delta_distance": delta,
                "on_shortest_descent": delta == -1,
                "context": snippet(text, pos, context_chars),
            }
        )
        previous_distance = distance

    return {
        "source": str(debug_json),
        "N": env.N,
        "initial_state": list(env.initial_state),
        "goal_state": list(env.goal_state),
        "min_moves": env.min_moves,
        "optimal_moves": env.solve(),
        "generated_token_count": data.get("generated_token_count"),
        "done_reason": data.get("done_reason"),
        "reported_moves": data.get("moves"),
        "reported_accuracy": data.get("accuracy"),
        "reported_v_score": data.get("v_score"),
        "goal_reached_at_mention": reached_at,
        "final_state_after_mentions": list(state),
        "final_distance_to_goal": env._distance[state],
        "rows": rows,
    }


def print_report(result: dict) -> None:
    print(f"source: {result['source']}")
    print(
        "problem: "
        f"N={result['N']} initial={result['initial_state']} "
        f"goal={result['goal_state']} min_moves={result['min_moves']}"
    )
    print(f"optimal: {result['optimal_moves']}")
    print(
        "generation: "
        f"tokens={result['generated_token_count']} done={result['done_reason']} "
        f"reported_accuracy={result['reported_accuracy']} "
        f"v={result['reported_v_score']}"
    )
    print(
        "mentions: "
        f"goal_reached_at={result['goal_reached_at_mention']} "
        f"final_state={result['final_state_after_mentions']} "
        f"final_distance={result['final_distance_to_goal']}"
    )
    print()
    print("i  move    before        after         d  dd  shortest  context")
    print("-- ------- ------------- ------------- -- --- --------- -------")
    for row in result["rows"]:
        shortest = "yes" if row["on_shortest_descent"] else "no"
        print(
            f"{row['i']:>2} {row['move']:<7} "
            f"{str(row['before']):<13} {str(row['after']):<13} "
            f"{row['distance_to_goal']:>2} {row['delta_distance']:>3} "
            f"{shortest:<9} {row['context']}"
        )


def repeated_state_ratio(data: dict) -> float:
    moves = data.get("moves_all_mentions") or []
    return float(data.get("repeated_state_count") or 0) / max(1, len(moves))


def has_final_answer(data: dict) -> bool:
    return bool(data.get("moves_final") or data.get("moves"))


def outcome_label(data: dict, loop_threshold: float) -> str:
    is_no_final = not has_final_answer(data)
    is_length_stop = data.get("done_reason") == "length"
    is_loop_trap = repeated_state_ratio(data) >= loop_threshold
    success_final = int(data.get("final_accuracy") or data.get("accuracy") or 0) == 1
    search_goal = bool(data.get("goal_reached_all_mentions"))

    if success_final:
        return "success_final"
    if is_no_final:
        return "no_final"
    if is_length_stop:
        return "length_stop"
    if is_loop_trap:
        return "loop_trap"
    if search_goal:
        return "search_success_final_fail"
    return "search_fail"


def load_run(debug_json: Path, loop_threshold: float) -> dict:
    data = json.loads(debug_json.read_text(encoding="utf-8"))
    ratio = repeated_state_ratio(data)
    row = {
        "source": str(debug_json),
        "N": int(data["N"]),
        "seed": data.get("seed"),
        "temperature": float(data["temperature"]),
        "num_predict": int(data.get("num_predict") or 0),
        "model_id": data.get("model_id"),
        "initial_state": data.get("initial_state"),
        "min_moves": data.get("min_moves"),
        "generated_token_count": data.get("generated_token_count"),
        "done_reason": data.get("done_reason"),
        "final_accuracy": int(data.get("final_accuracy") or data.get("accuracy") or 0),
        "goal_reached_all_mentions": bool(data.get("goal_reached_all_mentions")),
        "no_final": not has_final_answer(data),
        "length_stop": data.get("done_reason") == "length",
        "repeated_state_count": int(data.get("repeated_state_count") or 0),
        "num_moves_all_mentions": len(data.get("moves_all_mentions") or []),
        "repeated_state_ratio": ratio,
        "loop_trap": ratio >= loop_threshold,
        "first_goal_index": data.get("first_goal_index"),
        "excess_after_goal": int(data.get("excess_after_goal") or 0),
    }
    row["outcome_label"] = outcome_label(data, loop_threshold)
    return row


def find_debug_jsons(path: Path, run_dir_glob: str | None = None) -> list[Path]:
    if path.is_file():
        return [path]
    if run_dir_glob:
        return sorted(candidate / "debug.json" for candidate in path.glob(run_dir_glob) if (candidate / "debug.json").is_file())
    return sorted(path.rglob("debug.json"))


def aggregate_runs(rows: list[dict], group_by_min_moves: bool = False) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        key = (row["N"], row["min_moves"], row["temperature"]) if group_by_min_moves else (
            row["N"],
            row["temperature"],
        )
        groups[key].append(row)

    summary = []
    for key, items in sorted(groups.items()):
        if group_by_min_moves:
            N, min_moves, temperature = key
        else:
            N, temperature = key
            min_moves = None
        count = len(items)
        labels = defaultdict(int)
        for item in items:
            labels[item["outcome_label"]] += 1

        row = {
            "N": N,
            "temperature": temperature,
            "runs": count,
            "final_accuracy": mean(item["final_accuracy"] for item in items),
            "goal_reached_all_mentions": mean(
                1.0 if item["goal_reached_all_mentions"] else 0.0 for item in items
            ),
            "no_final": mean(1.0 if item["no_final"] else 0.0 for item in items),
            "length_stop": mean(1.0 if item["length_stop"] else 0.0 for item in items),
            "loop_trap": mean(1.0 if item["loop_trap"] else 0.0 for item in items),
            "repeated_state_ratio": mean(item["repeated_state_ratio"] for item in items),
            "success_final_count": labels["success_final"],
            "search_success_final_fail_count": labels["search_success_final_fail"],
            "search_fail_count": labels["search_fail"],
            "no_final_count": labels["no_final"],
            "length_stop_count": labels["length_stop"],
            "loop_trap_count": labels["loop_trap"],
        }
        if group_by_min_moves:
            row = {"N": N, "min_moves": min_moves, **{k: v for k, v in row.items() if k != "N"}}
        summary.append(row)
    return summary


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def print_summary(summary: list[dict]) -> None:
    if not summary:
        print("No debug.json files found.")
        return

    has_min_moves = "min_moves" in summary[0]
    if has_min_moves:
        print("N  mm  T     runs  final_acc  search_goal  no_final  length  loop  rep_ratio")
        print("-- --- ----- ----- ---------- ------------ -------- ------- ----- ---------")
    else:
        print("N  T     runs  final_acc  search_goal  no_final  length  loop  rep_ratio")
        print("-- ----- ----- ---------- ------------ -------- ------- ----- ---------")
    for row in summary:
        prefix = (
            f"{row['N']:>2} {row['min_moves']:>3} {row['temperature']:<5g}"
            if has_min_moves
            else f"{row['N']:>2} {row['temperature']:<5g}"
        )
        print(
            f"{prefix} {row['runs']:>5} "
            f"{row['final_accuracy']:>10.3f} "
            f"{row['goal_reached_all_mentions']:>12.3f} "
            f"{row['no_final']:>8.3f} "
            f"{row['length_stop']:>7.3f} "
            f"{row['loop_trap']:>5.3f} "
            f"{row['repeated_state_ratio']:>9.3f}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="A debug.json file or directory containing debug.json files.")
    parser.add_argument("--context-chars", type=int, default=80)
    parser.add_argument("--loop-threshold", type=float, default=LOOP_TRAP_THRESHOLD)
    parser.add_argument(
        "--run-dir-glob",
        default=None,
        help='Limit directory input to matching immediate run dirs, e.g. "N*_seed*_np4096_T*".',
    )
    parser.add_argument("--csv-out", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument(
        "--group-by",
        choices=("N", "min_moves"),
        default="N",
        help="Summarize by N only, or by N and min_moves.",
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Force detailed single-run trajectory report for a debug.json file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.path.is_file() and (args.detailed or args.path.name == "debug.json"):
        result = analyze_single_debug_json(args.path, args.context_chars)
        if args.json_out:
            args.json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print_report(result)
        return

    rows = [
        load_run(path, args.loop_threshold)
        for path in find_debug_jsons(args.path, args.run_dir_glob)
    ]
    summary = aggregate_runs(rows, group_by_min_moves=args.group_by == "min_moves")
    if args.csv_out:
        write_csv(args.csv_out, summary)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps({"runs": rows, "summary": summary}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print_summary(summary)


if __name__ == "__main__":
    main()
