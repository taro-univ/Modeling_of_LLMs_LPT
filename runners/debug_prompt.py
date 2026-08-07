"""
debug_prompt.py - Prompt/debug runner for puzzle LLM outputs.

Hidden state capture is intentionally out of scope here.  This script is for
inspecting the exact prompt, chat-template formatted input, raw generated text,
extracted moves, and puzzle evaluation for one lightweight smoke test.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import ast
from datetime import datetime
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import torch
except ImportError:
    torch = None  # type: ignore[assignment]

from envs.base_env import BaseEnv
from envs.hanoi_env import TowerOfHanoiEnv
from envs.lights_out_env import LightsOutEnv
from envs.pancake_env import PancakeSortingEnv
from runners.run_local import (
    ModelProfile,
    build_few_shot_messages,
    load_model_and_tokenizer,
    model_id_to_slug,
    resolve_model_profile,
)


def analyze_pancake_trajectory(
    env: PancakeSortingEnv,
    moves: list[str],
) -> dict:
    """Analyze all Flip mentions as a search trajectory."""
    state = env.initial_state
    state_trace = [list(state)]
    v_trace = [round(env.distance_to_goal(state) / env.min_moves, 6)]
    seen = {state}
    illegal_move_count = 0
    repeated_state_count = 0
    first_goal_index: Optional[int] = None

    for idx, move in enumerate(moves):
        before = state
        state = env.apply_move(state, move)
        if state == before and before != env.goal_state:
            illegal_move_count += 1
        if state in seen:
            repeated_state_count += 1
        seen.add(state)
        state_trace.append(list(state))
        v_trace.append(round(env.distance_to_goal(state) / env.min_moves, 6))
        if state == env.goal_state and first_goal_index is None:
            first_goal_index = idx

    return {
        "state_trace": state_trace,
        "v_trace": v_trace,
        "first_goal_index": first_goal_index,
        "illegal_move_count": illegal_move_count,
        "repeated_state_count": repeated_state_count,
        "excess_after_goal": (
            0 if first_goal_index is None else len(moves) - first_goal_index - 1
        ),
        "moves_all_mentions": moves,
        "goal_reached_all_mentions": env.goal_reached(moves),
    }


def build_formatted_prompt(tokenizer, prompt: str, env: BaseEnv, n_shot: int, profile: ModelProfile) -> str:
    """Return the exact chat-template text sent to the tokenizer."""
    if n_shot > 0:
        messages = build_few_shot_messages(env, n_shot)
    else:
        messages = [
            {"role": "system", "content": env.get_system_hint()},
            {"role": "user", "content": prompt},
        ]

    if profile.think_mode == "chat_template":
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=True,
        )

    formatted = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    if profile.think_mode == "prefill":
        formatted += profile.think_open_tag + "\n"
    return formatted


def apply_repetition_penalty(logits: torch.Tensor, generated_ids: list[int], penalty: float) -> None:
    """Apply a simple repetition penalty in-place."""
    if penalty == 1.0 or not generated_ids:
        return
    for token_id in set(generated_ids):
        if logits[token_id] > 0:
            logits[token_id] /= penalty
        else:
            logits[token_id] *= penalty


def choose_next_token(logits: torch.Tensor, temperature: float) -> int:
    """Greedy decode for temperature<=0; otherwise sample."""
    if temperature <= 0:
        return int(torch.argmax(logits).item())
    probs = torch.softmax(logits / temperature, dim=-1)
    return int(torch.multinomial(probs, num_samples=1).item())


def generate_text(
    model,
    tokenizer,
    input_ids: torch.Tensor,
    num_predict: int,
    temperature: float,
    repetition_penalty: float,
) -> tuple[str, list[int], Optional[str]]:
    """Generate text without hidden-state capture."""
    if torch is None:
        raise RuntimeError("debug generation requires torch to be installed")
    device = next(model.parameters()).device
    current_input_ids = input_ids.to(device)
    past_key_values = None
    generated_ids: list[int] = []
    done_reason: Optional[str] = None

    for _ in range(num_predict):
        with torch.no_grad():
            outputs = model(
                input_ids=current_input_ids,
                past_key_values=past_key_values,
                use_cache=True,
            )

        logits = outputs.logits[0, -1, :].float()
        apply_repetition_penalty(logits, generated_ids, repetition_penalty)
        next_token_id = choose_next_token(logits, temperature)

        if next_token_id == tokenizer.eos_token_id:
            done_reason = "eos"
            break

        generated_ids.append(next_token_id)
        past_key_values = outputs.past_key_values
        current_input_ids = torch.tensor([[next_token_id]], device=device)
    else:
        done_reason = "length"

    text = tokenizer.decode(generated_ids, skip_special_tokens=True)
    return text, generated_ids, done_reason


def parse_initial_state(value: str) -> tuple[int, ...]:
    """Parse a CLI permutation like '[3,4,1,2]' or '3,4,1,2'."""
    text = value.strip()
    if not text.startswith(("[", "(")):
        text = f"[{text}]"
    parsed = ast.literal_eval(text)
    if not isinstance(parsed, (list, tuple)):
        raise ValueError("--initial-state must be a list/tuple of integers")
    return tuple(int(item) for item in parsed)


def make_env(
    puzzle: str,
    N: int,
    seed: Optional[int],
    initial_state: Optional[tuple[int, ...]],
) -> BaseEnv:
    """Instantiate the selected puzzle environment."""
    if initial_state is not None and puzzle != "pancake":
        raise ValueError("--initial-state is currently supported only with pancake")
    if puzzle == "hanoi":
        if seed is not None:
            raise ValueError("--seed is only supported with lights_out or pancake")
        return TowerOfHanoiEnv(N)
    if puzzle == "lights_out":
        return LightsOutEnv(N, seed=seed)
    if puzzle == "pancake":
        return PancakeSortingEnv(N, seed=seed, initial_state=initial_state)
    raise ValueError(f"unsupported puzzle: {puzzle}")


def resolve_output_dir(args: argparse.Namespace) -> Path:
    """Return a clean per-run debug output directory."""
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = (
            Path("results")
            / "debug_prompt"
            / args.puzzle
            / model_id_to_slug(args.model_id)
            / f"N{args.N}_{stamp}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Debug exact prompt, generated text, and puzzle evaluation without hidden capture."
    )
    parser.add_argument("--puzzle", choices=["hanoi", "lights_out", "pancake"], default="pancake")
    parser.add_argument("--N", type=int, required=True)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--initial-state",
        type=parse_initial_state,
        default=None,
        help='Fixed pancake state, for example "[3,4,1,2]" or "3,4,1,2".',
    )
    parser.add_argument(
        "--model-id",
        type=str,
        default="deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
    )
    parser.add_argument("--device", type=str, default="cuda:0")
    parser.add_argument("--num_predict", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--repetition-penalty", type=float, default=1.1)
    parser.add_argument("--n-shot", type=int, default=0)
    parser.add_argument("--output-dir", type=str, default=None)
    parser.add_argument(
        "--print-formatted-prompt",
        action="store_true",
        help="Also print the full chat-template formatted prompt to stdout.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if torch is None:
        raise RuntimeError("debug_prompt.py requires torch to run model generation")
    env = make_env(args.puzzle, args.N, args.seed, args.initial_state)
    profile = resolve_model_profile(args.model_id)
    output_dir = resolve_output_dir(args)

    prompt = env.get_prompt()
    model, tokenizer = load_model_and_tokenizer(args.model_id, args.device)
    formatted_prompt = build_formatted_prompt(tokenizer, prompt, env, args.n_shot, profile)
    input_ids = tokenizer(formatted_prompt, return_tensors="pt").input_ids

    started = time.time()
    generated_text, generated_ids, done_reason = generate_text(
        model=model,
        tokenizer=tokenizer,
        input_ids=input_ids,
        num_predict=args.num_predict,
        temperature=args.temperature,
        repetition_penalty=args.repetition_penalty,
    )
    elapsed = time.time() - started

    moves_all_mentions = env.extract_moves_from_text(generated_text)
    moves = env.extract_scored_moves_from_text(generated_text)
    accuracy = 1 if env.goal_reached(moves) else 0
    v_score = env.evaluate_state(moves)
    trajectory_debug = (
        analyze_pancake_trajectory(env, moves_all_mentions)
        if isinstance(env, PancakeSortingEnv)
        else {
            "moves_all_mentions": moves_all_mentions,
            "goal_reached_all_mentions": env.goal_reached(moves_all_mentions),
        }
    )
    result = {
        "puzzle": args.puzzle,
        "N": args.N,
        "seed": args.seed,
        "model_id": args.model_id,
        "think_mode": profile.think_mode,
        "n_shot": args.n_shot,
        "num_predict": args.num_predict,
        "temperature": args.temperature,
        "repetition_penalty": args.repetition_penalty,
        "initial_state": str(env.initial_state),
        "goal_state": str(env.goal_state),
        "min_moves": env.min_moves,
        "optimal_moves": env.solve(),
        "generated_token_count": len(generated_ids),
        "done_reason": done_reason,
        "generated_text": generated_text,
        "moves": moves,
        "moves_final": moves,
        "moves_all_mentions": moves_all_mentions,
        "goal_reached_all_mentions": trajectory_debug["goal_reached_all_mentions"],
        "accuracy": accuracy,
        "final_accuracy": accuracy,
        "v_score": v_score,
        "elapsed_sec": round(elapsed, 3),
        "output_dir": str(output_dir),
    }
    result.update(trajectory_debug)

    (output_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    (output_dir / "formatted_prompt.txt").write_text(formatted_prompt, encoding="utf-8")
    (output_dir / "generated.txt").write_text(generated_text, encoding="utf-8")
    (output_dir / "debug.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("=" * 80)
    print(f"Debug output: {output_dir}")
    print(f"model={args.model_id}  puzzle={args.puzzle}  N={args.N}  n_shot={args.n_shot}")
    print(f"initial={env.initial_state}  goal={env.goal_state}  min_moves={env.min_moves}")
    print(f"optimal={env.solve()}")
    print(f"done_reason={done_reason}  generated_tokens={len(generated_ids)}  elapsed={elapsed:.1f}s")
    print("-" * 80)
    print("[PROMPT]")
    print(prompt)
    if args.print_formatted_prompt:
        print("-" * 80)
        print("[FORMATTED PROMPT]")
        print(formatted_prompt)
    print("-" * 80)
    print("[GENERATED]")
    print(generated_text)
    print("-" * 80)
    print(f"moves_final={moves}")
    print(f"moves_all_mentions={moves_all_mentions}")
    print(f"final_accuracy={accuracy}  v_score={v_score}")
    print("=" * 80)


if __name__ == "__main__":
    main()
