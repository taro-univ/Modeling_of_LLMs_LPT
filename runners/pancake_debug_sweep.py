"""Batch Pancake debug sweep that loads the model once."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from envs.pancake_env import PancakeSortingEnv
from runners.debug_prompt import (
    analyze_pancake_trajectory,
    build_formatted_prompt,
    generate_text,
)
from runners.run_local import (
    load_model_and_tokenizer,
    model_id_to_slug,
    resolve_model_profile,
)

DEFAULT_TEMPERATURES = "0.0 0.3 0.6 0.9 1.0"
DEFAULT_NUM_PREDICT = 4096
INSTANCE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class SweepRun:
    N: int
    temperature: float
    num_predict: int
    seed: int | None
    initial_state: tuple[int, ...] | None = None
    instance_id: str | None = None
    requested_min_moves: int | None = None


def parse_list(value: str, cast):
    return [cast(item) for item in value.split()]


def temperature_label(value: float) -> str:
    return str(value).replace(".", "_")


def _require_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    return value


def _require_positive_int(value: Any, field: str) -> int:
    parsed = _require_int(value, field)
    if parsed <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return parsed


def _require_temperature(value: Any, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field} must be a number")
    parsed = float(value)
    if parsed < 0:
        raise ValueError(f"{field} must be non-negative")
    return parsed


def load_instance_runs(
    path: Path,
    cli_temperatures: list[float] | None,
    cli_num_predict: int | None,
) -> list[SweepRun]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("instances file root must be a JSON object")
    if data.get("schema_version") != 1:
        raise ValueError("instances file schema_version must be 1")

    raw_instances = data.get("instances")
    if not isinstance(raw_instances, list) or not raw_instances:
        raise ValueError("instances file must contain a non-empty instances list")

    root_temperature = data.get("temperature")
    root_num_predict = data.get("num_predict")
    if cli_num_predict is not None:
        _require_positive_int(cli_num_predict, "--num_predict")

    runs: list[SweepRun] = []
    seen_ids: set[str] = set()
    for index, instance in enumerate(raw_instances):
        prefix = f"instances[{index}]"
        if not isinstance(instance, dict):
            raise ValueError(f"{prefix} must be a JSON object")

        missing = [
            field
            for field in ("instance_id", "N", "initial_state", "min_moves")
            if field not in instance
        ]
        if missing:
            raise ValueError(f"{prefix} missing required fields: {', '.join(missing)}")

        instance_id = instance["instance_id"]
        if not isinstance(instance_id, str) or not INSTANCE_ID_RE.fullmatch(instance_id):
            raise ValueError(
                f"{prefix}.instance_id must contain only letters, digits, '_' and '-'"
            )
        if instance_id in seen_ids:
            raise ValueError(f"duplicate instance_id: {instance_id}")
        seen_ids.add(instance_id)

        N = _require_int(instance["N"], f"{prefix}.N")
        requested_min_moves = _require_positive_int(
            instance["min_moves"], f"{prefix}.min_moves"
        )
        raw_state = instance["initial_state"]
        if not isinstance(raw_state, list):
            raise ValueError(f"{prefix}.initial_state must be a JSON array")
        initial_state = tuple(raw_state)

        seed = instance.get("seed")
        if seed is not None:
            seed = _require_int(seed, f"{prefix}.seed")

        env = PancakeSortingEnv(N=N, initial_state=initial_state)
        if env.min_moves != requested_min_moves:
            raise ValueError(
                f"{instance_id}: requested min_moves={requested_min_moves}, "
                f"but fixed initial_state has min_moves={env.min_moves}"
            )

        if "temperature" in instance:
            temperatures = [
                _require_temperature(
                    instance["temperature"], f"{prefix}.temperature"
                )
            ]
        elif cli_temperatures is not None:
            temperatures = [
                _require_temperature(value, "--temperatures")
                for value in cli_temperatures
            ]
        elif root_temperature is not None:
            temperatures = [
                _require_temperature(root_temperature, "root temperature")
            ]
        else:
            raise ValueError(
                f"{instance_id}: temperature is not set in the instance, CLI, or file root"
            )
        if not temperatures:
            raise ValueError("--temperatures must contain at least one value")

        if "num_predict" in instance:
            num_predict = _require_positive_int(
                instance["num_predict"], f"{prefix}.num_predict"
            )
        elif cli_num_predict is not None:
            num_predict = cli_num_predict
        elif root_num_predict is not None:
            num_predict = _require_positive_int(root_num_predict, "root num_predict")
        else:
            raise ValueError(
                f"{instance_id}: num_predict is not set in the instance, CLI, or file root"
            )

        for temperature in temperatures:
            runs.append(
                SweepRun(
                    N=N,
                    temperature=temperature,
                    num_predict=num_predict,
                    seed=seed,
                    initial_state=env.initial_state,
                    instance_id=instance_id,
                    requested_min_moves=requested_min_moves,
                )
            )
    return runs


def build_seed_runs(args: argparse.Namespace) -> list[SweepRun]:
    Ns = parse_list(args.ns, int)
    temperatures = parse_list(
        args.temperatures if args.temperatures is not None else DEFAULT_TEMPERATURES,
        float,
    )
    num_predict = (
        args.num_predict if args.num_predict is not None else DEFAULT_NUM_PREDICT
    )
    return [
        SweepRun(
            N=N,
            temperature=temperature,
            num_predict=num_predict,
            seed=args.seed_base + trial,
        )
        for N in Ns
        for temperature in temperatures
        for trial in range(args.trials)
    ]


def output_dir_for_run(base_dir: Path, run: SweepRun) -> Path:
    t_tag = temperature_label(run.temperature)
    if run.instance_id is not None:
        name = f"{run.instance_id}_np{run.num_predict}_T{t_tag}"
    else:
        name = f"N{run.N}_seed{run.seed}_np{run.num_predict}_T{t_tag}"
    return base_dir / name


def run_one(
    model,
    tokenizer,
    profile,
    args: argparse.Namespace,
    N: int,
    temperature: float,
    seed: int | None,
    output_dir: Path,
    *,
    initial_state: tuple[int, ...] | None = None,
    instance_id: str | None = None,
    requested_min_moves: int | None = None,
    num_predict: int | None = None,
) -> dict:
    if initial_state is None:
        env = PancakeSortingEnv(N=N, seed=seed)
    else:
        env = PancakeSortingEnv(N=N, initial_state=tuple(initial_state))
    if requested_min_moves is not None and env.min_moves != requested_min_moves:
        raise ValueError(
            f"{instance_id}: requested min_moves={requested_min_moves}, "
            f"but fixed initial_state has min_moves={env.min_moves}"
        )
    effective_num_predict = (
        num_predict
        if num_predict is not None
        else (
            args.num_predict
            if args.num_predict is not None
            else DEFAULT_NUM_PREDICT
        )
    )
    prompt = env.get_prompt()
    formatted_prompt = build_formatted_prompt(tokenizer, prompt, env, args.n_shot, profile)
    input_ids = tokenizer(formatted_prompt, return_tensors="pt").input_ids

    started = time.time()
    generated_text, generated_ids, done_reason = generate_text(
        model=model,
        tokenizer=tokenizer,
        input_ids=input_ids,
        num_predict=effective_num_predict,
        temperature=temperature,
        repetition_penalty=args.repetition_penalty,
    )
    elapsed = time.time() - started

    moves_all_mentions = env.extract_moves_from_text(generated_text)
    moves_final = env.extract_scored_moves_from_text(generated_text)
    final_accuracy = 1 if env.goal_reached(moves_final) else 0
    v_score = env.evaluate_state(moves_final)
    trajectory_debug = analyze_pancake_trajectory(env, moves_all_mentions)

    result = {
        "puzzle": "pancake",
        "N": N,
        "seed": seed,
        "instance_id": instance_id,
        "instance_seed": seed,
        "requested_min_moves": requested_min_moves,
        "model_id": args.model_id,
        "think_mode": profile.think_mode,
        "n_shot": args.n_shot,
        "num_predict": effective_num_predict,
        "temperature": temperature,
        "repetition_penalty": args.repetition_penalty,
        "initial_state": str(env.initial_state),
        "goal_state": str(env.goal_state),
        "min_moves": env.min_moves,
        "optimal_moves": env.solve(),
        "generated_token_count": len(generated_ids),
        "done_reason": done_reason,
        "generated_text": generated_text,
        "moves": moves_final,
        "moves_final": moves_final,
        "moves_all_mentions": moves_all_mentions,
        "goal_reached_all_mentions": trajectory_debug["goal_reached_all_mentions"],
        "accuracy": final_accuracy,
        "final_accuracy": final_accuracy,
        "v_score": v_score,
        "elapsed_sec": round(elapsed, 3),
        "output_dir": str(output_dir),
    }
    result.update(trajectory_debug)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    (output_dir / "formatted_prompt.txt").write_text(formatted_prompt, encoding="utf-8")
    (output_dir / "generated.txt").write_text(generated_text, encoding="utf-8")
    (output_dir / "debug.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", default="deepseek-ai/DeepSeek-R1-Distill-Qwen-14B")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--ns", default="3 4")
    parser.add_argument("--temperatures")
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--seed-base", type=int, default=1)
    parser.add_argument("--num_predict", type=int)
    parser.add_argument("--instances-file", type=Path)
    parser.add_argument("--repetition-penalty", type=float, default=1.1)
    parser.add_argument("--n-shot", type=int, default=0)
    parser.add_argument("--output-root", type=Path, default=Path("results/debug_prompt/pancake"))
    parser.add_argument("--no-analyze", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.instances_file is not None:
        cli_temperatures = (
            parse_list(args.temperatures, float)
            if args.temperatures is not None
            else None
        )
        runs = load_instance_runs(
            args.instances_file,
            cli_temperatures=cli_temperatures,
            cli_num_predict=args.num_predict,
        )
    else:
        runs = build_seed_runs(args)

    slug = model_id_to_slug(args.model_id)
    base_dir = args.output_root / slug
    total = len(runs)

    print("=" * 56)
    print("Pancake debug sweep")
    print("=" * 56)
    print(f"model={args.model_id}")
    print(f"output={base_dir}")
    if args.instances_file is not None:
        print(f"instances_file={args.instances_file} total={total}")
    else:
        print(f"N={parse_list(args.ns, int)} trials={args.trials} total={total}")
    print(f"device={args.device}")

    profile = resolve_model_profile(args.model_id)
    model, tokenizer = load_model_and_tokenizer(args.model_id, args.device)

    for count, run in enumerate(runs, start=1):
        output_dir = output_dir_for_run(base_dir, run)
        debug_json = output_dir / "debug.json"

        print("-" * 56)
        label = f"instance={run.instance_id}" if run.instance_id else f"seed={run.seed}"
        print(
            f"[{count}/{total}] N={run.N} T={run.temperature} "
            f"{label} num_predict={run.num_predict}"
        )
        if debug_json.exists():
            print(f"[SKIP] {debug_json}")
            continue

        result = run_one(
            model=model,
            tokenizer=tokenizer,
            profile=profile,
            args=args,
            N=run.N,
            temperature=run.temperature,
            seed=run.seed,
            output_dir=output_dir,
            initial_state=run.initial_state,
            instance_id=run.instance_id,
            requested_min_moves=run.requested_min_moves,
            num_predict=run.num_predict,
        )
        print(
            "done="
            f"{result['done_reason']} tokens={result['generated_token_count']} "
            f"elapsed={result['elapsed_sec']}s "
            f"final_acc={result['final_accuracy']} "
            f"search_goal={result['goal_reached_all_mentions']} "
            f"moves_final={result['moves_final']}"
        )

    if not args.no_analyze:
        from analysis.analyze_pancake_debug import (
            aggregate_runs,
            find_debug_jsons,
            load_run,
            print_summary,
            write_csv,
        )

        rows = [load_run(path, 0.3) for path in find_debug_jsons(base_dir)]
        summary = aggregate_runs(rows)
        write_csv(base_dir / "pancake_debug_summary.csv", summary)
        (base_dir / "pancake_debug_summary.json").write_text(
            json.dumps({"runs": rows, "summary": summary}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print_summary(summary)


if __name__ == "__main__":
    main()
