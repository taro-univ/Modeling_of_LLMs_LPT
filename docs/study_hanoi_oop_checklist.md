# 写経で学ぶ OOP / システム設計 — `hanoi_env.py` チェックリスト

`envs/hanoi_env.py` / `envs/base_env.py` を写経しながら設計を学ぶための自走用チェックリスト。

## 進め方の原則

- **写経先は別ファイル**にする（例: `practice/hanoi_env_practice.py`）。本物は触らない。
- 1 メソッドごとに **「何を・なぜ」を自分の言葉でコメントに書いてから写す**。写し終えたら本物のコメントと突き合わせる。
- フェーズの区切りで `python3 -m pytest tests/test_hanoi_env.py -q` を緑にする（import 先を一時的に写経ファイルへ差し替えて確認）。
- input（写経）を実装と同じ日に詰め込まない。1〜2 フェーズ / セッション。

各項目は「写せた」ではなく **「なぜそうなっているか説明できる」** で ✓ を付ける。

---

## Phase 0 — `BaseEnv`（抽象基底）

- [ ] `ABC` を継承し `@abstractmethod` を付ける目的を説明できる（= サブクラスに実装を強制する「契約」）
- [ ] `min_moves` / `initial_state` / `goal_state` が `@property` かつ `@abstractmethod` である理由
- [ ] `V(x)`（`evaluate_state`）の中身を基底に書かず抽象にしている理由（物理的意味がパズル依存）
- [ ] `count_moves` のように **抽象メソッドの組み合わせで書ける共通処理**を基底に置く発想（Template Method の入口）
- [ ] 自問: `extract_moves_with_position` が基底にあるのに、なぜハノイ側で上書きするのか（→ Phase 3 で回収）

## Phase 1 — `__init__` と状態表現

- [ ] 盤面を dict of list で表し、各リストが「底が大きい」順である理由を説明できる
- [ ] `goal_state`（単数・プロンプト用）と `goal_states`（複数・評価用）を分けて持つ理由
- [ ] `_goal_state_keys` を `frozenset` で **コンストラクタで事前計算**し使い回す利点（ゴール判定が O(1)）
- [ ] 公開は `@property`（読み取り専用）、内部状態は `_` 始まりにするカプセル化の方針

## Phase 2 — シミュレーション中核 `_parse_move` / `_apply_move`

- [ ] `_apply_move` が **非合法手では盤面を変えず `False`** を返す＝失敗してもオブジェクトを壊さない不変条件
- [ ] 合法判定 3 条件（src が空 / 指定円盤が一番上にない / 小さい円盤の上に大きい円盤）を列挙できる
- [ ] 戻り値（bool）で成否を伝え、呼び出し側が `illegal_count` を集計する責務分担

## Phase 3 — 入出力 `get_prompt` / `extract_moves_*`

- [ ] `MOVE_RE` で抽出した手を即「正規化文字列」に揃えて返す境界設計（汚い外部入力 → 綺麗な内部表現）
- [ ] `get_prompt` と `get_prompt_from_state` の違い（初期状態起点 vs 任意中間状態起点で再開）
- [ ] Phase 0 の自問を回収: 正規表現なら正確な出現開始位置が取れるので position 付き抽出を上書き

## Phase 4 — 評価ロジック `evaluate_state` / `_compute_V` / `_min_moves_to_peg`

- [ ] `_min_moves_to_peg` は盤面を **動かさず** に残り手数を厳密計算する純粋再帰、`evaluate_state` は実際に動かす — この対比を説明できる
- [ ] `_min_moves_to_peg` の漸化式（n が target にある / ない場合）を再現できる
- [ ] `V = LAMBDA_DIST * d_hat + LAMBDA_PENALTY * illegal_count` の各項の意味と「V 小 = ゴールに近い」
- [ ] `evaluate_state`（ペナルティ込み）と `goal_reached`（ペナルティ無し）を **目的別に分ける**設計
- [ ] ゴール到達時点で `break` / `return` する理由（余剰手による誤判定を防ぐ）

## Phase 5 — 仕上げ `solve` / `get_neighbors` / `_get_state_coord`

- [ ] `_solve_recursive` の古典的ハノイ再帰（n-1 を退避 → n を移動 → n-1 を戻す）
- [ ] `get_neighbors` が合法 1 手で行ける全次状態を返す（グラフ探索 / 解析用）
- [ ] `_get_state_coord` が盤面を 3N 次元 one-hot に変換する用途（隠れ状態と並べた幾何解析）
- [ ] 本体ロジックと「解析用に外へ開く API」の責務が分かれていることを確認

---

## 全体を貫く設計テーマ（写経後に振り返る）

- **契約と実装の分離**: 基底＝契約、サブクラス＝物理的意味
- **不変条件**: 失敗してもオブジェクトを壊さない（`_apply_move`）
- **純粋関数 vs 副作用**: 距離計算（純粋）とシミュレーション（副作用）の使い分け
- **事前計算とデータ構造**: `frozenset` によるゴール集合の O(1) 判定
- **境界での正規化**: 外部テキストを内部表現に揃える
- **目的別 API**: 同じシミュレーションでも評価用 / 判定用で関数を分ける
