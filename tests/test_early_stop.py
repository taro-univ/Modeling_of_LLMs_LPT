"""
tests/test_early_stop.py

Algorithm D（no_move_ratio 閾値変更）と Algorithm E（stagnation_after_move）の
単体テスト。Collapse-Phase Sweep 実施前に全テストが PASS であることを確認する。

実行方法（コンテナ内 /app から）:
    python3 -m pytest tests/test_early_stop.py -v
"""

import pytest
from envs.lights_out_env import LightsOutEnv
from runners.run import check_early_stop, EarlyStopConfig


# ===========================================================================
# テスト用ヘルパー
# ===========================================================================

def _d_only_cfg(no_move_ratio: float) -> EarlyStopConfig:
    """Algorithm D のみを有効にした設定を返す。"""
    return EarlyStopConfig(
        no_move_ratio=no_move_ratio,
        enable_think_budget=False,
        enable_move_ceiling=False,
        enable_move_loop=False,
        enable_stagnation=False,
    )


def _b_only_cfg(max_move_multiplier: float) -> EarlyStopConfig:
    """Algorithm B のみを有効にした設定を返す。"""
    return EarlyStopConfig(
        max_move_multiplier=max_move_multiplier,
        enable_think_budget=False,
        enable_no_move=False,
        enable_move_ceiling=True,
        enable_move_loop=False,
        enable_stagnation=False,
    )


def check_stagnation(
    last_move_chunk: int | None,
    current_chunk: int,
    num_predict: int = 4096,
    stagnation_ratio: float = 0.20,
) -> str | None:
    """
    Algorithm E の発動条件を単体で検証するヘルパー。
    query_ollama のストリーミングループと同一ロジック。
    """
    if last_move_chunk is None:
        return None
    gap = current_chunk - last_move_chunk
    if gap > num_predict * stagnation_ratio:
        return "stagnation_after_move"
    return None


# ===========================================================================
# Algorithm D テスト（no_move_ratio 閾値変更の検証）
# ===========================================================================

class TestAlgorithmD:

    def test_d1_fires_above_threshold(self):
        """D-1: 3600 chars（閾値 3584 超）、手なし → no_move_catchall"""
        cfg = _d_only_cfg(no_move_ratio=0.25)
        text = "A" * 3600
        result = check_early_stop(text, num_predict=4096, min_moves=7, cfg=cfg)
        assert result == "no_move_catchall"

    def test_d2_silent_below_threshold(self):
        """D-2: 3500 chars（閾値 3584 未満）、手なし → None"""
        cfg = _d_only_cfg(no_move_ratio=0.25)
        text = "A" * 3500
        result = check_early_stop(text, num_predict=4096, min_moves=7, cfg=cfg)
        assert result is None

    def test_d3_silent_when_move_exists(self):
        """D-3: 閾値超過 + 手 1 件 → None（E の管轄）"""
        cfg = _d_only_cfg(no_move_ratio=0.25)
        text = "A" * 3600 + "\nMove 1 from A to C\n"
        result = check_early_stop(text, num_predict=4096, min_moves=7, cfg=cfg)
        assert result is None

    def test_d4_no_false_positive_in_ordered_phase(self):
        """D-4: 秩序相相当（1750 chars + 手）→ 誤発動しない"""
        cfg = _d_only_cfg(no_move_ratio=0.25)
        # 500 tok ≈ 1750 chars の推論後に最初の手（実測上限）
        text = "thinking..." * 130 + "\nMove 1 from A to C\n"
        result = check_early_stop(text, num_predict=4096, min_moves=7, cfg=cfg)
        assert result is None

    def test_d5_old_threshold_does_not_fire(self):
        """D-5: 旧閾値 0.50 では 3600 chars で発動せず、新閾値 0.25 では発動する"""
        text = "A" * 3600
        old_result = check_early_stop(
            text, num_predict=4096, min_moves=7, cfg=_d_only_cfg(0.50)
        )
        new_result = check_early_stop(
            text, num_predict=4096, min_moves=7, cfg=_d_only_cfg(0.25)
        )
        assert old_result is None
        assert new_result == "no_move_catchall"

    def test_d6_lights_out_toggle_prevents_no_move_catchall(self):
        """D-6: Lights Out の Toggle は env 委譲で手として数える。"""
        cfg = _d_only_cfg(no_move_ratio=0.25)
        env = LightsOutEnv(N=3, seed=42)
        text = "A" * 3600 + "\nToggle (0,0)\n"

        legacy_result = check_early_stop(text, num_predict=4096, min_moves=7, cfg=cfg)
        delegated_result = check_early_stop(
            text,
            num_predict=4096,
            min_moves=env.min_moves,
            cfg=cfg,
            env=env,
        )

        assert legacy_result == "no_move_catchall"
        assert delegated_result is None

    def test_d7_lights_out_still_fires_when_no_toggle_exists(self):
        """D-7: env 委譲後も Toggle なしなら no_move_catchall は維持する。"""
        cfg = _d_only_cfg(no_move_ratio=0.25)
        env = LightsOutEnv(N=3, seed=42)
        text = "A" * 3600

        result = check_early_stop(
            text,
            num_predict=4096,
            min_moves=env.min_moves,
            cfg=cfg,
            env=env,
        )

        assert result == "no_move_catchall"


# ===========================================================================
# Algorithm B テスト（move_ceiling の env 委譲検証）
# ===========================================================================

class TestAlgorithmB:

    def test_b1_lights_out_toggle_count_triggers_move_ceiling(self):
        """B-1: Lights Out の Toggle 数が上限を超えると move_ceiling が発火する。"""
        env = LightsOutEnv(N=3, seed=42)
        cfg = _b_only_cfg(max_move_multiplier=1.0)
        text = "\n".join("Toggle (0,0)" for _ in range(env.min_moves + 1))

        result = check_early_stop(
            text,
            num_predict=4096,
            min_moves=env.min_moves,
            cfg=cfg,
            env=env,
        )

        assert result == "move_ceiling"


# ===========================================================================
# Algorithm E テスト（stagnation_after_move の検証）
# ===========================================================================

class TestAlgorithmE:

    def test_e1_fires_after_moves1_stagnation(self):
        """E-1: moves=1後 gap=900 チャンク（閾値 819）→ stagnation_after_move"""
        result = check_stagnation(last_move_chunk=100, current_chunk=1000)
        assert result == "stagnation_after_move"

    def test_e2_fires_after_moves4_stagnation(self):
        """E-2: moves=4後 gap=900（B3 ボトルネック）→ stagnation_after_move"""
        result = check_stagnation(last_move_chunk=300, current_chunk=1200)
        assert result == "stagnation_after_move"

    def test_e3_silent_below_threshold(self):
        """E-3: gap=200（閾値 819 未満）→ None（手と手の間の通常推論）"""
        result = check_stagnation(last_move_chunk=800, current_chunk=1000)
        assert result is None

    def test_e4_silent_when_no_moves(self):
        """E-4: last_move_chunk=None（moves=0）→ None（D の管轄）"""
        result = check_stagnation(last_move_chunk=None, current_chunk=2000)
        assert result is None

    def test_e5_no_false_positive_in_ordered_phase(self):
        """E-5: 秩序相で誤発動しない（最終手後 gap=221 < 819）"""
        # 全手が 1621 チャンク以内に完成（実測最大値）
        # 最後の手が chunk=1400、その後は chunk=1621 で EOS
        result = check_stagnation(last_move_chunk=1400, current_chunk=1621)
        assert result is None

    def test_e6_algorithm_c_fires_before_e_in_loop(self):
        """E-6: ループ中は last_move_chunk が更新され続けるため E は発動しない"""
        # ループ中は手が連続して出る → gap が蓄積しない
        # chunk=10 ごとに手が出る場合、gap は常に < 819
        for move_chunk in range(100, 1000, 10):
            current = move_chunk + 9  # 次の手が出る直前
            result = check_stagnation(
                last_move_chunk=move_chunk, current_chunk=current
            )
            assert result is None, (
                f"E-6 FAIL: gap={current - move_chunk} で誤発動 "
                f"(move_chunk={move_chunk}, current={current})"
            )
