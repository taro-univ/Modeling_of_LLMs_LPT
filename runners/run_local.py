"""
run_hf.py — ハノイの塔 推論崩壊検知 (HuggingFace Transformers 版)

run.py (Ollama API 版) の HuggingFace 対応版。
DeepSeek-R1-Distill-Qwen-7B を NF4 4-bit 量子化でローカル実行し、
Move 出力位置で隠れ状態ベクトルを選択的に保存する。

使用例:
  python run_hf.py --N 3
  python run_hf.py --N 5 --trials 10
  python run_hf.py --N 5 --no-early-stop --device cuda:1
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from envs.hanoi_env import TowerOfHanoiEnv
from runners.run import (
    EarlyStopConfig,
    _MOVE_RE,
    _estimate_reasoning_tokens,
    calc_default_trials,
    calc_num_predict,
    calc_think_budget_ratio,
    check_early_stop,
)

# ディスク番号込みの3-tuple で Move を抽出（ループ誤検知防止用）
# run.py の _MOVE_RE は (src, dst) のみで disk を落とすため、正解手列内の
# 同ペグ間異ディスク移動を誤ってループと判定してしまう。
_MOVE_RE_WITH_DISK = re.compile(
    r'Move\s+(\d+)\s+from\s+([ABC])\s+to\s+([ABC])',
    re.IGNORECASE,
)

# ===========================================================================
# 定数
# ===========================================================================

MODEL_ID = "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B"


# ===========================================================================
# Few-shot プロンプト構築
# ===========================================================================

# 再帰戦略ヒント: N=2 で A→B（中間ペグ）を正しく選ばせるための一般原則。
# 答えを直接与えず、再帰的思考の枠組みを与えることで汎化性を保つ。
SYSTEM_HINT = (
    "You are an expert at the Tower of Hanoi puzzle. "
    "Always apply the recursive strategy: to move N disks from peg X to peg Z, "
    "(1) move the top N-1 disks from X to the intermediate peg Y, "
    "(2) move disk N from X to Z, "
    "(3) move the N-1 disks from Y to Z. "
    "Identify the correct intermediate peg before making any move."
)


def build_few_shot_messages(env: TowerOfHanoiEnv, n_shot: int) -> list[dict]:
    """
    システムヒント + マルチターン few-shot メッセージリストを構築する。

    先頭に再帰戦略の system メッセージを置き、N-n_shot〜N-1 の正解例を
    User→Assistant ターンで提示してから本番問題を末尾に追加する。

    N=2: N=1 の例 1 つ → 中間ペグ選択の習得を狙う
    N=3: N=1, N=2 の例 2 つ → 偶奇パリティの学習
    N=4+: N-2, N-1 の例 2 つ → 直近パターンの転移

    Args:
        env: 本番の TowerOfHanoiEnv（N を参照するために使用）。
        n_shot: 提示する例の数（1 or 2）。

    Returns:
        messages リスト（system → few-shot turns → 本番 User メッセージ）。
    """
    messages: list[dict] = [{"role": "system", "content": SYSTEM_HINT}]

    example_ns = list(range(max(1, env.N - n_shot), env.N))
    for ex_n in example_ns:
        ex_env = TowerOfHanoiEnv(N=ex_n)
        solution_lines = "\n".join(ex_env.solve())
        messages.append({"role": "user",      "content": ex_env.get_prompt()})
        messages.append({"role": "assistant", "content": solution_lines})

    messages.append({"role": "user", "content": env.get_prompt()})
    return messages

# 保存対象レイヤーインデックス（負のインデックスで指定）
# hidden_states は (embedding + 28 transformer) = 29 要素のタプル
CAPTURE_LAYERS: dict[str, int] = {
    "layer_m1":  -1,   # 最終出力層 (layer 28)
    "layer_m8":  -8,   # 中間後半層 (layer 21)
    "layer_m16": -16,  # 中間層    (layer 13)
}


# ===========================================================================
# モデルロード
# ===========================================================================

def load_model_and_tokenizer(
    model_id: str,
    device: str,
) -> tuple[AutoModelForCausalLM, AutoTokenizer]:
    """
    NF4 4-bit 量子化でモデルとトークナイザーをロードする。

    NF4 量子化: 正規分布 N(0,1) の分位点を格子点に使うため、
    Transformer の重みが経験的に正規分布に従うことを活用し
    INT4 より量子化誤差を低減する。

    Args:
        model_id: HuggingFace モデル ID。
        device: デバイス指定 (例: "cuda:0")。

    Returns:
        (model, tokenizer) のタプル。
    """
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,  # スケールを 8-bit で二重量子化
    )

    print(f"[INFO] モデルをロード中: {model_id}  device={device}")
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        quantization_config=bnb_config,
        device_map=device,
        torch_dtype=torch.bfloat16,
    )
    model.eval()

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print(f"[INFO] ロード完了  hidden_size={model.config.hidden_size}"
          f"  num_layers={model.config.num_hidden_layers}")
    return model, tokenizer


# ===========================================================================
# 隠れ状態キャプチャ付き逐次生成ループ
# ===========================================================================

@dataclass
class GenerationResult:
    """generate_with_hidden_states() の返り値。"""
    text: str
    total_tokens: int
    reasoning_tokens: int
    early_stop: Optional[str]
    # Move 位置ごとの隠れ状態: {layer_key: np.ndarray of shape (num_moves, hidden_size)}
    hidden_states: dict[str, np.ndarray]
    move_steps: np.ndarray    # shape: (num_moves,) — 何ステップ目で検出されたか
    move_texts: list[str]     # 検出された手の文字列リスト


def generate_with_hidden_states(
    model: AutoModelForCausalLM,
    tokenizer: AutoTokenizer,
    prompt: str,
    num_predict: int,
    min_moves: int,
    env: TowerOfHanoiEnv,
    early_stop_cfg: Optional[EarlyStopConfig] = None,
    temperature: float = 0.6,
    repetition_penalty: float = 1.1,
    n_shot: int = 0,
) -> GenerationResult:
    """
    トークンを 1 つずつ生成するカスタムループ。

    KV キャッシュを引き継ぐことで速度は model.generate() とほぼ同等。
    Move 文字列が完成した直後のステップで hidden_states を CPU に転送し保存する。

    Args:
        model: ロード済みモデル。
        tokenizer: トークナイザー。
        prompt: 入力プロンプト文字列。
        num_predict: 最大生成トークン数。
        min_moves: この N の最短手数（早期終了判定に使用）。
        early_stop_cfg: 早期終了設定。None なら無効。

    Returns:
        GenerationResult インスタンス。
    """
    device = next(model.parameters()).device

    # system ヒント + few-shot（n_shot=0 でも system ヒントは常に適用）
    if n_shot > 0:
        messages = build_few_shot_messages(env, n_shot)
    else:
        messages = [
            {"role": "system", "content": SYSTEM_HINT},
            {"role": "user",   "content": prompt},
        ]

    # Qwen 系モデルはチャットテンプレート必須。
    # <think> をプリフィルして DeepSeek-R1 の推論モードを強制起動する。
    formatted = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    formatted += "<think>\n"
    input_ids = tokenizer(formatted, return_tensors="pt").input_ids.to(device)

    # 生成トークンを蓄積するバッファ
    generated_ids: list[int] = []
    accumulated_text = ""
    past_key_values = None
    stop_reason: Optional[str] = None

    # 隠れ状態バッファ: {layer_key: list of 1D numpy array}
    hs_buffer: dict[str, list[np.ndarray]] = {k: [] for k in CAPTURE_LAYERS}
    move_steps_list: list[int] = []
    move_texts_list: list[str] = []

    # 直前ステップまでに抽出済みの手数（重複キャプチャ防止）
    prev_move_count = 0

    current_input_ids = input_ids

    for step in range(num_predict):
        with torch.no_grad():
            outputs = model(
                input_ids=current_input_ids,
                past_key_values=past_key_values,
                use_cache=True,
                output_hidden_states=True,
            )

        # Repetition penalty: 生成済みトークンの logits を減衰させてループを抑制
        logits = outputs.logits[0, -1, :].float()
        if repetition_penalty != 1.0 and generated_ids:
            for token_id in set(generated_ids):
                if logits[token_id] > 0:
                    logits[token_id] /= repetition_penalty
                else:
                    logits[token_id] *= repetition_penalty

        # Temperature sampling（greedy は決定論的で全試行が同一出力になるため使用しない）
        logits = logits / temperature
        probs = torch.softmax(logits, dim=-1)
        next_token_id = int(torch.multinomial(probs, num_samples=1).item())

        # EOS チェック
        if next_token_id == tokenizer.eos_token_id:
            break

        generated_ids.append(next_token_id)
        past_key_values = outputs.past_key_values

        # BPE サブワード境界のズレを防ぐため、全トークンを一括デコード
        accumulated_text = tokenizer.decode(generated_ids, skip_special_tokens=True)

        # Move 検出: ディスク番号込みで抽出（hidden state キャプチャ & move_texts 用）
        current_moves_full = _MOVE_RE_WITH_DISK.findall(accumulated_text)  # (disk, src, dst)
        current_move_count = len(current_moves_full)

        if current_move_count > prev_move_count:
            for mv_idx in range(prev_move_count, current_move_count):
                for layer_key, layer_idx in CAPTURE_LAYERS.items():
                    hs_tensor = outputs.hidden_states[layer_idx][0, -1, :]
                    hs_buffer[layer_key].append(hs_tensor.float().cpu().numpy())
                move_steps_list.append(step)
                disk, src, dst = current_moves_full[mv_idx]
                move_texts_list.append(f"Move {disk} from {src} to {dst}")

            prev_move_count = current_move_count

            # ゴール到達を検知したら即停止（以降の手が hidden state を汚染するのを防ぐ）
            extracted = env.extract_moves_from_text(accumulated_text)
            if env.goal_reached(extracted):
                stop_reason = "goal_reached"
                break

        # 次ステップの入力は今生成したトークンのみ（KV キャッシュを活用）
        current_input_ids = torch.tensor([[next_token_id]], device=device)
        last_outputs = outputs  # フォールバック用に最終ステップの出力を保持

        # 早期終了チェック（50 文字おきに評価してオーバーヘッドを抑える）
        # Algorithm C (move_loop) のみディスク番号込みの3-tuple で再判定し誤爆を防ぐ
        if early_stop_cfg is not None and len(accumulated_text) % 50 < 5:
            reason = check_early_stop(
                accumulated_text, num_predict, min_moves, early_stop_cfg
            )
            if reason in ("move_loop_repeat", "move_loop_reverse"):
                # ディスク番号を含めて再チェック: 同じ (disk,src,dst) が繰り返すか確認
                cfg = early_stop_cfg
                if len(current_moves_full) >= cfg.loop_window:
                    recent = current_moves_full[-cfg.loop_window:]
                    disk_loop = any(
                        recent.count(mv) >= cfg.loop_min_count for mv in set(recent)
                    )
                    reverse_loop = any(
                        recent[i][1] == recent[i+1][2]
                        and recent[i][2] == recent[i+1][1]
                        and recent[i][0] == recent[i+1][0]
                        for i in range(len(recent) - 1)
                    )
                    if not (disk_loop or reverse_loop):
                        reason = None  # 誤検知: ディスクが違うので無視
            if reason:
                stop_reason = reason
                break

    total_tokens = len(generated_ids)
    # <think> をプリフィルしているため、生成テキストは </think> を含む形になる。
    # reasoning_tokens 推定のため <think> を先頭に補って渡す。
    reasoning_tokens = _estimate_reasoning_tokens("<think>\n" + accumulated_text, total_tokens)

    # moves が1本も取れなかった場合（常磁性相: no_move_catchall 等）、
    # 最終トークンの hidden state をフォールバックとして記録する。
    # これにより P(q) 解析で常磁性相とスピングラス相を比較できる。
    if not move_steps_list and generated_ids and 'last_outputs' in dir():
        for layer_key, layer_idx in CAPTURE_LAYERS.items():
            hs_tensor = last_outputs.hidden_states[layer_idx][0, -1, :]
            hs_buffer[layer_key].append(hs_tensor.float().cpu().numpy())
        move_steps_list.append(step)
        move_texts_list.append("__fallback__")

    # list[np.ndarray] → np.ndarray of shape (num_moves, hidden_size)
    hidden_states_np: dict[str, np.ndarray] = {}
    num_captured = len(move_steps_list)
    for layer_key in CAPTURE_LAYERS:
        if hs_buffer[layer_key]:
            hidden_states_np[layer_key] = np.stack(hs_buffer[layer_key], axis=0)
        else:
            hidden_states_np[layer_key] = np.empty((0, model.config.hidden_size), dtype=np.float32)

    return GenerationResult(
        text=accumulated_text,
        total_tokens=total_tokens,
        reasoning_tokens=reasoning_tokens,
        early_stop=stop_reason,
        hidden_states=hidden_states_np,
        move_steps=np.array(move_steps_list, dtype=np.int32),
        move_texts=move_texts_list,
    )


# ===========================================================================
# 実験ループ
# ===========================================================================

def run_experiment_hf(
    N: int,
    trials: int,
    model: AutoModelForCausalLM,
    tokenizer: AutoTokenizer,
    num_predict: Optional[int] = None,
    early_stop_cfg: Optional[EarlyStopConfig] = None,
    output_dir: Optional[Path] = None,
    temperature: float = 0.6,
    repetition_penalty: float = 1.1,
    n_shot: int = 2,
) -> list[dict]:
    """
    N 枚ハノイの塔で trials 回の推論を実行し、結果リストを返す。

    Args:
        N: 円盤の枚数。
        trials: 試行回数。
        model: ロード済みモデル。
        tokenizer: トークナイザー。
        num_predict: 最大出力トークン数。None なら calc_num_predict(N) を使用。
        early_stop_cfg: 早期終了設定。None なら無効。
        output_dir: npz 保存先ディレクトリ。None なら保存しない。

    Returns:
        各試行の結果辞書のリスト。
    """
    env = TowerOfHanoiEnv(N=N)
    results: list[dict] = []
    num_predict_ = num_predict if num_predict is not None else calc_num_predict(N)

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)

    es_label = "有効" if early_stop_cfg is not None else "無効"
    print(f"\n{'='*60}")
    print(f"  Tower of Hanoi (HF)  N={N}  trials={trials}  model={MODEL_ID}")
    print(f"  最短手数 (2^N-1): {env.min_moves}")
    print(f"  num_predict: {num_predict_}")
    print(f"  早期終了:    {es_label}")
    print(f"  出力先:      {output_dir}")
    print(f"{'='*60}\n")

    for trial in range(1, trials + 1):
        print(f"--- Trial {trial}/{trials} ---")
        prompt = env.get_prompt()

        t_start = time.time()
        result_gen = generate_with_hidden_states(
            model=model,
            tokenizer=tokenizer,
            prompt=prompt,
            num_predict=num_predict_,
            min_moves=env.min_moves,
            env=env,
            early_stop_cfg=early_stop_cfg,
            temperature=temperature,
            repetition_penalty=repetition_penalty,
            n_shot=n_shot,
        )
        elapsed = time.time() - t_start

        moves = env.extract_moves_from_text(result_gen.text)
        accuracy = 1 if env.goal_reached(moves) else 0
        v_score = env.evaluate_state(moves)

        result: dict = {
            "trial":            trial,
            "accuracy":         accuracy,
            "total_tokens":     result_gen.total_tokens,
            "reasoning_tokens": result_gen.reasoning_tokens,
            "num_predict":      num_predict_,
            "moves_extracted":  len(moves),
            "moves_captured":   int(result_gen.move_steps.shape[0]),
            "v_score":          v_score,
            "elapsed_sec":      round(elapsed, 2),
            "early_stop":       result_gen.early_stop,
        }
        results.append(result)

        status = "PASS" if accuracy else "FAIL"
        es_info = f"  es={result_gen.early_stop}" if result_gen.early_stop else ""
        print(f"  [{status}] accuracy={accuracy}  "
              f"total_tokens={result_gen.total_tokens}  "
              f"reasoning_tokens={result_gen.reasoning_tokens}  "
              f"v_score={v_score:.4f}  "
              f"moves={len(moves)}  captured={result_gen.move_steps.shape[0]}  "
              f"time={elapsed:.1f}s{es_info}")

        # 隠れ状態を npz 形式で保存
        if output_dir is not None:
            npz_path = output_dir / f"trial_{trial:03d}_hidden.npz"
            np.savez(
                npz_path,
                **result_gen.hidden_states,
                move_steps=result_gen.move_steps,
                move_texts=np.array(result_gen.move_texts, dtype=object),
            )
            print(f"  [SAVE] {npz_path}")

    return results


def print_summary(results: list[dict], N: int) -> None:
    """実験結果のサマリーを標準出力へ表示する。"""
    n = len(results)
    avg_acc = sum(r["accuracy"] for r in results) / n
    avg_tok = sum(r["total_tokens"] for r in results) / n
    avg_reas = sum(r["reasoning_tokens"] for r in results) / n
    avg_v = sum(r["v_score"] for r in results) / n

    es_counts: dict[str, int] = {}
    for r in results:
        reason = r.get("early_stop")
        if reason:
            es_counts[reason] = es_counts.get(reason, 0) + 1

    print(f"\n{'='*60}")
    print(f"  Summary (HF)  N={N}  trials={n}")
    print(f"{'='*60}")
    print(f"  Accuracy (goal_reached):     {avg_acc:.3f}  ({sum(r['accuracy'] for r in results)}/{n})")
    print(f"  Avg total tokens:            {avg_tok:.1f}")
    print(f"  Avg reasoning tokens (est.): {avg_reas:.1f}")
    print(f"  Avg V(x) score:              {avg_v:.4f}  (0=goal, 1=initial)")
    if es_counts:
        print(f"  Early stop breakdown:        {es_counts}")
    print(f"{'='*60}\n")


# ===========================================================================
# エントリポイント
# ===========================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ハノイの塔で LLM の推論崩壊を検知する (HuggingFace Transformers 版)"
    )
    parser.add_argument("--N",           type=int,   required=True,
                        help="円盤の枚数")
    parser.add_argument("--trials",      type=int,   default=None,
                        help="試行回数（省略時は N に応じて自動設定）")
    parser.add_argument("--model-id",    type=str,   default=MODEL_ID,
                        help=f"HuggingFace モデル ID (default: {MODEL_ID})")
    parser.add_argument("--device",      type=str,   default="cuda:0",
                        help="デバイス (default: cuda:0)")
    parser.add_argument("--num_predict", type=int,   default=None,
                        help="最大出力トークン数の手動指定（省略時は N に応じて自動設定）")
    parser.add_argument("--output",      type=str,   default=None,
                        help="summary JSON の保存先パス")
    parser.add_argument("--output-dir",  type=str,   default=None,
                        help="隠れ状態 npz の保存先ディレクトリ（省略時は自動生成）")
    parser.add_argument("--no-save-hidden", action="store_true",
                        help="隠れ状態の npz を保存しない")
    parser.add_argument("--no-early-stop",  action="store_true",
                        help="早期終了アルゴリズムを無効化する")

    # 早期終了パラメータ
    parser.add_argument("--es-think-ratio", type=float, default=None)
    parser.add_argument("--es-move-mult",   type=float, default=1.5)
    parser.add_argument("--es-loop-window", type=int,   default=6)
    parser.add_argument("--es-loop-count",  type=int,   default=2)
    parser.add_argument("--temperature",         type=float, default=0.6,
                        help="サンプリング温度 (default: 0.6)")
    parser.add_argument("--repetition-penalty",  type=float, default=1.1,
                        help="繰り返しペナルティ ρ (default: 1.1, 1.0 で無効)")
    parser.add_argument("--n-shot",              type=int,   default=1,
                        help="few-shot 例の数 (default: 1, 0 で無効)")
    parser.add_argument("--sweep-type",          type=str,   default="hf",
                        help="実験種別ラベル（DB の sweep_type カラムに対応）")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    trials = args.trials if args.trials is not None else calc_default_trials(args.N)
    think_ratio = (
        args.es_think_ratio
        if args.es_think_ratio is not None
        else calc_think_budget_ratio(args.N)
    )

    early_stop_cfg: Optional[EarlyStopConfig] = None
    if not args.no_early_stop:
        early_stop_cfg = EarlyStopConfig(
            think_budget_ratio=think_ratio,
            max_move_multiplier=args.es_move_mult,
            loop_window=args.es_loop_window,
            loop_min_count=args.es_loop_count,
        )

    # 出力ディレクトリの解決
    output_dir: Optional[Path] = None
    if not args.no_save_hidden:
        base = args.output_dir or f"results/hanoi/results_N{args.N}_hf"
        output_dir = Path(base)

    # summary.json の保存先を確定（meta.json の書き出し先に使う）
    summary_path = Path(args.output) if args.output else (
        output_dir / "summary.json" if output_dir else None
    )

    # meta.json を summary.json より先に書き出す
    # → 実験途中でクラッシュしても sync.sh が "waiting" として検知できる
    if summary_path is not None:
        meta_dir = summary_path.parent
        meta_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "environment": "hanoi",
            "model":       args.model_id,
            "N":           args.N,
            "temperature": args.temperature,
            "sweep_type":  args.sweep_type,
        }
        meta_path = meta_dir / "meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        print(f"メタデータを保存しました: {meta_path}")

    # モデルロード
    model, tokenizer = load_model_and_tokenizer(args.model_id, args.device)

    results = run_experiment_hf(
        N=args.N,
        trials=trials,
        model=model,
        tokenizer=tokenizer,
        num_predict=args.num_predict,
        early_stop_cfg=early_stop_cfg,
        output_dir=output_dir,
        temperature=args.temperature,
        repetition_penalty=args.repetition_penalty,
        n_shot=args.n_shot,
    )

    print_summary(results, args.N)

    # summary.json を自動保存
    if summary_path is not None:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"結果を保存しました: {summary_path}")


if __name__ == "__main__":
    main()
