"""Pancake hidden-state sweep for analysis-ready token trajectories."""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis.join_pancake_hidden_events import join_run
from envs.pancake_env import PancakeSortingEnv
from runners.pancake_debug_sweep import (
    SweepRun as DebugSweepRun,
    load_instance_runs,
    temperature_label,
)
from runners.run_local import (
    CaptureTiming,
    EarlyStopConfig,
    calc_think_budget_ratio,
    load_model_and_tokenizer,
    make_capture_layers,
    model_id_to_slug,
    parse_capture_timing,
    parse_initial_state,
    resolve_model_profile,
    run_experiment_hf,
)


@dataclass(frozen=True)
class HiddenSweepRun:
    N: int
    temperature: float
    num_predict: int
    initial_state: tuple[int, ...]
    min_moves: int
    instance_id: str
    instance_seed: int | None = None


def select_initial_state_by_min_moves(
    N: int,
    min_moves: int,
    *,
    instance_index: int = 0,
) -> tuple[int, ...]:
    """Return a deterministic Pancake state at an exact BFS distance."""
    if instance_index < 0:
        raise ValueError("instance_index must be non-negative")
    matches: list[tuple[int, ...]] = []
    for state in itertools.permutations(range(1, N + 1)):
        if state == tuple(range(1, N + 1)):
            continue
        env = PancakeSortingEnv(N=N, initial_state=state)
        if env.min_moves == min_moves:
            matches.append(state)
    if instance_index >= len(matches):
        raise ValueError(
            f"N={N} min_moves={min_moves} has only {len(matches)} matching "
            f"states; cannot select index {instance_index}"
        )
    return matches[instance_index]


def _run_from_debug_instance(run: DebugSweepRun) -> HiddenSweepRun:
    if run.initial_state is None or run.requested_min_moves is None:
        raise ValueError("instances-file runs must resolve initial_state and min_moves")
    instance_id = run.instance_id or f"N{run.N}_seed{run.seed}_mm{run.requested_min_moves}"
    return HiddenSweepRun(
        N=run.N,
        temperature=run.temperature,
        num_predict=run.num_predict,
        initial_state=tuple(run.initial_state),
        min_moves=run.requested_min_moves,
        instance_id=instance_id,
        instance_seed=run.seed,
    )


def build_hidden_runs(args: argparse.Namespace) -> list[HiddenSweepRun]:
    if args.instances_file is not None:
        cli_temperatures = [args.temperature] if args.temperature is not None else None
        debug_runs = load_instance_runs(
            args.instances_file,
            cli_temperatures=cli_temperatures,
            cli_num_predict=args.num_predict,
        )
        return [_run_from_debug_instance(run) for run in debug_runs]

    if args.N is None or args.min_moves is None:
        raise ValueError("--N and --min-moves are required without --instances-file")
    if args.initial_state is None:
        initial_state = select_initial_state_by_min_moves(
            args.N,
            args.min_moves,
            instance_index=args.instance_index,
        )
    else:
        initial_state = args.initial_state

    env = PancakeSortingEnv(N=args.N, initial_state=initial_state)
    if env.min_moves != args.min_moves:
        raise ValueError(
            f"requested min_moves={args.min_moves}, but initial_state "
            f"{list(initial_state)} has min_moves={env.min_moves}"
        )
    instance_id = (
        args.instance_id
        or f"N{args.N}_mm{args.min_moves}_idx{args.instance_index + 1}"
    )
    temperature = 0.6 if args.temperature is None else args.temperature
    num_predict = 8192 if args.num_predict is None else args.num_predict
    return [
        HiddenSweepRun(
            N=args.N,
            temperature=temperature,
            num_predict=num_predict,
            initial_state=tuple(initial_state),
            min_moves=args.min_moves,
            instance_id=instance_id,
            instance_seed=args.seed,
        )
    ]


def output_dir_for_run(output_root: Path, model_slug: str, run: HiddenSweepRun) -> Path:
    t_tag = temperature_label(run.temperature)
    return output_root / model_slug / f"{run.instance_id}_T{t_tag}"


def event_dir_for_run(event_root: Path, model_slug: str, run: HiddenSweepRun) -> Path:
    t_tag = temperature_label(run.temperature)
    return event_root / model_slug / f"{run.instance_id}_T{t_tag}"


def build_early_stop_cfg(args: argparse.Namespace, N: int) -> EarlyStopConfig | None:
    if args.no_early_stop:
        return None
    think_ratio = (
        args.es_think_ratio if args.es_think_ratio is not None else calc_think_budget_ratio(N)
    )
    return EarlyStopConfig(
        think_budget_ratio=think_ratio,
        max_move_multiplier=args.es_move_mult,
        loop_window=args.es_loop_window,
        loop_min_count=args.es_loop_count,
        enable_move_loop=not args.no_loop_detection,
    )


def write_run_meta(path: Path, args: argparse.Namespace, run: HiddenSweepRun) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "environment": "pancake",
        "model": args.model_id,
        "N": run.N,
        "temperature": run.temperature,
        "num_predict": run.num_predict,
        "sweep_type": args.sweep_type,
        "instance_id": run.instance_id,
        "instance_seed": run.instance_seed,
        "sample_seed": args.sample_seed,
        "initial_state": list(run.initial_state),
        "min_moves": run.min_moves,
        "trials": args.trials,
        "capture_timing": str(args.capture_timing),
        "capture_mode": args.capture_mode,
        "hidden_dtype": args.hidden_dtype,
    }
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", default="deepseek-ai/DeepSeek-R1-Distill-Qwen-14B")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--N", type=int)
    parser.add_argument("--min-moves", type=int)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--initial-state", type=parse_initial_state)
    parser.add_argument("--instance-id")
    parser.add_argument("--instance-index", type=int, default=0)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--sample-seed", type=int)
    parser.add_argument("--instances-file", type=Path)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--num_predict", type=int)
    parser.add_argument("--repetition-penalty", type=float, default=1.1)
    parser.add_argument("--n-shot", type=int, default=0)
    parser.add_argument("--capture-timing", type=parse_capture_timing, default=CaptureTiming("token", 8))
    parser.add_argument("--capture-mode", choices=["relative", "all"], default="relative")
    parser.add_argument("--hidden-dtype", choices=["float16", "float32"], default="float16")
    parser.add_argument(
        "--hidden-compression",
        choices=["none", "npz_compressed"],
        default="npz_compressed",
    )
    parser.add_argument("--no-early-stop", action="store_true")
    parser.add_argument("--no-loop-detection", action="store_true")
    parser.add_argument("--es-think-ratio", type=float)
    parser.add_argument("--es-move-mult", type=float, default=1.5)
    parser.add_argument("--es-loop-window", type=int, default=6)
    parser.add_argument("--es-loop-count", type=int, default=2)
    parser.add_argument("--output-root", type=Path, default=Path("results/pancake/hidden_success_probe"))
    parser.add_argument(
        "--event-output-root",
        type=Path,
        default=Path("results/analysis/pancake_hidden_events"),
    )
    parser.add_argument("--no-join-events", action="store_true")
    parser.add_argument("--sweep-type", default="pancake_hidden_sweep")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.trials <= 0:
        parser.error("--trials must be positive")
    if args.instances_file is not None and (
        args.N is not None or args.min_moves is not None or args.initial_state is not None
    ):
        parser.error("--instances-file cannot be combined with --N, --min-moves, or --initial-state")
    return args


def main() -> None:
    args = parse_args()
    runs = build_hidden_runs(args)
    model_slug = model_id_to_slug(args.model_id)

    print("=" * 64)
    print("Pancake hidden sweep")
    print("=" * 64)
    print(f"model={args.model_id}")
    print(f"runs={len(runs)} trials_per_run={args.trials}")
    print(f"capture_timing={args.capture_timing} capture_mode={args.capture_mode}")
    print(f"output_root={args.output_root / model_slug}")
    if not args.no_join_events:
        print(f"event_output_root={args.event_output_root / model_slug}")

    if args.dry_run:
        for run in runs:
            print(
                f"[DRY-RUN] {run.instance_id}: N={run.N} mm={run.min_moves} "
                f"state={list(run.initial_state)} T={run.temperature} "
                f"num_predict={run.num_predict}"
            )
        return

    profile = resolve_model_profile(args.model_id)
    model, tokenizer = load_model_and_tokenizer(args.model_id, args.device)
    capture_layers = make_capture_layers(model.config.num_hidden_layers, args.capture_mode)

    for index, run in enumerate(runs, start=1):
        out_dir = output_dir_for_run(args.output_root, model_slug, run)
        event_dir = event_dir_for_run(args.event_output_root, model_slug, run)
        summary_path = out_dir / "summary.json"
        print("-" * 64)
        print(
            f"[{index}/{len(runs)}] {run.instance_id} "
            f"N={run.N} mm={run.min_moves} T={run.temperature} "
            f"trials={args.trials}"
        )
        write_run_meta(out_dir / "meta.json", args, run)
        env = PancakeSortingEnv(N=run.N, initial_state=run.initial_state)
        results = run_experiment_hf(
            env=env,
            N=run.N,
            trials=args.trials,
            model_id=args.model_id,
            model=model,
            tokenizer=tokenizer,
            num_predict=run.num_predict,
            early_stop_cfg=build_early_stop_cfg(args, run.N),
            output_dir=out_dir,
            temperature=run.temperature,
            repetition_penalty=args.repetition_penalty,
            n_shot=args.n_shot,
            profile=profile,
            capture_layers=capture_layers,
            capture_timing=args.capture_timing,
            capture_mode=args.capture_mode,
            hidden_dtype=args.hidden_dtype,
            hidden_compression=args.hidden_compression,
            seed=run.instance_seed,
            instance_id=run.instance_id,
            instance_seed=run.instance_seed,
            sample_seed=args.sample_seed,
            save_text_artifacts=True,
        )
        summary_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"[SAVE] {summary_path}")
        if not args.no_join_events:
            written = join_run(out_dir, event_dir)
            print(f"[JOIN] wrote {len(written)} event files to {event_dir}")


if __name__ == "__main__":
    main()
