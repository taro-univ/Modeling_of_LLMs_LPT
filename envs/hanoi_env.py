"""hanoi_env.py - Tower of Hanoi environment."""

import re

from envs.base_env import BaseEnv


# ===========================================================================
# TowerOfHanoiEnv
# ===========================================================================

class TowerOfHanoiEnv(BaseEnv):
    """
    ハノイの塔の環境シミュレータおよび推論ポテンシャルの絶対評価。

    円盤数 N で初期化し、初期状態（A に全円盤）と
    ゴール状態（C に全円盤）を管理する。
    """

    LAMBDA_DIST = 1.0
    LAMBDA_PENALTY = 0.5

    def __init__(self, N: int) -> None:
        if N < 1:
            raise ValueError("N must be >= 1")
        super().__init__(N)
        self._initial_state: dict = {
            'A': list(range(N, 0, -1)),  # [N, N-1, ..., 1]（底が大きい）
            'B': [],
            'C': [],
        }
        self._goal_state: dict = {
            'A': [],
            'B': [],
            'C': list(range(N, 0, -1)),
        }

    # ------------------------------------------------------------------
    # 公開 API
    # ------------------------------------------------------------------

    @property
    def min_moves(self) -> int:
        return (2 ** self.N) - 1

    @property
    def initial_state(self) -> dict:
        return self._initial_state

    @property
    def goal_state(self) -> dict:
        return self._goal_state

    def make_sub_env(self, N: int) -> 'TowerOfHanoiEnv':
        return TowerOfHanoiEnv(N)

    def state_to_key(self, state: dict) -> tuple:
        """状態を hashable なタプルへ変換する。"""
        return (tuple(state['A']), tuple(state['B']), tuple(state['C']))

    def get_prompt(self) -> str:
        """LLM に与える初期プロンプトを生成して返す。"""
        initial_str = self._state_to_str(self.initial_state)
        goal_str    = self._state_to_str(self.goal_state)
        return (
            f"You are an AI solving the Tower of Hanoi puzzle.\n\n"
            f"[Rules]\n"
            f"1. There are 3 pegs (A, B, C) and {self.N} disks.\n"
            f"2. Only the top disk of a peg can be moved at a time.\n"
            f"3. A larger disk cannot be placed on a smaller disk.\n\n"
            f"[Initial State]\n{initial_str}\n\n"
            f"[Goal State]\n{goal_str}\n\n"
            f"[Output Format]\n"
            f'Output each step as "Move <disk_number> from <peg> to <peg>" on its own line.\n'
            f"Example: Move 1 from A to C\n\n"
            f"Solve in the minimum number of moves ({self.min_moves} moves). "
            f"Output ONLY the moves, one per line. Stop immediately after the final move. Begin:\n"
        )

    def get_prompt_from_state(self, state: dict) -> str:
        """任意の中間状態を起点に LLM へ与えるプロンプトを生成して返す。"""
        state_str = self._state_to_str(state)
        goal_str  = self._state_to_str(self.goal_state)
        remaining = self._min_moves_from(state)
        return (
            f"You are an AI solving the Tower of Hanoi puzzle.\n\n"
            f"[Rules]\n"
            f"1. There are 3 pegs (A, B, C) and {self.N} disks.\n"
            f"2. Only the top disk of a peg can be moved at a time.\n"
            f"3. A larger disk cannot be placed on a smaller disk.\n\n"
            f"[Current State]\n{state_str}\n\n"
            f"[Goal State]\n{goal_str}\n\n"
            f"[Output Format]\n"
            f'Output each step as "Move <disk_number> from <peg> to <peg>" on its own line.\n'
            f"Example: Move 1 from A to C\n\n"
            f"Solve in the minimum number of moves ({remaining} moves). "
            f"Output ONLY the moves, one per line. Stop immediately after the final move. Begin:\n"
        )

    def extract_moves_from_text(self, text: str) -> list:
        """LLM テキストから "Move <disk> from <peg> to <peg>" 形式の手を抽出する。"""
        matches = re.findall(
            r'Move\s+(\d+)\s+from\s+([ABC])\s+to\s+([ABC])',
            text, re.IGNORECASE,
        )
        return [f"Move {d} from {s.upper()} to {t.upper()}" for d, s, t in matches]

    def evaluate_state(self, current_moves: list) -> float:
        """
        手のリストをシミュレートし、推論ポテンシャル V(x) を返す。

        ゴール到達時点で早期終了し、余剰手による誤判定を防ぐ。
        """
        state         = {k: list(v) for k, v in self.initial_state.items()}
        illegal_count = 0

        for move_str in current_moves:
            if state == self.goal_state:
                break
            parsed = self._parse_move(move_str)
            if parsed is None:
                continue
            disk, src, dst = parsed
            if not self._apply_move(state, disk, src, dst):
                illegal_count += 1

        return self._compute_V(state, illegal_count)

    def goal_reached(self, current_moves: list) -> bool:
        """
        手のリストをシミュレートし、ゴール状態に到達したかを返す。

        accuracy の判定に使用。違法手ペナルティは含まない。
        """
        state = {k: list(v) for k, v in self.initial_state.items()}

        for move_str in current_moves:
            if state == self.goal_state:
                return True
            parsed = self._parse_move(move_str)
            if parsed is None:
                continue
            disk, src, dst = parsed
            self._apply_move(state, disk, src, dst)

        return state == self.goal_state

    def solve(self) -> list:
        """最適手列を文字列リストで返す（O(2^N) 再帰）。"""
        return self._solve_recursive(self.N, 'A', 'C', 'B')

    def get_bad_move(self) -> str:
        """fixation 用: 最大円盤を A→B へ移動（ほぼ常に非合法）。"""
        return f"Move {self.N} from A to B"

    def get_neighbors(self, state: dict) -> list:
        """合法手 1 手で到達できる全次状態を返す。"""
        neighbors = []
        pegs = ['A', 'B', 'C']
        for src in pegs:
            if not state[src]:
                continue
            disk = state[src][-1]
            for dst in pegs:
                if src == dst:
                    continue
                if state[dst] and state[dst][-1] < disk:
                    continue
                new_state = {p: list(state[p]) for p in pegs}
                new_state[dst].append(new_state[src].pop())
                neighbors.append(new_state)
        return neighbors

    # ------------------------------------------------------------------
    # 物理的特性
    # ------------------------------------------------------------------

    def _get_state_coord(self, state: dict) -> 'np.ndarray':
        """盤面状態を 3N 次元の one-hot ベクトルへ変換する。"""
        import numpy as np
        peg_index = {'A': 0, 'B': 1, 'C': 2}
        coord = np.zeros(3 * self.N, dtype=float)
        for peg, disks in state.items():
            col = peg_index[peg]
            for disk in disks:
                coord[(disk - 1) * 3 + col] = 1.0
        return coord

    def _min_moves_from(self, state: dict) -> int:
        """任意の盤面状態からゴールまでの最短手数を O(N) 再帰で返す。"""
        return self._min_moves_to_peg(state, self.N, 'C')

    def _compute_V(self, state: dict, illegal_count: int = 0) -> float:
        """ハノイ固有の推論ポテンシャル V(x) を計算する。"""
        d_hat = self._min_moves_from(state) / self.min_moves
        penalty = self.LAMBDA_PENALTY * illegal_count
        return round(self.LAMBDA_DIST * d_hat + penalty, 6)

    # ------------------------------------------------------------------
    # 内部ユーティリティ
    # ------------------------------------------------------------------

    def _state_to_str(self, state: dict) -> str:
        lines = []
        for peg in ('A', 'B', 'C'):
            disks    = state[peg]
            disk_str = ', '.join(str(d) for d in disks) if disks else '(empty)'
            lines.append(f"  Peg {peg}: [{disk_str}]")
        return '\n'.join(lines)

    def _parse_move(self, move_str: str):
        """
        "Move <disk> from <src> to <dst>" 形式をパースする。
        マッチしない場合は None を返す。
        """
        m = re.search(
            r'Move\s+(\d+)\s+from\s+([ABC])\s+to\s+([ABC])',
            move_str, re.IGNORECASE,
        )
        if m:
            return int(m.group(1)), m.group(2).upper(), m.group(3).upper()
        return None

    def _apply_move(self, state: dict, disk: int, src: str, dst: str) -> bool:
        """
        盤面に手を適用する。合法なら True、非合法なら False を返す。
        非合法手は state を変更しない。
        """
        src_stack = state.get(src)
        dst_stack = state.get(dst)

        if src_stack is None or dst_stack is None or not src_stack:
            return False
        if src_stack[-1] != disk:
            return False
        if dst_stack and dst_stack[-1] < disk:
            return False

        dst_stack.append(src_stack.pop())
        return True

    def _min_moves_to_peg(self, state: dict, n: int, target: str) -> int:
        """
        円盤 1..n を target ペグへ積み上げるための最短手数を再帰で返す。

        アルゴリズム:
          - 円盤 n が既に target にある → n-1 のサブ問題を同じ target で解く
          - 円盤 n が別のペグにある   → aux を中継地として
              cost = D(state, n-1, aux) + 1 + (2^(n-1) - 1)
        """
        if n == 0:
            return 0

        peg_of_n = next(
            (peg for peg, disks in state.items() if n in disks), None
        )

        if peg_of_n == target:
            return self._min_moves_to_peg(state, n - 1, target)
        else:
            aux           = self._third_peg(peg_of_n, target)
            cost_to_clear = self._min_moves_to_peg(state, n - 1, aux)
            cost_from_aux = (2 ** (n - 1)) - 1
            return cost_to_clear + 1 + cost_from_aux

    def _simulate_states(self, start_state: dict, moves: list) -> list:
        """手のリストを適用し、各ステップ後の状態キー列を返す。"""
        state = {k: list(v) for k, v in start_state.items()}
        keys  = [self.state_to_key(state)]
        for move_str in moves:
            parsed = self._parse_move(move_str)
            if parsed is not None:
                disk, src, dst = parsed
                self._apply_move(state, disk, src, dst)
            keys.append(self.state_to_key(state))
        return keys

    def _solve_recursive(self, n: int, src: str, dst: str, aux: str) -> list:
        """ハノイの塔の最適解を再帰で生成する。"""
        if n == 0:
            return []
        return (
            self._solve_recursive(n - 1, src, aux, dst)
            + [f"Move {n} from {src} to {dst}"]
            + self._solve_recursive(n - 1, aux, dst, src)
        )

    @staticmethod
    def _third_peg(peg1: str, peg2: str) -> str:
        """3つのペグ {A, B, C} のうち peg1・peg2 以外の1つを返す。"""
        return ({'A', 'B', 'C'} - {peg1, peg2}).pop()
