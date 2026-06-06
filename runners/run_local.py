"""
run_local.py — ハノイの塔 推論崩壊検知 (HuggingFace Transformers 版)

run.py (Ollama API 版) の HuggingFace 対応版。
DeepSeek-R1-Distill-Qwen-7B を NF4 4-bit 量子化でローカル実行し、
Move 出力位置で隠れ状態ベクトルを選択的に保存する。

使用例:
  python runners/run_local.py --N 3
  python runners/run_local.py --N 5 --trials 10
  python runners/run_local.py --N 5 --no-early-stop --device cuda:1
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from envs.base_env import BaseEnv
from envs.hanoi_env import TowerOfHanoiEnv
from envs.lights_out_env import LightsOutEnv
from runners.run import (
    EarlyStopConfig,
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

@dataclass
class ModelProfile:
    """モデルごとの推論設定（think 起動方式とタグ）を保持する。"""
    model_id:        str
    think_mode:      str   # "prefill" | "chat_template" | "none"
    think_open_tag:  str = "<think>"
    think_close_tag: str = "</think>"


def resolve_model_profile(model_id: str) -> ModelProfile:
    """model_id のプレフィックスマッチで ModelProfile を自動選択する。"""
    lm = model_id.lower()
    if lm.startswith("qwen/qwen3"):
        # Qwen3 は apply_chat_template の enable_thinking=True で thinking を起動する
        return ModelProfile(model_id=model_id, think_mode="chat_template")
    if lm.startswith("meta-llama"):
        # Meta-Llama 系は推論タグを持たない標準 instruct モデル
        return ModelProfile(model_id=model_id, think_mode="none")
    # DeepSeek-R1-Distill 系（Qwen/Llama ベース）は <think> プリフィルで起動する
    return ModelProfile(model_id=model_id, think_mode="prefill")


def model_id_to_slug(model_id: str) -> str:
    """HuggingFace model_id からファイルシステム安全なスラグを生成する。

    "org/ModelName" → "modelname"（組織名を除いた名前部分を小文字化）
    """
    return model_id.split("/")[-1].lower()


# ===========================================================================
# Few-shot プロンプト構築
# ===========================================================================

def build_few_shot_messages(env: BaseEnv, n_shot: int) -> list[dict]:
    """
    システムヒント + マルチターン few-shot メッセージリストを構築する。

    先頭に env 固有の system メッセージを置き、N-n_shot〜N-1 の正解例を
    User→Assistant ターンで提示してから本番問題を末尾に追加する。

    N=2: N=1 の例 1 つ → 中間ペグ選択の習得を狙う
    N=3: N=1, N=2 の例 2 つ → 偶奇パリティの学習
    N=4+: N-2, N-1 の例 2 つ → 直近パターンの転移

    Args:
        env: 本番の BaseEnv（N を参照するために使用）。
        n_shot: 提示する例の数（1 or 2）。

    Returns:
        messages リスト（system → few-shot turns → 本番 User メッセージ）。
    """
    messages: list[dict] = [{"role": "system", "content": env.get_system_hint()}]

    example_ns = list(range(max(1, env.N - n_shot), env.N))
    for ex_n in example_ns:
        # TODO(SPEC-FUTURE): build_few_shot_messages はハノイ専用プロンプトを使用。
        # LightsOutEnv 対応は別 SPEC で BaseEnv.get_few_shot_examples() 等を追加して対応予定。
        ex_env = env.make_sub_env(ex_n)
        solution_lines = "\n".join(ex_env.solve())
        messages.append({"role": "user",      "content": ex_env.get_prompt()})
        messages.append({"role": "assistant", "content": solution_lines})

    messages.append({"role": "user", "content": env.get_prompt()})
    return messages

def make_capture_layers(num_hidden_layers: int) -> dict[str, int]:
    """層数に依存しない相対深度でキャプチャ層を決定する。

    負インデックスで返す。hidden_states タプルは (embedding + N transformer) の
    N+1 要素なので、abs(idx) <= num_hidden_layers が有効範囲。
    """
    return {
        "layer_top":  -1,                              # 100% 深度（最終層）
        "layer_mid":  -(num_hidden_layers // 2),       #  50% 深度
        "layer_low":  -(num_hidden_layers * 3 // 4),   #  25% 深度
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
        dtype=torch.bfloat16,
        trust_remote_code=True,
    )
    model.eval()

    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
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


def _estimate_reasoning_tokens_with_profile(
    text: str, total_tokens: int, profile: ModelProfile
) -> int:
    """profile の think タグを使って reasoning_tokens を近似する。"""
    open_tag = re.escape(profile.think_open_tag)
    close_tag = re.escape(profile.think_close_tag)
    match = re.search(f'{open_tag}(.*?){close_tag}', text, re.DOTALL | re.IGNORECASE)
    if not match:
        return 0
    think_len = len(match.group(1))
    total_len = max(len(text), 1)
    return int(total_tokens * (think_len / total_len))


def _prepare_input_ids(
    tokenizer: AutoTokenizer,
    prompt: str,
    env: BaseEnv,
    n_shot: int,
    profile: ModelProfile,
) -> torch.Tensor:
    """messages を構築し、chat template を適用して input_ids を返す。

    `.to(device)` は呼び出し側で行う。
    """
    if n_shot > 0:
        messages = build_few_shot_messages(env, n_shot)
    else:
        messages = [
            {"role": "system", "content": env.get_system_hint()},
            {"role": "user",   "content": prompt},
        ]

    if profile.think_mode == "chat_template":
        # Qwen3 系: enable_thinking=True でトークナイザーが thinking モードを制御する
        formatted = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
            enable_thinking=True,
        )
    else:
        formatted = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        if profile.think_mode == "prefill":
            # DeepSeek-R1 系: <think> をプリフィルして推論モードを強制起動する
            formatted += profile.think_open_tag + "\n"

    return tokenizer(formatted, return_tensors="pt").input_ids


def _apply_repetition_penalty(
    logits: torch.Tensor,
    generated_ids: list[int],
    penalty: float,
) -> None:
    """生成済みトークンの logits を in-place で減衰させてループを抑制する。"""
    if penalty == 1.0 or not generated_ids:
        return
    for token_id in set(generated_ids):
        if logits[token_id] > 0:
            logits[token_id] /= penalty
        else:
            logits[token_id] *= penalty


def _sample_next_token(logits: torch.Tensor, temperature: float) -> int:
    """温度サンプリングで次の token id を返す。"""
    scaled = logits / temperature
    probs = torch.softmax(scaled, dim=-1)
    return int(torch.multinomial(probs, num_samples=1).item())


def _capture_new_move_hidden_states(
    outputs,
    capture_layers: dict[str, int],
    current_move_texts: list[str],
    prev_move_count: int,
    step: int,
    hs_buffer: dict[str, list[np.ndarray]],
    move_steps_list: list[int],
    move_texts_list: list[str],
) -> int:
    """prev_move_count 以降の新しい Move について hidden state をキャプチャする。

    Returns:
        current_move_count（新しい prev_move_count として使う）。
    """
    current_move_count = len(current_move_texts)
    for mv_idx in range(prev_move_count, current_move_count):
        for layer_key, layer_idx in capture_layers.items():
            hs_tensor = outputs.hidden_states[layer_idx][0, -1, :]
            hs_buffer[layer_key].append(hs_tensor.float().cpu().numpy())
        move_steps_list.append(step)
        move_texts_list.append(current_move_texts[mv_idx])
    return current_move_count


def _parse_hanoi_move_tuple(move_text: str) -> Optional[tuple[str, str, str]]:
    """Return (disk, src, dst) for Hanoi move text, or None for other puzzles."""
    match = _MOVE_RE_WITH_DISK.search(move_text)
    if not match:
        return None
    disk, src, dst = match.groups()
    return disk, src.upper(), dst.upper()


def _is_disk_loop_confirmed(
    current_move_texts: list[str],
    cfg: EarlyStopConfig,
) -> bool:
    """ディスク番号込みでループを再検証する。

    loop_window と loop_min_count を使って disk_loop と reverse_loop の OR を返す。
    """
    parsed_moves = [
        parsed for move_text in current_move_texts
        if (parsed := _parse_hanoi_move_tuple(move_text)) is not None
    ]
    if len(parsed_moves) < cfg.loop_window:
        return False
    recent = parsed_moves[-cfg.loop_window:]
    disk_loop = any(
        recent.count(mv) >= cfg.loop_min_count for mv in set(recent)
    )
    reverse_loop = any(
        recent[i][1] == recent[i + 1][2]
        and recent[i][2] == recent[i + 1][1]
        and recent[i][0] == recent[i + 1][0]
        for i in range(len(recent) - 1)
    )
    return disk_loop or reverse_loop


def _check_early_stop_with_disk_verify(
    accumulated_text: str,
    num_predict: int,
    min_moves: int,
    early_stop_cfg: EarlyStopConfig,
    current_move_texts: list[str],
    env: BaseEnv,
) -> Optional[str]:
    """check_early_stop を呼び、move_loop 系は disk 番号込みで再検証する。

    誤検知（disk 番号が違う）の場合は None を返す。
    """
    reason = check_early_stop(
        accumulated_text,
        num_predict,
        min_moves,
        early_stop_cfg,
        env=env,
        moves=current_move_texts,
    )
    if reason in ("move_loop_repeat", "move_loop_reverse"):
        if not _is_disk_loop_confirmed(current_move_texts, early_stop_cfg):
            return None  # 誤検知: ディスクが違うので無視
    return reason


def _finalize_hidden_states(
    hs_buffer: dict[str, list[np.ndarray]],
    capture_layers: dict[str, int],
    move_steps_list: list[int],
    move_texts_list: list[str],
    step: int,
    generated_ids: list[int],
    last_outputs,
    hidden_size: int,
) -> dict[str, np.ndarray]:
    """hidden state バッファを ndarray に変換して返す。

    move が 1 本も取れなかった場合（fallback）は last_outputs の最終トークンを記録し、
    move_steps_list / move_texts_list に "__fallback__" を in-place で追記する。
    """
    if not move_steps_list and generated_ids and last_outputs is not None:
        for layer_key, layer_idx in capture_layers.items():
            hs_tensor = last_outputs.hidden_states[layer_idx][0, -1, :]
            hs_buffer[layer_key].append(hs_tensor.float().cpu().numpy())
        move_steps_list.append(step)
        move_texts_list.append("__fallback__")

    hidden_states_np: dict[str, np.ndarray] = {}
    for layer_key in capture_layers:
        if hs_buffer[layer_key]:
            hidden_states_np[layer_key] = np.stack(hs_buffer[layer_key], axis=0)
        else:
            hidden_states_np[layer_key] = np.empty((0, hidden_size), dtype=np.float32)
    return hidden_states_np


def _handle_new_moves(
    outputs,
    capture_layers: dict[str, int],
    current_move_texts: list[str],
    prev_move_count: int,
    step: int,
    hs_buffer: dict[str, list[np.ndarray]],
    move_steps_list: list[int],
    move_texts_list: list[str],
    env: BaseEnv,
    accumulated_text: str,
    disable_goal_stop: bool,
) -> tuple[int, Optional[str]]:
    """新しい Move のキャプチャとゴール到達チェックをまとめて行う。

    Returns:
        (new_prev_move_count, stop_reason_or_None)
    """
    new_prev_move_count = _capture_new_move_hidden_states(
        outputs, capture_layers, current_move_texts,
        prev_move_count, step, hs_buffer, move_steps_list, move_texts_list,
    )
    if disable_goal_stop:
        return new_prev_move_count, None
    extracted = env.extract_moves_from_text(accumulated_text)
    if env.goal_reached(extracted):
        return new_prev_move_count, "goal_reached"
    return new_prev_move_count, None


def _build_reasoning_text(accumulated_text: str, profile: ModelProfile) -> str:
    """prefill モード用に think_open_tag を先頭に補った reasoning_text を返す。"""
    if profile.think_mode == "prefill":
        return profile.think_open_tag + "\n" + accumulated_text
    return accumulated_text


def _should_check_early_stop(
    early_stop_cfg: Optional[EarlyStopConfig],
    accumulated_text: str,
) -> bool:
    """早期終了チェックを実行すべきかどうかを返す（50 文字おき）。"""
    return early_stop_cfg is not None and len(accumulated_text) % 50 < 5


def generate_with_hidden_states(
    model: AutoModelForCausalLM,
    tokenizer: AutoTokenizer,
    prompt: str,
    num_predict: int,
    min_moves: int,
    env: BaseEnv,
    early_stop_cfg: Optional[EarlyStopConfig] = None,
    temperature: float = 0.6,
    repetition_penalty: float = 1.1,
    n_shot: int = 0,
    profile: ModelProfile = None,             # type: ignore[assignment]  実質必須
    capture_layers: dict[str, int] = None,    # type: ignore[assignment]  実質必須
    disable_goal_stop: bool = False,
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
        env: パズル環境。BaseEnv の共通 API でプロンプト評価を行う。
        early_stop_cfg: 早期終了設定。None なら無効。
        profile: ModelProfile（必須）。resolve_model_profile() で生成すること。
        capture_layers: キャプチャ層マップ（必須）。make_capture_layers() で生成すること。

    Returns:
        GenerationResult インスタンス。
    """
    device = next(model.parameters()).device

    input_ids = _prepare_input_ids(tokenizer, prompt, env, n_shot, profile).to(device)

    # 生成トークンを蓄積するバッファ
    generated_ids: list[int] = []
    accumulated_text = ""
    past_key_values = None
    stop_reason: Optional[str] = None
    last_outputs = None

    hs_buffer: dict[str, list[np.ndarray]] = {k: [] for k in capture_layers}
    move_steps_list: list[int] = []
    move_texts_list: list[str] = []

    # 直前ステップまでに抽出済みの手数（重複キャプチャ防止）
    prev_move_count = 0
    current_input_ids = input_ids

    # Algorithm E: 最後に move を検出したステップ（token index）
    last_move_step: Optional[int] = None

    # for が 0 回の場合の step 未定義を防ぐ
    step = -1
    for step in range(num_predict):
        with torch.no_grad():
            outputs = model(
                input_ids=current_input_ids,
                past_key_values=past_key_values,
                use_cache=True,
                output_hidden_states=True,
            )

        logits = outputs.logits[0, -1, :].float()
        _apply_repetition_penalty(logits, generated_ids, repetition_penalty)
        next_token_id = _sample_next_token(logits, temperature)

        # EOS チェック
        if next_token_id == tokenizer.eos_token_id:
            break

        generated_ids.append(next_token_id)
        past_key_values = outputs.past_key_values

        # BPE サブワード境界のズレを防ぐため、全トークンを一括デコード
        accumulated_text = tokenizer.decode(generated_ids, skip_special_tokens=True)

        # Move 検出: env 固有の抽出器で手と出現位置を取得する
        current_moves_with_position = env.extract_moves_with_position(accumulated_text)
        current_move_texts = [move for move, _ in current_moves_with_position]

        if len(current_move_texts) > prev_move_count:
            last_move_step = step  # Algorithm E: 最後の move 検出ステップを更新
            prev_move_count, goal_stop = _handle_new_moves(
                outputs, capture_layers, current_move_texts,
                prev_move_count, step, hs_buffer, move_steps_list, move_texts_list,
                env, accumulated_text, disable_goal_stop,
            )
            if goal_stop:
                stop_reason = goal_stop
                break

        # 次ステップの入力は今生成したトークンのみ（KV キャッシュを活用）
        current_input_ids = torch.tensor([[next_token_id]], device=device)
        last_outputs = outputs  # フォールバック用に最終ステップの出力を保持

        # Algorithm E: Stagnation After Move（毎トークン・軽量チェック）
        # move を ≥1 本出した後、stagnation_ratio × num_predict トークン手が止まれば打ち切る
        if (early_stop_cfg is not None
                and early_stop_cfg.enable_stagnation
                and last_move_step is not None
                and step - last_move_step > num_predict * early_stop_cfg.stagnation_ratio):
            stop_reason = "stagnation_after_move"
            break

        # 早期終了チェック（50 文字おきに評価してオーバーヘッドを抑える）
        # Algorithm C (move_loop) のみディスク番号込みの3-tuple で再判定し誤爆を防ぐ
        if _should_check_early_stop(early_stop_cfg, accumulated_text):
            reason = _check_early_stop_with_disk_verify(
                accumulated_text,
                num_predict,
                min_moves,
                early_stop_cfg,
                current_move_texts,
                env,
            )
            if reason:
                stop_reason = reason
                break

    total_tokens = len(generated_ids)
    reasoning_tokens = _estimate_reasoning_tokens_with_profile(
        _build_reasoning_text(accumulated_text, profile), total_tokens, profile
    )

    hidden_states_np = _finalize_hidden_states(
        hs_buffer, capture_layers, move_steps_list, move_texts_list,
        step, generated_ids, last_outputs, model.config.hidden_size,
    )

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
    env: BaseEnv,
    N: int,
    trials: int,
    model_id: str,
    model: AutoModelForCausalLM,
    tokenizer: AutoTokenizer,
    num_predict: Optional[int] = None,
    early_stop_cfg: Optional[EarlyStopConfig] = None,
    output_dir: Optional[Path] = None,
    temperature: float = 0.6,
    repetition_penalty: float = 1.1,
    n_shot: int = 2,
    profile: Optional[ModelProfile] = None,
    capture_layers: Optional[dict[str, int]] = None,
) -> list[dict]:
    """
    指定されたパズル環境で trials 回の推論を実行し、結果リストを返す。

    Args:
        env: パズル環境。
        N: 問題サイズ。
        trials: 試行回数。
        model: ロード済みモデル。
        tokenizer: トークナイザー。
        num_predict: 最大出力トークン数。None なら calc_num_predict(N) を使用。
        early_stop_cfg: 早期終了設定。None なら無効。
        output_dir: npz 保存先ディレクトリ。None なら保存しない。

    Returns:
        各試行の結果辞書のリスト。
    """
    results: list[dict] = []
    num_predict_ = num_predict if num_predict is not None else calc_num_predict(N)

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)

    es_label = "有効" if early_stop_cfg is not None else "無効"
    print(f"\n{'='*60}")
    print(f"  {env.__class__.__name__} (HF)  N={N}  trials={trials}  model={model_id}")
    print(f"  最短手数: {env.min_moves}")
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
            profile=profile,
            capture_layers=capture_layers,
        )
        elapsed = time.time() - t_start

        moves = env.extract_moves_from_text(result_gen.text)
        accuracy = 1 if env.goal_reached(moves) else 0
        v_score = env.evaluate_state(moves)

        result: dict = {
            "trial":            trial,
            "accuracy":         accuracy,
            "N":                N,
            "temperature":      temperature,
            "total_tokens":     result_gen.total_tokens,
            "reasoning_tokens": result_gen.reasoning_tokens,
            "num_predict":      num_predict_,
            "num_moves":        len(moves),
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
    parser.add_argument(
        "--model-id", type=str,
        default="deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
        help="HuggingFace モデル ID (default: deepseek-ai/DeepSeek-R1-Distill-Qwen-7B)",
    )
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
    parser.add_argument("--no-early-stop",      action="store_true",
                        help="早期終了アルゴリズムを無効化する")
    parser.add_argument("--no-loop-detection",  action="store_true",
                        help="Algorithm C（ループ検出）を無効化する。Lights Out など involution を持つパズル向け")

    # 早期終了パラメータ
    parser.add_argument("--es-think-ratio", type=float, default=None)
    parser.add_argument("--es-move-mult",   type=float, default=1.5)
    parser.add_argument("--es-loop-window", type=int,   default=6)
    parser.add_argument("--es-loop-count",  type=int,   default=2)
    parser.add_argument("--seed",           type=int,   default=None,
                        help="env 初期状態の乱数シード（Lights Out で盤面を固定する場合に使用）")
    parser.add_argument("--temperature",         type=float, default=0.6,
                        help="サンプリング温度 (default: 0.6)")
    parser.add_argument("--repetition-penalty",  type=float, default=1.1,
                        help="繰り返しペナルティ ρ (default: 1.1, 1.0 で無効)")
    parser.add_argument("--n-shot",              type=int,   default=1,
                        help="few-shot 例の数 (default: 1, 0 で無効)")
    parser.add_argument("--sweep-type",          type=str,   default="hf",
                        help="実験種別ラベル（DB の sweep_type カラムに対応）")
    parser.add_argument(
        "--puzzle",
        type=str,
        default="hanoi",
        choices=["hanoi", "lights_out"],
        help="パズル種を選択（デフォルト: hanoi）",
    )
    args = parser.parse_args()
    if args.puzzle != "lights_out" and args.seed is not None:
        parser.error("--seed is only supported with --puzzle lights_out")
    if args.puzzle == "lights_out" and args.n_shot > 0:
        print(
            f"[WARN] Lights Out uses n_shot=0 by SPEC-2026-06-06-003 decision #5; "
            f"overriding --n-shot {args.n_shot} to 0.",
            file=sys.stderr,
        )
        args.n_shot = 0
    return args


def _build_early_stop_cfg(args) -> Optional[EarlyStopConfig]:
    """CLI 引数から EarlyStopConfig を構築する。--no-early-stop 時は None を返す。"""
    if args.no_early_stop:
        return None
    think_ratio = (
        args.es_think_ratio if args.es_think_ratio is not None
        else calc_think_budget_ratio(args.N)
    )
    return EarlyStopConfig(
        think_budget_ratio=think_ratio,
        max_move_multiplier=args.es_move_mult,
        loop_window=args.es_loop_window,
        loop_min_count=args.es_loop_count,
        enable_move_loop=not args.no_loop_detection,
    )


def _resolve_output_paths(args) -> tuple[Optional[Path], Optional[Path]]:
    """出力ディレクトリと summary.json パスを解決する。

    Returns:
        (output_dir, summary_path): いずれも保存不要なら None。
    """
    output_dir: Optional[Path] = None
    if not args.no_save_hidden:
        output_dir = (
            Path(args.output_dir) if args.output_dir
            else Path(f"results/{args.puzzle}/{model_id_to_slug(args.model_id)}/N{args.N}")
        )
    summary_path = (
        Path(args.output) if args.output
        else (output_dir / "summary.json" if output_dir else None)
    )
    return output_dir, summary_path


def _write_meta_json(summary_path: Optional[Path], args) -> None:
    """meta.json を summary.json より先に書き出す。

    実験途中でクラッシュしても sync.sh が "waiting" として検知できる。
    summary_path が None の場合は何もしない。
    """
    if summary_path is None:
        return
    meta_dir = summary_path.parent
    meta_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "environment": args.puzzle,
        "model":       args.model_id,
        "N":           args.N,
        "temperature": args.temperature,
        "sweep_type":  args.sweep_type,
    }
    meta_path = meta_dir / "meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"メタデータを保存しました: {meta_path}")


def main() -> None:
    args = parse_args()

    puzzle_factories = {
        "hanoi": TowerOfHanoiEnv,
        "lights_out": LightsOutEnv,
    }
    env_factory = puzzle_factories[args.puzzle]
    env = (
        env_factory(args.N, seed=args.seed)
        if args.puzzle == "lights_out"
        else env_factory(args.N)
    )

    trials         = args.trials if args.trials is not None else calc_default_trials(args.N)
    early_stop_cfg = _build_early_stop_cfg(args)
    output_dir, summary_path = _resolve_output_paths(args)
    _write_meta_json(summary_path, args)

    # モデルプロファイル解決（think 起動方式の自動選択）
    profile = resolve_model_profile(args.model_id)
    print(f"[INFO] ModelProfile: think_mode={profile.think_mode}")

    # モデルロード
    model, tokenizer = load_model_and_tokenizer(args.model_id, args.device)

    # モデルの層数から CAPTURE_LAYERS を動的に決定する
    capture_layers = make_capture_layers(model.config.num_hidden_layers)
    print(f"[INFO] capture_layers: {capture_layers}")

    results = run_experiment_hf(
        env=env,
        N=args.N,
        trials=trials,
        model_id=args.model_id,
        model=model,
        tokenizer=tokenizer,
        num_predict=args.num_predict,
        early_stop_cfg=early_stop_cfg,
        output_dir=output_dir,
        temperature=args.temperature,
        repetition_penalty=args.repetition_penalty,
        n_shot=args.n_shot,
        profile=profile,
        capture_layers=capture_layers,
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
