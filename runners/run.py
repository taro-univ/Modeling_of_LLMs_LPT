"""
run.py — ハノイの塔 推論崩壊検知 最小実験スクリプト

指標:
  - accuracy       : ゴール到達の成否 (0 or 1)
  - total_tokens   : Ollama が生成したトークン数（出力全体）
  - reasoning_tokens: <think>...</think> 内のトークン数（近似）
  - early_stop     : 早期終了の理由 (None = 最後まで生成)

使用例:
  python run.py --N 3
  python run.py --N 5 --trials 5 --model deepseek-r1:14b
  python run.py --N 5 --no-early-stop   # 早期終了を無効化
"""

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

import requests

from envs.hanoi_env import TowerOfHanoiEnv


# ===========================================================================
# トークン数計算
# ===========================================================================

def calc_num_predict(N: int) -> int:
    """
    円盤数 N に応じた最大出力トークン数を返す。

    早期終了が機能する場合、実際の生成トークンはこれより大幅に少ない。

    KVキャッシュ見積もり（DeepSeek-R1 14B, fp16, GQA 8ヘッド）:
      num_ctx × 40層 × 2 × 8 × 128 × 2 bytes
      N=5:  4096 tokens → ~0.68 GB  (モデル重み8.5 GB + KV ≈  9.2 GB)
      N=6:  8192 tokens → ~1.35 GB  (モデル重み8.5 GB + KV ≈  9.9 GB)
      N=7: 16384 tokens → ~2.70 GB  (モデル重み8.5 GB + KV ≈ 11.2 GB ← ギリギリ)
      N=8: 16384 tokens → ~2.70 GB  (N=8 は early-stop 頼りで同じ枠を使用)

    Parameters
    ----------
    N : int
        円盤の枚数。

    Returns
    -------
    int
        num_predict (最大出力トークン数)。
    """
    if N <= 5:
        return 4096
    elif N == 6:
        return 8192
    else:  # N >= 7: VRAM上限を考慮し 16384 に固定
        return 16384


def calc_num_ctx(N: int) -> int:
    """コンテキストウィンドウ = num_predict + プロンプト余裕 512。"""
    return calc_num_predict(N) + 512


def calc_default_trials(N: int) -> int:
    """
    円盤数 N に応じた推奨試行回数を返す。

    N が大きくなるほど 1 試行あたりのコストが増大するため、
    統計的な有意性を保ちつつ総実験時間を抑える。

    Parameters
    ----------
    N : int
        円盤の枚数。

    Returns
    -------
    int
        推奨試行回数。
    """
    table: dict[int, int] = {
        5: 20,
        6: 15,
        7: 10,
    }
    if N <= 4:
        return 25
    return table.get(N, 5)  # N>=8 は探索的に 5 試行


def calc_think_budget_ratio(N: int) -> float:
    """
    円盤数 N に応じた think_budget_ratio を返す。

    N が大きくなるほど thinking が token 予算を圧迫しやすいため、
    より早い段階で打ち切る。

    Parameters
    ----------
    N : int
        円盤の枚数。

    Returns
    -------
    float
        <think> 内トークンが num_predict のこの割合を超えたら打ち切る閾値。
    """
    if N <= 5:
        return 0.65
    elif N == 6:
        return 0.55
    elif N == 7:
        return 0.45
    else:  # N >= 8
        return 0.35


# ===========================================================================
# 早期終了設定
# ===========================================================================

@dataclass
class EarlyStopConfig:
    """
    早期終了アルゴリズムの設定。

    Attributes
    ----------
    think_budget_ratio : float
        <think> 内推定トークンが num_predict のこの割合を超えたら打ち切る。
        Algorithm A: Think Budget。
        Token Exhaustion（<think>が閉じないまま全トークン消費）を防ぐ。

    no_move_ratio : float
        累積テキストが num_predict のこの割合を超えても手が1つも抽出されない場合に打ち切る。
        Algorithm D: No Move Catch-All。
        <think>タグを使わずプレーンテキストで応答し続けるケースを補足する。

    max_move_multiplier : float
        抽出済み手数が最短手数のこの倍数を超えたら打ち切る。
        Algorithm B: Move Count Ceiling。
        過剰な手数出力（ループの兆候）を早期検出する。

    loop_window : int
        往復手ループ検出に使う直近の手数ウィンドウ。
        Algorithm C: Reverse Move Loop。

    loop_min_count : int
        loop_window 内で同一手が何回出現したら打ち切るか。
    """
    think_budget_ratio: float = 0.70
    no_move_ratio: float = 0.50
    max_move_multiplier: float = 1.5
    loop_window: int = 6
    loop_min_count: int = 2

    # 各アルゴリズムの有効化フラグ
    enable_think_budget: bool = True
    enable_no_move: bool = True
    enable_move_ceiling: bool = True
    enable_move_loop: bool = True


# ===========================================================================
# 早期終了チェック（ストリーミング中に毎チャンク呼び出す）
# ===========================================================================

_MOVE_RE = re.compile(
    r'Move\s+\d+\s+from\s+([ABC])\s+to\s+([ABC])',
    re.IGNORECASE,
)


def check_early_stop(
    text: str,
    num_predict: int,
    min_moves: int,
    cfg: EarlyStopConfig,
) -> Optional[str]:
    """
    ストリーミング中の累積テキストに対して早期終了条件を評価する。

    Parameters
    ----------
    text : str
        現時点までの累積出力テキスト。
    num_predict : int
        今回の試行の最大出力トークン数。
    min_moves : int
        この N に対する最短手数（2^N - 1）。
    cfg : EarlyStopConfig
        早期終了パラメータ。

    Returns
    -------
    str or None
        打ち切り理由のラベル。条件に引っかからなければ None。
        - "think_budget"      : Algorithm A
        - "no_move_catchall"  : Algorithm D
        - "move_ceiling"      : Algorithm B
        - "move_loop_repeat"  : Algorithm C（同一手の繰り返し）
        - "move_loop_reverse" : Algorithm C（往復手）
    """
    # ------------------------------------------------------------------
    # Algorithm A: Think Budget
    # ------------------------------------------------------------------
    if cfg.enable_think_budget:
        think_open = re.search(r'<think>(.*)', text, re.DOTALL | re.IGNORECASE)
        think_closed = bool(re.search(r'</think>', text, re.IGNORECASE))
        if think_open and not think_closed:
            # 文字数 / 3.5 でトークン数を近似（DeepSeek-R1 系の経験則）
            think_chars = len(think_open.group(1))
            think_tokens_est = think_chars / 3.5
            if think_tokens_est > num_predict * cfg.think_budget_ratio:
                return "think_budget"

    # ------------------------------------------------------------------
    # Algorithm D: No Move Catch-All
    # <think>タグなしのプレーンテキスト応答など、A/B/C が不発になる
    # ケースを補足する。累積テキストが no_move_ratio を超えても
    # 手が1つも抽出されていなければ打ち切る。
    # ------------------------------------------------------------------
    if cfg.enable_no_move:
        text_tokens_est = len(text) / 3.5
        if text_tokens_est > num_predict * cfg.no_move_ratio:
            moves_so_far = _MOVE_RE.findall(text)
            if len(moves_so_far) == 0:
                return "no_move_catchall"

    # ------------------------------------------------------------------
    # Algorithm B & C: Move フォーマットを逐次抽出
    # ------------------------------------------------------------------
    moves = _MOVE_RE.findall(text)  # list of (src, dst)
    n_moves = len(moves)

    # Algorithm B: Move Count Ceiling
    if cfg.enable_move_ceiling:
        if n_moves > min_moves * cfg.max_move_multiplier:
            return "move_ceiling"

    # Algorithm C: Move Loop Detection
    if cfg.enable_move_loop and n_moves >= cfg.loop_window:
        recent = moves[-cfg.loop_window:]

        # C-1: 同一手の繰り返し（同じ src→dst が loop_min_count 回以上）
        for mv in set(recent):
            if recent.count(mv) >= cfg.loop_min_count:
                return "move_loop_repeat"

        # C-2: 往復手（A→B の直後に B→A）
        for i in range(len(recent) - 1):
            src1, dst1 = recent[i]
            src2, dst2 = recent[i + 1]
            if src1 == dst2 and dst1 == src2:
                return "move_loop_reverse"

    return None


# ===========================================================================
# Ollama クライアント（ストリーミング対応）
# ===========================================================================

def query_ollama(
    prompt: str,
    model: str,
    base_url: str,
    num_predict: int,
    min_moves: int,
    early_stop_cfg: Optional[EarlyStopConfig] = None,
    timeout: int = 600,
) -> tuple[str, int, int, Optional[str]]:
    """
    Ollama の /api/generate をストリーミングモードで呼び出す。

    早期終了条件を満たした時点でストリームを切断し、
    それまでの累積テキストを返す。

    Parameters
    ----------
    prompt : str
        LLM に渡すプロンプト。
    model : str
        Ollama モデル名（例: "deepseek-r1:14b"）。
    base_url : str
        Ollama サーバの URL。
    num_predict : int
        最大出力トークン数。
    min_moves : int
        この N に対する最短手数（早期終了の閾値計算に使用）。
    early_stop_cfg : EarlyStopConfig or None
        None の場合は早期終了を無効化（従来の非ストリーミング動作と同等）。
    timeout : int
        リクエストタイムアウト秒数。

    Returns
    -------
    tuple[str, int, int, str | None]
        (response_text, total_tokens, reasoning_tokens, early_stop_reason)
    """
    url = f"{base_url.rstrip('/')}/api/generate"
    body = {
        "model":  model,
        "prompt": prompt,
        "stream": True,
        "options": {
            "num_predict": num_predict,
            "num_ctx":     num_predict + 512,
        },
    }

    accumulated   = ""
    total_tokens  = 0
    stop_reason: Optional[str] = None

    try:
        with requests.post(url, json=body, stream=True, timeout=timeout) as resp:
            resp.raise_for_status()
            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                chunk = json.loads(raw_line)
                accumulated  += chunk.get("response", "")
                total_tokens  = chunk.get("eval_count", total_tokens)

                if chunk.get("done"):
                    break

                # 早期終了チェック（50 文字おきに評価 → オーバーヘッド最小化）
                if early_stop_cfg is not None and len(accumulated) % 50 < 5:
                    reason = check_early_stop(
                        accumulated, num_predict, min_moves, early_stop_cfg
                    )
                    if reason:
                        stop_reason = reason
                        break

    except requests.exceptions.ConnectionError:
        print(f"[ERROR] Ollama に接続できません: {url}", file=sys.stderr)
        print("       Ollama が起動しているか、OLLAMA_BASE_URL を確認してください。",
              file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"[ERROR] Ollama HTTP エラー: {e}", file=sys.stderr)
        sys.exit(1)

    # total_tokens が取れなかった場合は文字数から近似
    if total_tokens == 0:
        total_tokens = max(1, len(accumulated) // 4)

    reasoning_tokens = _estimate_reasoning_tokens(accumulated, total_tokens)
    return accumulated, total_tokens, reasoning_tokens, stop_reason


def _estimate_reasoning_tokens(text: str, total_tokens: int) -> int:
    """
    <think>...</think> 内テキストの文字数比率でリーズニングトークン数を近似する。
    """
    match = re.search(r'<think>(.*?)</think>', text, re.DOTALL | re.IGNORECASE)
    if not match:
        return 0
    think_len = len(match.group(1))
    total_len = max(len(text), 1)
    return int(total_tokens * (think_len / total_len))


# ===========================================================================
# 実験ループ
# ===========================================================================

def run_experiment(
    N: int,
    trials: int,
    model: str,
    base_url: str,
    num_predict: Optional[int] = None,
    early_stop_cfg: Optional[EarlyStopConfig] = None,
) -> list[dict]:
    """
    N 枚ハノイの塔で trials 回の推論を実行し、結果リストを返す。

    Parameters
    ----------
    N : int
        円盤の枚数。
    trials : int
        試行回数。
    model : str
        Ollama モデル名。
    base_url : str
        Ollama サーバ URL。
    num_predict : int or None
        手動指定時のトークン上限。None なら calc_num_predict(N) を使用。
    early_stop_cfg : EarlyStopConfig or None
        None の場合は早期終了なし。

    Returns
    -------
    list[dict]
        各試行の結果辞書のリスト。
    """
    env          = TowerOfHanoiEnv(N=N)
    results: list[dict] = []
    num_predict_ = num_predict if num_predict is not None else calc_num_predict(N)

    es_label = "有効" if early_stop_cfg is not None else "無効"
    print(f"\n{'='*60}")
    print(f"  Tower of Hanoi  N={N}  trials={trials}  model={model}")
    print(f"  Ollama URL: {base_url}")
    print(f"  最短手数 (2^N-1): {env.min_moves}")
    print(f"  num_predict: {num_predict_}"
          + ("  (手動指定)" if num_predict is not None else f"  (= 1024 * 2^N)"))
    print(f"  num_ctx:     {num_predict_ + 512}")
    print(f"  早期終了:    {es_label}")
    print(f"{'='*60}\n")

    for trial in range(1, trials + 1):
        print(f"--- Trial {trial}/{trials} ---")
        prompt = env.get_prompt()

        t_start = time.time()
        text, total_tokens, reasoning_tokens, es_reason = query_ollama(
            prompt        = prompt,
            model         = model,
            base_url      = base_url,
            num_predict   = num_predict_,
            min_moves     = env.min_moves,
            early_stop_cfg= early_stop_cfg,
        )
        elapsed = time.time() - t_start

        moves    = env.extract_moves_from_text(text)
        accuracy = 1 if env.goal_reached(moves) else 0
        v_score  = env.evaluate_state(moves)

        result = {
            "trial":            trial,
            "accuracy":         accuracy,
            "total_tokens":     total_tokens,
            "reasoning_tokens": reasoning_tokens,
            "num_predict":      num_predict_,
            "num_ctx":          num_predict_ + 512,
            "moves_extracted":  len(moves),
            "v_score":          v_score,
            "elapsed_sec":      round(elapsed, 2),
            "early_stop":       es_reason,
        }
        results.append(result)

        status   = "PASS" if accuracy else "FAIL"
        es_info  = f"  es={es_reason}" if es_reason else ""
        print(f"  [{status}] accuracy={accuracy}  "
              f"total_tokens={total_tokens}  "
              f"reasoning_tokens={reasoning_tokens}  "
              f"v_score={v_score:.4f}  "
              f"moves={len(moves)}  "
              f"time={elapsed:.1f}s{es_info}")

    return results


def print_summary(results: list[dict], N: int) -> None:
    """実験結果のサマリーを標準出力へ表示する。"""
    n        = len(results)
    avg_acc  = sum(r["accuracy"]         for r in results) / n
    avg_tok  = sum(r["total_tokens"]     for r in results) / n
    avg_reas = sum(r["reasoning_tokens"] for r in results) / n
    avg_v    = sum(r["v_score"]          for r in results) / n

    es_counts: dict[str, int] = {}
    for r in results:
        reason = r.get("early_stop")
        if reason:
            es_counts[reason] = es_counts.get(reason, 0) + 1

    print(f"\n{'='*60}")
    print(f"  Summary  N={N}  trials={n}")
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
        description="ハノイの塔で LLM の推論崩壊を検知する最小実験スクリプト"
    )
    parser.add_argument("--N",           type=int,   required=True)
    parser.add_argument("--trials",      type=int,   default=None,
                        help="試行回数（省略時は N に応じて自動設定: N≤4→25, N=5→20, N=6→15, N=7→10, N≥8→5）")
    parser.add_argument("--model",       type=str,   default="deepseek-r1:14b")
    parser.add_argument("--ollama-url",  type=str,   default=None)
    parser.add_argument("--num_predict", type=int,   default=None,
                        help="最大出力トークン数の手動指定（省略時は N に応じて自動設定）")
    parser.add_argument("--output",      type=str,   default=None,
                        help="結果を保存する JSON ファイルパス")
    parser.add_argument("--no-early-stop", action="store_true",
                        help="早期終了アルゴリズムを無効化する")

    # 早期終了パラメータの個別調整
    parser.add_argument("--es-think-ratio",    type=float, default=None,
                        help="Think Budget 比率（省略時は N に応じて自動設定: N≤5→0.65, N=6→0.55, N=7→0.45, N≥8→0.35）")
    parser.add_argument("--es-move-mult",      type=float, default=1.5,
                        help="Move Count Ceiling 倍率 (default: 1.5)")
    parser.add_argument("--es-loop-window",    type=int,   default=6,
                        help="ループ検出ウィンドウ手数 (default: 6)")
    parser.add_argument("--es-loop-count",     type=int,   default=2,
                        help="ループ判定の出現回数閾値 (default: 2)")
    return parser.parse_args()


def main() -> None:
    args     = parse_args()
    base_url = (
        args.ollama_url
        or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    )

    # N 依存のデフォルト値を解決
    trials          = args.trials       if args.trials       is not None else calc_default_trials(args.N)
    think_ratio     = args.es_think_ratio if args.es_think_ratio is not None else calc_think_budget_ratio(args.N)

    early_stop_cfg: Optional[EarlyStopConfig] = None
    if not args.no_early_stop:
        early_stop_cfg = EarlyStopConfig(
            think_budget_ratio  = think_ratio,
            max_move_multiplier = args.es_move_mult,
            loop_window         = args.es_loop_window,
            loop_min_count      = args.es_loop_count,
        )

    results = run_experiment(
        N              = args.N,
        trials         = trials,
        model          = args.model,
        base_url       = base_url,
        num_predict    = args.num_predict,
        early_stop_cfg = early_stop_cfg,
    )

    print_summary(results, args.N)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"結果を保存しました: {args.output}")


if __name__ == "__main__":
    main()
