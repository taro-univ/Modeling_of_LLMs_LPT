"""
test_model_architecture.py — 新モデル追加時のアーキテクチャ検証スクリプト

run_local.py が複数モデルに対応できているかを系統的に確認する。

使用例:
  # GPU 不要テストのみ（モデルダウンロード前の事前確認）
  PYTHONPATH=/app python runners/test_model_architecture.py \\
      --model-id deepseek-ai/DeepSeek-R1-Distill-Qwen-14B --no-gpu-tests

  # 全テスト実行
  PYTHONPATH=/app python runners/test_model_architecture.py \\
      --model-id Qwen/Qwen3-8B
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

import numpy as np
import torch
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

from envs.hanoi_env import TowerOfHanoiEnv
from runners.run import calc_num_predict
from runners.run_local import (
    GenerationResult,
    ModelProfile,
    _MOVE_RE_WITH_DISK,
    generate_with_hidden_states,
    load_model_and_tokenizer,
    make_capture_layers,
    resolve_model_profile,
    run_experiment_hf,
)

# ===========================================================================
# 型定義
# ===========================================================================

# (test_id, status, message)
# status は "PASS" | "WARN" | "FAIL" の 3 値
TestResult = tuple[str, str, str]


# ===========================================================================
# 結果生成ヘルパー
# ===========================================================================

def ok(test_id: str, message: str) -> TestResult:
    return (test_id, "PASS", message)


def warn(test_id: str, message: str) -> TestResult:
    return (test_id, "WARN", message)


def fail(test_id: str, message: str) -> TestResult:
    return (test_id, "FAIL", message)


# ===========================================================================
# 表示ヘルパー
# ===========================================================================

_STATUS_SYMBOL = {"PASS": "✓", "WARN": "△", "FAIL": "✗"}


def print_group(group_name: str, results: list[TestResult]) -> None:
    """テストグループの結果を整形して標準出力へ表示する。"""
    statuses = [s for _, s, _ in results]
    if "FAIL" in statuses:
        group_status = "FAIL"
    elif "WARN" in statuses:
        group_status = "WARN"
    else:
        group_status = "PASS"

    print(f"\n[{group_name}] --- {group_status} ---")
    for test_id, status, message in results:
        sym = _STATUS_SYMBOL.get(status, "?")
        print(f"  {sym} {test_id} {status:4s}  {message}")


def print_summary(all_results: list[TestResult]) -> None:
    """全テストの最終集計を表示する。終了コードを返す（FAIL あり: 1, なし: 0）。"""
    print(f"\n{'='*60}")
    print("  TEST SUMMARY")
    print(f"{'='*60}")

    fail_count = sum(1 for _, s, _ in all_results if s == "FAIL")
    warn_count = sum(1 for _, s, _ in all_results if s == "WARN")
    pass_count = sum(1 for _, s, _ in all_results if s == "PASS")

    print(f"  PASS: {pass_count}  WARN: {warn_count}  FAIL: {fail_count}")

    if fail_count:
        print("\n  [FAIL 一覧]")
        for test_id, status, message in all_results:
            if status == "FAIL":
                print(f"    {test_id}: {message}")

    overall = "FAIL" if fail_count else ("WARN" if warn_count else "PASS")
    print(f"\n  Overall: {overall}")
    print(f"{'='*60}\n")

    return 1 if fail_count else 0


# ===========================================================================
# 引数パース
# ===========================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="新モデルのアーキテクチャ・出力フォーマット・hidden state を検証する"
    )
    parser.add_argument(
        "--model-id", type=str,
        default="deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
        help="HuggingFace モデル ID",
    )
    parser.add_argument(
        "--no-gpu-tests", action="store_true",
        help="T0 のみ実行する（モデルダウンロード前の事前確認用）",
    )
    parser.add_argument(
        "--device", type=str, default="cuda:0",
        help="デバイス指定 (default: cuda:0)",
    )
    return parser.parse_args()


# ===========================================================================
# T0: 設定確認（GPU 不要）
# ===========================================================================

def run_t0(
    model_id: str,
) -> tuple[Optional[AutoConfig], Optional[AutoTokenizer], list[TestResult]]:
    """
    AutoConfig と AutoTokenizer のみを使った事前確認。

    Returns:
        (config, tokenizer, results)
        ロードに失敗した場合は config / tokenizer が None になる。
    """
    print(f"\n[T0] 設定確認: {model_id}")
    results: list[TestResult] = []
    config = None
    tokenizer = None

    # --- T0-1 / T0-2: num_hidden_layers, hidden_size の取得 ---
    try:
        config = AutoConfig.from_pretrained(model_id)
        num_layers = config.num_hidden_layers
        hidden_size = config.hidden_size
        results.append(ok("T0-1", f"num_hidden_layers = {num_layers}"))
        results.append(ok("T0-2", f"hidden_size       = {hidden_size}"))
    except Exception as e:
        results.append(fail("T0-1", f"AutoConfig のロード失敗: {e}"))
        results.append(fail("T0-2", "AutoConfig のロード失敗のためスキップ"))
        # config なしでは T0-3〜T0-5 も続行不能
        return config, tokenizer, results

    # --- T0-3〜T0-5: tokenizer のロードとチャットテンプレート確認 ---
    try:
        tokenizer = AutoTokenizer.from_pretrained(model_id)
    except Exception as e:
        results.append(fail("T0-3", f"AutoTokenizer のロード失敗: {e}"))
        results.append(fail("T0-4", "tokenizer のロード失敗のためスキップ"))
        results.append(fail("T0-5", "tokenizer のロード失敗のためスキップ"))
        return config, tokenizer, results

    # T0-3: chat_template の存在確認
    if tokenizer.chat_template is not None:
        results.append(ok("T0-3", "chat_template 存在"))
    else:
        results.append(fail("T0-3", "chat_template が None — プロンプト設計が必要"))

    # T0-4〜T0-5 で使うテスト用メッセージ（system + user の最小構成）
    _test_messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user",   "content": "Hello."},
    ]

    # T0-4: system ロールを含むメッセージで apply_chat_template が通るか
    try:
        tokenizer.apply_chat_template(
            _test_messages, tokenize=False, add_generation_prompt=True
        )
        results.append(ok("T0-4", "system ロール OK"))
    except Exception as e:
        results.append(fail("T0-4", f"system ロール拒否: {e}"))

    # T0-5: enable_thinking=True が通るか
    # TypeError → WARN（think_mode="prefill" を使うべき示唆）
    # その他の例外 → FAIL
    try:
        tokenizer.apply_chat_template(
            _test_messages, tokenize=False, add_generation_prompt=True,
            enable_thinking=True,
        )
        results.append(ok("T0-5", "enable_thinking=True 対応"))
    except TypeError:
        results.append(warn("T0-5", 'enable_thinking 非対応 → think_mode="prefill" を使用'))
    except Exception as e:
        results.append(fail("T0-5", f"apply_chat_template で予期しないエラー: {e}"))

    return config, tokenizer, results


# ===========================================================================
# T1: モデルロードと CAPTURE_LAYERS 検証
# ===========================================================================

def run_t1(
    model_id: str,
    device: str,
    config_t0: Optional[AutoConfig],
) -> tuple[
    Optional[AutoModelForCausalLM],
    Optional[AutoTokenizer],
    dict[str, int],
    list[TestResult],
]:
    """
    NF4 量子化でモデルをロードし、CAPTURE_LAYERS の有効性と VRAM 消費を確認する。

    Args:
        config_t0: T0 で取得した AutoConfig（T1-2 の照合に使用）。None の場合は照合をスキップ。

    Returns:
        (model, tokenizer, capture_layers, results)
        ロードに失敗した場合は model / tokenizer が None、capture_layers が {} になる。
    """
    print(f"\n[T1] モデルロード: {model_id}  device={device}")
    results: list[TestResult] = []

    # T1-1: NF4 量子化ロード
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    try:
        model, tokenizer = load_model_and_tokenizer(model_id, device)
    except Exception as e:
        results.append(fail("T1-1", f"モデルロード失敗: {e}"))
        results.append(fail("T1-2", "ロード失敗のためスキップ"))
        results.append(fail("T1-3", "ロード失敗のためスキップ"))
        results.append(fail("T1-4", "ロード失敗のためスキップ"))
        return None, None, {}, results

    results.append(ok("T1-1", "NF4 量子化ロード完了"))

    # T1-2: hidden_size が T0 実測値と一致するか
    actual_hidden = model.config.hidden_size
    actual_layers = model.config.num_hidden_layers
    if config_t0 is not None:
        expected_hidden = config_t0.hidden_size
        if actual_hidden == expected_hidden:
            results.append(ok("T1-2", f"hidden_size = {actual_hidden}（T0 と一致）"))
        else:
            results.append(fail(
                "T1-2",
                f"hidden_size 不一致: T0={expected_hidden}, model={actual_hidden}",
            ))
    else:
        results.append(ok("T1-2", f"hidden_size = {actual_hidden}（T0 config なしのため実測のみ）"))

    # T1-3: make_capture_layers の各インデックスが hidden_states タプル長の範囲内か
    # hidden_states は (embedding + num_hidden_layers 個の transformer) = num_hidden_layers+1 要素
    # 有効な負インデックスは -1 〜 -(num_hidden_layers+1)
    capture_layers = make_capture_layers(actual_layers)
    tuple_len = actual_layers + 1  # embedding 込み
    invalid = {
        k: idx for k, idx in capture_layers.items() if abs(idx) > tuple_len
    }
    if not invalid:
        results.append(ok(
            "T1-3",
            f"全インデックスが範囲内 (tuple_len={tuple_len}): {capture_layers}",
        ))
    else:
        results.append(fail(
            "T1-3",
            f"範囲外インデックスあり (tuple_len={tuple_len}): {invalid}",
        ))

    # T1-4: VRAM 消費量の確認
    if torch.cuda.is_available():
        vram_gb = torch.cuda.memory_allocated(device) / 1e9
        if vram_gb < 12.0:
            results.append(ok("T1-4", f"VRAM = {vram_gb:.2f} GB（< 12 GB）"))
        elif vram_gb < 14.0:
            results.append(warn("T1-4", f"VRAM = {vram_gb:.2f} GB（12〜14 GB）— num_predict を下げることを検討"))
        else:
            results.append(fail("T1-4", f"VRAM = {vram_gb:.2f} GB（>= 14 GB）— 実験実行前に対処が必要"))
    else:
        results.append(warn("T1-4", "CUDA 不使用のため VRAM 計測をスキップ"))

    return model, tokenizer, capture_layers, results


# ===========================================================================
# T2–T4 共有: 1 試行 N=2 の生成
# ===========================================================================

def _run_shared_trial(
    model: AutoModelForCausalLM,
    tokenizer: AutoTokenizer,
    profile: ModelProfile,
    capture_layers: dict[str, int],
    N: int = 2,
    temperature: float = 0.6,
    n_shot: int = 1,
) -> GenerationResult:
    """T2・T3・T4 が共有する 1 試行の生成を実行して返す。

    early_stop_cfg=None かつ disable_goal_stop=True で全トークンを生成し、
    think タグの出現を確実に確認できるようにする。
    """
    env = TowerOfHanoiEnv(N=N)
    return generate_with_hidden_states(
        model=model,
        tokenizer=tokenizer,
        prompt=env.get_prompt(),
        num_predict=calc_num_predict(N),
        min_moves=env.min_moves,
        env=env,
        early_stop_cfg=None,
        temperature=temperature,
        repetition_penalty=1.1,
        n_shot=n_shot,
        profile=profile,
        capture_layers=capture_layers,
        disable_goal_stop=True,
    )


# ===========================================================================
# T2: thinking 起動検証
# ===========================================================================

def run_t2(
    gen_result: GenerationResult,
    profile: ModelProfile,
) -> list[TestResult]:
    """think タグの出現・正常クローズ・推論トークン数・二重付与を確認する。"""
    print("\n[T2] thinking 起動検証")
    results: list[TestResult] = []

    # prefill モードでは <think> はプロンプト側にあるため、確認用テキストに補う
    if profile.think_mode == "prefill":
        check_text = profile.think_open_tag + "\n" + gen_result.text
    else:
        check_text = gen_result.text

    # T2-1: think_open_tag が（補完後の）テキストに存在するか
    if profile.think_open_tag in check_text:
        results.append(ok("T2-1", f"{profile.think_open_tag} を確認"))
    else:
        results.append(fail("T2-1", f"{profile.think_open_tag} が出力に現れない"))

    # T2-2: think_close_tag が存在するか（正常クローズ）
    if profile.think_close_tag in check_text:
        results.append(ok("T2-2", f"{profile.think_close_tag} を確認（正常クローズ）"))
    else:
        results.append(fail("T2-2", f"{profile.think_close_tag} が出力に現れない — thinking が未クローズ"))

    # T2-3: reasoning_tokens が 0 より大きいか
    rt = gen_result.reasoning_tokens
    if rt > 0:
        results.append(ok("T2-3", f"reasoning_tokens = {rt}"))
    else:
        results.append(fail("T2-3", "reasoning_tokens = 0 — think タグの書式が期待と異なる可能性"))

    # T2-4: プリフィルの二重付与チェック（モード別に判定基準が異なる）
    stripped = gen_result.text.lstrip()
    if profile.think_mode == "prefill":
        # prefill 済みの think_open_tag を model が再出力していないか確認
        if stripped.startswith(profile.think_open_tag):
            results.append(fail(
                "T2-4",
                f"二重プリフィルの疑い: 生成テキストの先頭に {profile.think_open_tag} が出現",
            ))
        else:
            results.append(ok("T2-4", "プリフィル二重付与なし"))
    elif profile.think_mode == "chat_template":
        # モデルが think_open_tag から出力を開始しているか確認
        if stripped.startswith(profile.think_open_tag):
            results.append(ok("T2-4", f"出力が {profile.think_open_tag} から開始"))
        else:
            results.append(warn(
                "T2-4",
                f"出力が {profile.think_open_tag} から始まっていない（先頭: {stripped[:40]!r}）",
            ))
    else:
        results.append(ok("T2-4", "think_mode=none のためスキップ"))

    return results


# ===========================================================================
# T3: 出力フォーマット検証
# ===========================================================================

def run_t3(
    gen_result: GenerationResult,
    env: TowerOfHanoiEnv,
) -> list[TestResult]:
    """Move 抽出の件数・自己ループ・ディスク番号範囲・パーサ整合性を確認する。"""
    print("\n[T3] 出力フォーマット検証")
    results: list[TestResult] = []

    # _MOVE_RE_WITH_DISK は (disk, src, dst) の文字列タプルを返す
    matches: list[tuple[str, str, str]] = _MOVE_RE_WITH_DISK.findall(gen_result.text)

    # T3-1: 1 件以上マッチするか
    if len(matches) >= 1:
        results.append(ok("T3-1", f"{len(matches)} 手を抽出"))
    else:
        results.append(fail("T3-1", "Move が 1 件もマッチしない"))
        # 手が 0 件では T3-2〜T3-3 は検証不能
        results.append(fail("T3-2", "Move なしのためスキップ"))
        results.append(fail("T3-3", "Move なしのためスキップ"))
        # T3-4 はパーサ整合性なので 0 件同士でも確認できる
        extracted = env.extract_moves_from_text(gen_result.text)
        if len(matches) == len(extracted):
            results.append(ok("T3-4", f"件数一致（両方 0 件）"))
        else:
            results.append(fail("T3-4", f"件数不一致: _MOVE_RE_WITH_DISK={len(matches)}, extract_moves={len(extracted)}"))
        return results

    # T3-2: 全手で src != dst（自己ループなし）
    self_loops = [(d, s, t) for d, s, t in matches if s.upper() == t.upper()]
    if not self_loops:
        results.append(ok("T3-2", "自己ループなし（全手で src ≠ dst）"))
    else:
        results.append(fail(
            "T3-2",
            f"自己ループあり: {[f'Move {d} {s}→{t}' for d, s, t in self_loops]}",
        ))

    # T3-3: 全手で 1 <= disk <= N
    out_of_range = [
        (d, s, t) for d, s, t in matches if not (1 <= int(d) <= env.N)
    ]
    if not out_of_range:
        results.append(ok("T3-3", f"全手のディスク番号が範囲内（1〜{env.N}）"))
    else:
        results.append(fail(
            "T3-3",
            f"ディスク番号が範囲外（N={env.N}）: {[f'disk={d}' for d, _, _ in out_of_range]}",
        ))

    # T3-4: _MOVE_RE_WITH_DISK と env.extract_moves_from_text の件数一致
    extracted = env.extract_moves_from_text(gen_result.text)
    if len(matches) == len(extracted):
        results.append(ok("T3-4", f"パーサ件数一致（{len(matches)} 件）"))
    else:
        results.append(fail(
            "T3-4",
            f"件数不一致: _MOVE_RE_WITH_DISK={len(matches)}, extract_moves={len(extracted)}",
        ))

    return results


# ===========================================================================
# T4: hidden state 抽出の形状・健全性検証
# ===========================================================================

def run_t4(
    gen_result: GenerationResult,
    hidden_size: int,
    capture_layers: dict[str, int],
) -> list[TestResult]:
    """hidden_states の構造・shape・有限性・move との整合性を確認する。"""
    print("\n[T4] hidden state 検証")
    results: list[TestResult] = []

    num_moves = int(gen_result.move_steps.shape[0])

    # T4-1: hidden_states のキーが capture_layers と一致するか
    actual_keys = set(gen_result.hidden_states.keys())
    expected_keys = set(capture_layers.keys())
    if actual_keys == expected_keys:
        results.append(ok("T4-1", f"キー一致: {sorted(actual_keys)}"))
    else:
        missing = expected_keys - actual_keys
        extra   = actual_keys - expected_keys
        results.append(fail(
            "T4-1",
            f"キー不一致 — 欠損: {missing}  余分: {extra}",
        ))

    # T4-2: 各配列の shape が (num_moves, hidden_size) か
    shape_errors: list[str] = []
    for key, arr in gen_result.hidden_states.items():
        expected_shape = (num_moves, hidden_size)
        if arr.shape != expected_shape:
            shape_errors.append(f"{key}: got {arr.shape}, expected {expected_shape}")
    if not shape_errors:
        results.append(ok("T4-2", f"全配列の shape = ({num_moves}, {hidden_size})"))
    else:
        results.append(fail("T4-2", "shape 不一致: " + "; ".join(shape_errors)))

    # T4-3: NaN / Inf が含まれないか
    nan_inf_keys: list[str] = []
    for key, arr in gen_result.hidden_states.items():
        if arr.size > 0 and not np.isfinite(arr).all():
            nan_inf_keys.append(key)
    if not nan_inf_keys:
        results.append(ok("T4-3", "全配列に NaN / Inf なし"))
    else:
        results.append(fail("T4-3", f"NaN / Inf を含む層: {nan_inf_keys}"))

    # T4-4: move_texts と move_steps の長さが num_moves と一致するか
    n_texts = len(gen_result.move_texts)
    n_steps = int(gen_result.move_steps.shape[0])
    if n_texts == n_steps == num_moves:
        results.append(ok("T4-4", f"move_texts / move_steps / num_moves = {num_moves} で一致"))
    else:
        results.append(fail(
            "T4-4",
            f"長さ不一致 — move_texts={n_texts}, move_steps={n_steps}, num_moves={num_moves}",
        ))

    # T4-5: fallback パスが誤って記録されていないか
    # N=2 では必ず 1 手以上出力されるはずなので __fallback__ は想定外
    if "__fallback__" not in gen_result.move_texts:
        results.append(ok("T4-5", "__fallback__ なし"))
    else:
        fallback_count = gen_result.move_texts.count("__fallback__")
        results.append(fail(
            "T4-5",
            f"__fallback__ が {fallback_count} 件記録されている（Move が 1 手も出なかった可能性）",
        ))

    return results


# ===========================================================================
# T5: 機能的サニティチェック
# ===========================================================================

# T5-3 で確認する必須フィールド（DB 同期の前提条件）
_T5_REQUIRED_FIELDS = {"accuracy", "early_stop", "num_moves", "temperature", "N"}


def run_t5(
    model_id: str,
    model: AutoModelForCausalLM,
    tokenizer: AutoTokenizer,
    profile: ModelProfile,
    capture_layers: dict[str, int],
) -> list[TestResult]:
    """N=2・3 試行・T=0.2 で定性的な正解傾向と結果フィールドの整合性を確認する。

    数値的な閾値ではなく傾向の確認であり、確率的ゆらぎを考慮した緩い基準とする。
    """
    print("\n[T5] 機能的サニティチェック（N=2, trials=3, T=0.2）")
    results: list[TestResult] = []

    try:
        trial_results = run_experiment_hf(
            N=2,
            trials=3,
            model_id=model_id,
            model=model,
            tokenizer=tokenizer,
            temperature=0.2,
            n_shot=1,
            output_dir=None,
            profile=profile,
            capture_layers=capture_layers,
        )
    except Exception as e:
        results.append(fail("T5-1", f"run_experiment_hf で例外: {e}"))
        results.append(fail("T5-2", "run_experiment_hf 失敗のためスキップ"))
        results.append(fail("T5-3", "run_experiment_hf 失敗のためスキップ"))
        return results

    n_trials = len(trial_results)

    # T5-1: 3 試行中 1 回以上正解するか
    accuracy_sum = sum(r["accuracy"] for r in trial_results)
    if accuracy_sum >= 1:
        results.append(ok("T5-1", f"正解 {accuracy_sum}/{n_trials} 試行"))
    else:
        results.append(fail("T5-1", f"正解 0/{n_trials} 試行 — T=0.2 で N=2 が全敗は設定に問題がある可能性"))

    # T5-2: early_stop が goal_reached または None の件数が 2/3 以上か
    ordered_count = sum(
        1 for r in trial_results
        if r.get("early_stop") in ("goal_reached", None)
    )
    if ordered_count >= 2:
        results.append(ok(
            "T5-2",
            f"goal_reached / None = {ordered_count}/{n_trials} 試行",
        ))
    else:
        loop_pm_count = n_trials - ordered_count
        results.append(fail(
            "T5-2",
            f"ループ / no_move が多発: goal_reached/None={ordered_count}/{n_trials},"
            f" loop/no_move={loop_pm_count}/{n_trials}",
        ))

    # T5-3: 必須フィールドが全結果辞書に存在するか
    missing_per_trial: list[str] = []
    for r in trial_results:
        missing = _T5_REQUIRED_FIELDS - r.keys()
        if missing:
            missing_per_trial.append(f"trial {r.get('trial', '?')}: {missing}")
    if not missing_per_trial:
        results.append(ok(
            "T5-3",
            f"必須フィールド {sorted(_T5_REQUIRED_FIELDS)} が全 {n_trials} 試行に存在",
        ))
    else:
        results.append(fail(
            "T5-3",
            "フィールド欠損あり: " + "; ".join(missing_per_trial),
        ))

    return results


# ===========================================================================
# エントリポイント
# ===========================================================================

def main() -> None:
    args = parse_args()
    model_id = args.model_id
    all_results: list[TestResult] = []

    profile = resolve_model_profile(model_id)
    print(f"[INFO] model_id   = {model_id}")
    print(f"[INFO] think_mode = {profile.think_mode}")

    # -----------------------------------------------------------------------
    # T0: 設定確認（GPU 不要）
    # -----------------------------------------------------------------------
    config, _, t0_results = run_t0(model_id)
    print_group("T0", t0_results)
    all_results.extend(t0_results)

    if args.no_gpu_tests:
        sys.exit(print_summary(all_results))

    # CUDA が使えない場合は T1 以降を実行しない
    if not torch.cuda.is_available():
        all_results.append(warn("GPU", "CUDA が使用できないため T1〜T5 をスキップ"))
        sys.exit(print_summary(all_results))

    # -----------------------------------------------------------------------
    # T1: モデルロードと CAPTURE_LAYERS 検証
    # -----------------------------------------------------------------------
    model, tokenizer, capture_layers, t1_results = run_t1(model_id, args.device, config)
    print_group("T1", t1_results)
    all_results.extend(t1_results)

    if any(s == "FAIL" for _, s, _ in t1_results):
        print("\n[SKIP] T1 に FAIL があるため T2〜T5 をスキップします")
        sys.exit(print_summary(all_results))

    # -----------------------------------------------------------------------
    # T2〜T4 共有: 1 試行 N=2 の生成
    # -----------------------------------------------------------------------
    print("\n[INFO] T2〜T4 用の共有試行を生成中（N=2, T=0.6, 1 試行）…")
    env_n2 = TowerOfHanoiEnv(N=2)
    try:
        gen_result = _run_shared_trial(
            model=model,
            tokenizer=tokenizer,
            profile=profile,
            capture_layers=capture_layers,
        )
    except Exception as e:
        msg = f"共有試行の生成で例外: {e}"
        for tid in ("T2", "T3", "T4"):
            all_results.append(fail(f"{tid}-*", msg))
        print(f"\n[SKIP] {msg} — T2〜T4 をスキップ")
        # T5 は独立した run_experiment_hf を使うため続行する
        gen_result = None

    # -----------------------------------------------------------------------
    # T2: thinking 起動検証
    # -----------------------------------------------------------------------
    if gen_result is not None:
        t2_results = run_t2(gen_result, profile)
        print_group("T2", t2_results)
        all_results.extend(t2_results)

        # T3: 出力フォーマット検証
        t3_results = run_t3(gen_result, env_n2)
        print_group("T3", t3_results)
        all_results.extend(t3_results)

        # T4: hidden state 検証
        t4_results = run_t4(gen_result, model.config.hidden_size, capture_layers)
        print_group("T4", t4_results)
        all_results.extend(t4_results)

    # -----------------------------------------------------------------------
    # T5: 機能的サニティチェック
    # -----------------------------------------------------------------------
    t5_results = run_t5(model_id, model, tokenizer, profile, capture_layers)
    print_group("T5", t5_results)
    all_results.extend(t5_results)

    # -----------------------------------------------------------------------
    # 最終集計
    # -----------------------------------------------------------------------
    sys.exit(print_summary(all_results))


if __name__ == "__main__":
    main()
