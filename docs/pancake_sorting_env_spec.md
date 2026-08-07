# Pancake Sorting Env 実装仕様書

作成日: 2026-07-24

対象: `envs/pancake_env.py` と `runners/run_local.py`

目的: Hanoi とは異なる permutation 状態空間を持ち、単一 goal を自然に定義できる Pancake Sorting puzzle を `BaseEnv` に追加し、LLM 実験・early stop・hidden state capture の既存アーキテクチャへ最小変更で接続する。

## 1. 採用理由

Pancake Sorting は、スタック上の上から `k` 枚を反転する prefix reversal により permutation を操作するパズルである。

既存パズルとの違い:

- Hanoi: 3 peg 上の再帰的状態空間、最短経路は閉形式に近い。
- Lights Out: GF(2) 線形系、手順は可換、goal は all-zero。
- Pancake Sorting: permutation graph / Cayley graph、手順は非可換、goal は昇順 permutation の単一状態。

実験上の利点:

- `Flip k` という短い move 形式で、正規表現抽出が安定する。
- `N` により状態数 `N!` が増え、Hanoi の `3^N` と異なるスケーリングを持つ。
- 小さい `N` では BFS により exact distance と optimal solution を計算できる。
- move capture では permutation 遷移、token capture では短い action token と reasoning token を対応づけやすい。

## 2. パズル定義

### 2.1 状態

状態は pancake stack を上から下へ並べた permutation とする。

例:

```python
(3, 1, 4, 2)
```

これは上から順に pancake 3, 1, 4, 2 が積まれていることを表す。

### 2.2 goal

goal は単一状態:

```python
(1, 2, ..., N)
```

gauge 等価な goal は導入しない。

### 2.3 move

合法手は `Flip k` である。

意味:

- stack の上から `k` 枚を反転する。
- `2 <= k <= N` のとき合法。
- `k=1` は状態を変えないため不採用。

例:

```text
state = (3, 1, 4, 2)
Flip 3
next  = (4, 1, 3, 2)
```

### 2.4 状態空間

状態数は `N!`。各状態からの分岐数は `N-1`。

初期実装では exact BFS を使うため、対応サイズは次を推奨する。

```text
3 <= N <= 8
```

`N=9` は状態数 `362880` でまだ可能だが、テスト・ローカル実験の軽さを優先して初期実装では上限 8 とする。

## 3. `BaseEnv` 実装仕様

クラス名:

```python
PancakeSortingEnv
```

ファイル:

```text
envs/pancake_env.py
```

### 3.1 constructor

```python
def __init__(
    self,
    N: int,
    initial_state: tuple[int, ...] | None = None,
    seed: int | None = None,
    scramble_depth: int | None = None,
) -> None:
```

仕様:

- `N` は `3 <= N <= 8`。
- `initial_state` が与えられた場合は permutation として検証する。
- `initial_state` がない場合は `seed` と `scramble_depth` から初期状態を生成する。
- `initial_state == goal_state` は reject する。
- `seed` 指定時は同一初期状態・同一解を再現できる。

`scramble_depth`:

- goal から random legal flip を適用する回数。
- 未指定時は `max(2, N)` を default とする。
- 直前手と同じ `k` は避ける。同じ flip を連続すると即座に戻るため。
- 生成後に BFS distance を確認し、distance > 0 でなければ再生成する。
- 難易度制御を厳密にしたい場合は将来 `target_distance` を追加する。

### 3.2 properties

```python
@property
def min_moves(self) -> int:
```

`initial_state` から `goal_state` までの exact shortest path length。

```python
@property
def initial_state(self) -> tuple[int, ...]:
```

初期 stack。tuple は immutable なのでそのまま返してよい。

```python
@property
def goal_state(self) -> tuple[int, ...]:
```

`tuple(range(1, N + 1))`。

### 3.3 state_to_key

```python
def state_to_key(self, state) -> tuple[int, ...]:
```

状態を検証して tuple に正規化する。

### 3.4 make_sub_env

```python
def make_sub_env(self, N: int) -> "PancakeSortingEnv":
```

few-shot 用に同じ puzzle type の小さい env を返す。

初期実装:

```python
return PancakeSortingEnv(N, seed=42)
```

注意: 現状 `runners/run_local.py` の `build_few_shot_messages()` は Hanoi 由来のコメントを持つが、実装自体は `env.make_sub_env().get_prompt()` と `solve()` を使うため Pancake でも動く。ただし初期実験では外部補助なしを基準にするため、runner の default は `--n-shot 0` とする。

追加注意:

- `PancakeSortingEnv` の初期対応サイズを `3 <= N <= 8` とする場合、`N=3` で `--n-shot 1` を明示すると `make_sub_env(2)` が呼ばれて失敗する。
- 初期実装では Pancake 実験の推奨を `--n-shot 0` とし、runner default も `0` に揃える。
- 将来対応として、`BaseEnv.get_few_shot_examples()` を追加し、各 puzzle が有効な example size を自分で選ぶ設計にする。

## 4. Prompt 仕様

`get_prompt()` は次の情報を含む。

- puzzle 名
- pancake stack は top-to-bottom であること
- `Flip k` は上から `k` 枚を反転すること
- 合法範囲は `2 <= k <= N`
- goal は `[1, 2, ..., N]`
- 出力は `Flip k` を1行ずつ
- minimum number of moves を明示

例:

```text
You are an AI solving a Pancake Sorting puzzle.

[Rules]
1. The stack contains 5 pancakes labeled 1 to 5.
2. The stack is shown from top to bottom.
3. A move "Flip k" reverses the top k pancakes.
4. Only moves with 2 <= k <= 5 are legal.
5. Goal: sort the stack into [1, 2, 3, 4, 5] from top to bottom.

[Initial State]
  Stack: [3, 1, 5, 2, 4]

[Goal State]
  Stack: [1, 2, 3, 4, 5]

[Output Format]
Output each step as "Flip k" on its own line.
Example: Flip 3

Solve in the minimum number of moves (4 moves).
Output ONLY the moves, one per line. Stop immediately after the final move. Begin:
```

`get_system_hint()`:

```text
You are an expert at Pancake Sorting. Track the stack exactly after each prefix reversal. Use only legal moves of the form "Flip k".
```

## 5. Move 抽出仕様

正規表現:

```python
MOVE_RE = re.compile(r"Flip\s+(\d+)", re.IGNORECASE)
```

`extract_moves_from_text(text)`:

- `Flip 03` は `Flip 3` に正規化する。
- 範囲外の `Flip k` は抽出段階では残してよい。
- 合法性は simulation 側で扱う。

返り値例:

```python
["Flip 3", "Flip 5"]
```

`extract_moves_with_position(text)`:

- 正規化済み move 文字列と `match.start()` を返す。
- token/move capture の同期点として使う。

## 6. solve / distance 実装

### 6.1 BFS 方針

goal から全状態への BFS を一度構築する。

保存するもの:

```python
self._distance: dict[tuple[int, ...], int]
self._next_move_to_goal: dict[tuple[int, ...], str]
```

BFS の向き:

- graph は無向。`Flip k` は自己逆操作。
- goal から BFS して、任意状態 `s` の neighbor `n` を発見したとき、`n` から goal へ近づく次手は同じ `Flip k`。

擬似コード:

```python
distance[goal] = 0
queue = deque([goal])
while queue:
    state = queue.popleft()
    for k in range(2, N + 1):
        neighbor = apply_flip(state, k)
        if neighbor not in distance:
            distance[neighbor] = distance[state] + 1
            next_move_to_goal[neighbor] = f"Flip {k}"
            queue.append(neighbor)
```

`solve()`:

```python
state = initial_state
moves = []
while state != goal_state:
    move = next_move_to_goal[state]
    moves.append(move)
    state = apply_move(state, move)
return moves
```

### 6.2 BFS cache

同じ `N` では BFS table を共有できる。

推奨:

```python
@functools.lru_cache(maxsize=None)
def _build_bfs_tables(N: int) -> tuple[dict, dict]:
```

ただし numpy は不要で、標準ライブラリだけで実装する。

## 7. evaluate_state / V(x)

`evaluate_state(current_moves)` は move list を初期状態から simulation し、最終状態の exact distance を用いる。

基本形:

```python
V(x) = d(x, goal) / min_moves(initial, goal)
```

返り値:

- goal 到達時: `0.0`
- 初期状態: `1.0`
- round は既存 env に合わせて `round(value, 6)`。

違法手:

- 初期実装では違法な `Flip k` を無視し、状態を変えない。
- 解析時に違法手を見たい場合に備え、将来 `illegal_count` penalty を追加できる。

候補:

```python
LAMBDA_DIST = 1.0
LAMBDA_PENALTY = 0.0
```

初期実装では penalty なしを推奨する。LLM が `Flip 1` や範囲外を出したときに、評価が過度に不連続になることを避けるため。

## 8. goal_reached

`goal_reached(current_moves)`:

- 初期状態から moves を simulation する。
- simulation 中または終了時に goal に到達したら `True`。
- goal 到達後の余剰手は無視してよい。Hanoi と同じく early_stop との相性を優先する。

推奨実装:

```python
state = initial_state
for move in current_moves:
    if state == goal_state:
        return True
    state = apply_move_if_legal(state, move)
return state == goal_state
```

## 9. runner 接続仕様

対象:

```text
runners/run_local.py
```

変更点:

1. import 追加

```python
from envs.pancake_env import PancakeSortingEnv
```

2. `_puzzle_name()`

```python
if isinstance(env, PancakeSortingEnv):
    return "pancake"
```

3. CLI choices

```python
choices=["hanoi", "lights_out", "pancake"]
```

4. seed 制限

現状は `--seed` を Lights Out のみに許可している。Pancake でも初期 permutation 生成に使うため、次の形に変更する。

```python
if args.puzzle not in ("lights_out", "pancake") and args.seed is not None:
    parser.error("--seed is only supported with --puzzle lights_out or pancake")
```

5. factory

```python
puzzle_factories = {
    "hanoi": TowerOfHanoiEnv,
    "lights_out": LightsOutEnv,
    "pancake": PancakeSortingEnv,
}
```

6. env construction

```python
if args.puzzle in ("lights_out", "pancake"):
    env = env_factory(args.N, seed=args.seed)
else:
    env = env_factory(args.N)
```

### 9.1 early_stop

既存の `check_early_stop()` は `env.extract_moves_from_text()` 委譲に対応済みなので、`Flip k` は move count として扱える。

注意:

- Algorithm C の loop detection は Hanoi の move tuple 再検証だけ特別扱いしている。
- 現状の `runners/run.py::check_early_stop()` は move count には `env` / `moves` を使うが、loop detection 自体は legacy Hanoi regex の `_extract_loop_moves(text)` に依存している。
- したがって Pancake の `Flip k` について初期実装で効く early stop は主に `goal_reached`, `no_move_catchall`, `move_ceiling`, `stagnation_after_move` であり、Algorithm C は実質的に発火しない。
- Pancake は `Flip k` が自己逆なので、同じ `Flip k` の反復ループ検出は有用である。ただしこれは Pancake env 追加とは別の runner 改修として扱う。
- 将来、`BaseEnv.extract_loop_signature(move)` または `BaseEnv.is_reverse_move(a, b)` のような hook を追加すれば、Hanoi / Pancake / Lights Out で loop detection を puzzle 固有にできる。

### 9.2 hidden capture

追加対応は不要。

- move timing: `Flip k` が新しく検出された token step で hidden `[M,L,D]` を保存。
- token timing: 既存の token / token stride 保存にそのまま乗る。
- `move_texts` には `Flip 3` 形式の正規化済み文字列が入る。

## 10. テスト仕様

追加ファイル:

```text
tests/test_pancake_env.py
```

必須テスト:

1. seed 再現性

```python
env_a = PancakeSortingEnv(N=5, seed=123)
env_b = PancakeSortingEnv(N=5, seed=123)
assert env_a.initial_state == env_b.initial_state
assert env_a.solve() == env_b.solve()
assert env_a.min_moves == env_b.min_moves
```

2. solve が goal 到達

```python
env = PancakeSortingEnv(N=5, seed=1)
solution = env.solve()
assert len(solution) == env.min_moves
assert env.goal_reached(solution) is True
assert env.evaluate_state(solution) == 0.0
assert env.evaluate_state([]) == 1.0
```

3. move 抽出

```python
text = "Flip 3\nnoise\nflip 05"
assert env.extract_moves_from_text(text) == ["Flip 3", "Flip 5"]
```

4. move positions

```python
assert env.extract_moves_with_position(text) == [
    ("Flip 3", text.index("Flip 3")),
    ("Flip 5", text.index("flip 05")),
]
```

5. state_to_key

```python
assert env.state_to_key([3, 1, 2]) == (3, 1, 2)
```

6. invalid N

```python
with pytest.raises(ValueError):
    PancakeSortingEnv(N=2)
with pytest.raises(ValueError):
    PancakeSortingEnv(N=9)
```

7. invalid initial_state

```python
with pytest.raises(ValueError):
    PancakeSortingEnv(N=4, initial_state=(1, 2, 2, 4))
with pytest.raises(ValueError):
    PancakeSortingEnv(N=4, initial_state=(1, 2, 3, 4))
```

8. BaseEnv subclass registration

`tests/test_base_env.py` に `PancakeSortingEnv` を追加する。

## 11. 初期実験プロトコル

推奨 smoke test:

```bash
python runners/run_local.py \
  --puzzle pancake \
  --N 5 \
  --trials 1 \
  --seed 42 \
  --n-shot 0 \
  --capture-timing move
```

token capture:

```bash
python runners/run_local.py \
  --puzzle pancake \
  --N 5 \
  --trials 1 \
  --seed 42 \
  --n-shot 0 \
  --capture-timing token:8 \
  --capture-mode relative
```

初期 sweep:

```text
N = 4, 5, 6, 7
temperature = 0.6
seed = 1..20
n_shot = 0
capture_timing = move
```

## 12. 非目標

初期実装では次を行わない。

- burnt pancake sorting
- `target_distance` による厳密な距離指定生成
- A* / IDA*
- runner 内での物理量計算
- DB への hidden 本体保存
- Pancake 専用 few-shot provider の抽象化

これらは、Pancake env が安定して実験可能になった後の拡張とする。

## 13. 実装順序

1. `envs/pancake_env.py` を追加する。
2. `tests/test_pancake_env.py` を追加する。
3. `tests/test_base_env.py` に Pancake を追加する。
4. `pytest tests/test_pancake_env.py tests/test_base_env.py` を通す。
5. `runners/run_local.py` に puzzle choice と factory を追加する。
6. `pytest tests/test_early_stop.py` を通し、env 委譲による move count が壊れていないことを確認する。
