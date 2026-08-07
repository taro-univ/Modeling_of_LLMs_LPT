# 2026年9月末発表に向けた研究ロードマップ

作成日: 2026-07-27

目的: 2026年9月末の学会発表までに到達すべき研究成果、学習項目、実験計画、リスク管理を1本にまとめる。

関連論文から出た拡張実験案は、本ロードマップへ直接混ぜず、`docs/research_state/literature_extension_branches_20260728.md` で branch 的に管理する。主線へ採用するのは、pilot で有効性が見えたものに限る。

ただし `length_stop` と真の failure を分離する方針は本線へ採用済みとする。拡張実験は、phase labeling、token-hidden-event 統合、entropy / failure onset oracle、PCA 次元数選定、failure onset timeline の順で pilot する。one-step prediction、jump statistics、ablation、SLDS、一般 benchmark probe は、主線の PCA trajectory と drift/diffusion 解析が固まった後に扱う。

## 1. 研究の位置づけ

本研究は、LLM の推論過程を token-level hidden-state trajectory として観測し、推論成功・失敗を高次元状態空間上の時間発展の違いとして記述することを目指す。

既存の LLM 改善は、モデルサイズ拡大、追加学習、外部ツール連携、推論 token 数の増加に強く依存している。本研究ではそれとは別に、凍結済みモデルの内部状態遷移を観測・粗視化し、推論失敗の発生点を定量的に特定する。長期的には、hidden-state dynamics の理解から inference-time control / activation steering の設計原理を得ることを目標とする。

9月末発表では、制御そのものを主成果にはしない。主成果は「推論崩壊の動力学的診断」である。

## 2. 9月末までの中心命題

中心命題:

```text
LLM の推論崩壊は、出力上の誤答として現れる前に、
hidden-state trajectory の drift・滞留・final commit 失敗として観測できる。
```

この命題を、Pancake Sorting を主対象として検証する。比較対象として Hanoi を用い、余力があれば Lights Out または別パズルへ横展開する。

## 3. 到達目標

Minimum:

- Pancake Sorting N=3/N=4 で、探索中の全 `Flip k` mention と `<final>...</final>` 内の最終答案を分離して評価する。
- 代表モデル1つで、token-level hidden-state trajectory を取得する。
- 成功・失敗・no final・loop trap などの outcome label を付ける。
- PCA 上で hidden trajectory とイベント列を可視化する。

Target:

- full hidden pilot から有効な粗視化空間を決める。
- PCA 空間で経験的 drift / diffusion を推定する。
- 成功軌道、失敗軌道、loop trap 軌道の違いを定量化する。
- 初期または中盤 token 区間の dynamics 指標から最終成否を予測できるか検証する。

Stretch:

- Hanoi に同じ解析 pipeline を適用し、Pancake 固有ではない構造が見えるか確認する。
- PCA 後 trajectory を保存する軽量形式を設計し、trial 数を増やす。

Future:

- 推定した drift / failure mode に基づく activation steering または closed-loop control。
- 複数モデル、複数パズル、温度依存の広域相図。

## 4. 実験対象

主対象:

```text
Pancake Sorting
```

比較対象:

```text
Hanoi
```

余力:

```text
Lights Out
その他の状態遷移が厳密なパズル
```

代表モデル:

```text
deepseek-ai/DeepSeek-R1-Distill-Qwen-14B
```

モデル比較は9月末の主目的にしない。ただし、後から別モデルを走らせられるよう、実装は model_id / puzzle / N / temperature / seed を metadata に残す形にする。

## 5. 温度 T* の決め方

temperature は横に広げすぎない。まず小スイープで、成功・失敗が混在する境界付近の温度 T* を1つ選ぶ。

初期スイープ案:

```text
Pancake N=3: T = 0.0, 0.3, 0.6, 0.9, 1.0, 各 5 trials
Pancake N=4: T = 0.0, 0.3, 0.6, 0.9, 1.0, 各 5 trials
```

選択基準:

- N=4 で `final_accuracy` が 0.3-0.7 付近に入る。
- または `success_final` / `search_fail` / `no_final` / `loop_trap` が混在する。
- N=3 は成功寄りでもよい。N=3 成功軌道を基準軌道として使えるため。

T sweep 自体は主成果にしない。T* 決定のための前処理として扱う。

## 6. データ取得計画

本実験の基本 trial 数:

```text
各主要条件 50 trials
```

初期条件:

```text
Pancake N=3, T=T*, 50 trials
Pancake N=4, T=T*, 50 trials
```

余力:

```text
Pancake N=5, T=T*, 20 trials exploratory
Hanoi, 代表 N, T=T*, 50 trials
```

N=5 exploratory は、主成果を N=5 に広げるためではなく、N=4 までで観測される失敗が単なる token budget 不足か、十分な budget でも残る推論能力・軌道崩壊かを切り分ける補助実験として扱う。

初期案:

```text
Pancake N=5, T=T*, num_predict=4096, 5 trials
Pancake N=5, T=T*, num_predict=8192, 5 trials
```

この比較では `final_accuracy` だけでなく、生成自然文と debug JSON から以下を確認する。

- `done_reason == length` か。
- `<final>` が出たか。
- 全 `Flip k` mention の軌道で goal を通過したか。
- `first_goal_index` が token budget 内のどこにあるか。
- `v_trace` が goal 方向へ単調に近づいていたか、途中で離れたか。
- `repeated_state_ratio` が高く、loop/trap に滞留していないか。

4096 で止まった試行が 8192 で成功する、または 4096 の自然文上で明らかに正解軌道に乗っている場合、その試行は能力不足の失敗ではなく budget-censored trial として扱う。逆に 8192 でも goal に近づかない、同じ状態・手順に滞留する、または `<final>` で誤った手順へ commit する場合は、failure dynamics の主要対象に含める。

### 6.1 N と min_moves の切り分け

Pancake の `min_moves` は `N` と初期状態で決まる厳密な最短距離であり、温度や token budget では変わらない。現在の初期状態生成は goal から `scramble_depth=N` 回 flip する方式だが、短縮経路が存在するため `min_moves=N` には固定されない。

そのため、N sweep の結果は以下の効果が混ざる。

- `N`: stack 長、合法手候補数、状態表現の長さ。
- `min_moves`: 最短計画長。
- 初期状態固有の紛らわしさ: 反復しやすい軌道、局所的に良さそうな flip、near-goal からの逸脱。

N=5 exploratory の seed 1-5 は以下の構成になっている。

```text
N=5 seed1: min_moves=3
N=5 seed2: min_moves=3
N=5 seed3: min_moves=3
N=5 seed4: min_moves=3
N=5 seed5: min_moves=5
```

したがって、N=5 の結果だけを N 効果として読まない。次の補助実験では、温度をいったん `T=0.6` に固定し、N=3-5 で `min_moves` を層化した難易度セットを作る。まず seed を広めに列挙し、`(N, seed, initial_state, min_moves)` の候補表を作る。そのうえで、各 `min_moves` 層から代表初期状態を選ぶ。

実装仕様は `docs/research_state/pancake_stratified_sweep_spec.md` を正本にする。

既に確認できている候補例:

```text
N=4 seed1: initial=(2, 4, 1, 3), min_moves=4
N=4 seed2: initial=(4, 2, 3, 1), min_moves=4
N=4 seed8: initial=(3, 1, 4, 2), min_moves=4
```

比較の読み方:

- 同じ/近い `min_moves` で N を変える: stack 長・状態表現の増大が、同程度の計画長でも失敗を増やすか。
- 同じ N 内で `min_moves` を変える: 計画長が失敗・loop・budget censoring をどれだけ増やすか。
- 同じ `N`・近い `min_moves` 内の seed 差: 初期状態固有の failure dynamics を見る。

hidden 保存方針:

1. まず `capture-mode relative` で token 全体の時間発展を確認する。
2. すぐに少数の `capture-mode all` full hidden pilot を走らせる。
3. full hidden pilot で層ごとの差、PCA 寄与率、成功/失敗分離に効く層を確認する。
4. その結果に基づき、代表層または PCA 後 trajectory の軽量保存へ移る。

full hidden pilot の目安:

```text
N=3 success: 5 trajectories
N=4 success: 5 trajectories
N=4 failure: 5 trajectories
```

N=4 success が集まりにくい場合は、seed または T を調整して代表例を確保する。pilot は均等性よりも、典型的な成功・失敗軌道を見つけることを優先する。

## 7. Outcome Label

最初に固定する最低限の分類:

| label | 定義 |
|---|---|
| `success_final` | `<final>...</final>` 内の手順で goal に到達 |
| `search_success_final_fail` | 全 mention の軌道では goal を通過するが、final answer は失敗 |
| `search_fail` | 全 mention の軌道でも goal に到達しない |
| `no_final` | `<final>` block が存在しない、または final moves が空 |
| `length_stop` | token budget で終了 |
| `loop_trap` | 同じ状態・同じ move pattern への滞留が強い |
| `budget_censored_success_like` | token budget で終了したが、探索中に goal を通過、または自然文上で正解軌道に乗っている |
| `budget_censored_unknown` | token budget で終了し、成功/失敗/滞留の判定が自然文だけでは不十分 |

`loop_trap` は初期実装では簡単なしきい値でよい。

候補:

```text
repeated_state_count / max(1, len(moves_all_mentions)) > threshold
```

または、

```text
同じ subsequence, 例: Flip 2 -> Flip 3, が複数回繰り返される
```

しきい値は pilot data を見て決める。9月末発表では、loop trap の厳密なしきい値よりも、分類が軌道差を説明するかを重視する。

`length_stop` は一律に失敗として扱わない。特に `goal_reached_all_mentions == true` かつ `moves_final` が空の試行は、観測窓で final commit まで到達しなかった打ち切りデータとして分離する。発表時の failure breakdown では、能力不足・軌道崩壊・final commit 失敗と、budget censoring を混同しない。

## 8. 解析計画

### 8.1 イベント付き trajectory 可視化

token-level hidden state を PCA などで低次元化し、以下のイベントを重ねる。

- `Flip k` mention
- `<final>` 開始
- `</final>` 終了
- `</think>` 付近
- 全 mention 軌道で goal を初めて通過した token
- final answer の開始 token
- length stop / eos

まずは top layer、次に low/mid/top 比較、最後に full layer pilot から重要層を判断する。

### 8.2 Drift / diffusion 推定

PCA 後の状態を `z_t` とする。

```text
Δz_t = z_{t+1} - z_t
```

局所的に、

```text
b(z) = E[Δz_t | z_t ≈ z]
D(z) = E[Δz_t Δz_t^T | z_t ≈ z]
```

を推定する。

有効方程式:

```text
z_{t+1} = z_t + b(z_t) + ξ_t
```

連続時間近似:

```text
∂p(z,t)/∂t = -∇·(b(z)p(z,t)) + 1/2 ∇∇:(D(z)p(z,t))
```

9月末までの「方程式の実証」は、Fokker-Planck 方程式を完全に数値解することではなく、以下を示すことと定義する。

- 経験的 drift / diffusion が outcome ごとに異なる。
- drift field 上の流線や密度が、実際の trajectory ensemble と整合する。
- 初期または中盤の drift 指標が最終成否を予測する。

### 8.3 定量指標

優先する指標:

- `final_accuracy`
- `goal_reached_all_mentions`
- first passage time to goal in all mentions
- first passage time to `<final>`
- trajectory length before final
- repeated state ratio
- loop subsequence count
- PCA explained variance
- drift magnitude `||b(z)||`
- diffusion magnitude `tr D(z)`
- distance to success trajectory / success manifold
- early-window outcome prediction accuracy

## 9. 発表で見せる図

優先図:

1. 研究概念図  
   token generation → hidden trajectory → puzzle state trace → final answer

2. Pancake N=3 成功例  
   generated text の要約、`moves_all_mentions`、`moves_final`、`state_trace`

3. Pancake N=4 失敗例  
   `search_success_final_fail` / `no_final` / `loop_trap` の代表例

4. PCA hidden trajectory  
   success / failure / loop trap を同じ空間に重ね、イベントを marker で表示

5. Empirical drift field  
   背景に trajectory density または `-log p(z)`、矢印に drift、色に outcome

6. Failure mode breakdown  
   N=3/N=4 の label 割合

7. Early-window prediction  
   生成前半の trajectory 指標から最終成否をどれだけ予測できるか

## 10. 学習ロードマップ

### LLM 基本機構

- Transformer の residual stream / hidden state
- attention / MLP / layer norm
- logits, softmax, temperature sampling
- KV cache と token-by-token generation
- chat template, `<think>`, `<final>` formatting
- activation steering / representation engineering の基本

### 複雑系・非平衡系の数理

- 確率過程
- Markov 過程
- Langevin 方程式
- Fokker-Planck 方程式
- drift / diffusion
- first-passage time
- metastability
- entropy / entropy production
- order parameter / phase diagram

### データ駆動の力学系解析

- PCA / whitening
- density estimation
- clustering
- Markov State Model
- empirical drift-diffusion estimation
- Wasserstein distance / MMD / KL
- Dynamic Mode Decomposition / Koopman 解析
- 時系列分類

カオスや Lyapunov exponent は、最初から主役にしない。初期条件や温度摂動に対する軌道分岐が明確に見えた段階で導入する。

## 11. 週ごとのロードマップ

### Week 1

- Pancake final answer 分離の動作確認を完了する。
- `debug_prompt.py` で N=3/N=4 の代表例を確認する。
- T* 決定用の小スイープを走らせる。
- outcome label の初期集計を作る。

### Week 2

- token hidden 保存を relative で確認する。
- debug JSON と hidden NPZ を結合する解析スクリプト仕様を書く。
- PCA trajectory の最初の図を作る。
- イベント label を PCA 図に重ねる。

### Week 3

- full hidden pilot を走らせる。
- 層別 PCA / explained variance / outcome 分離を確認する。
- 本実験で使う粗視化空間を決める。

### Week 4

- Pancake N=3/N=4, T=T*, 50 trials を集める。
- success / failure / no_final / loop_trap の breakdown を作る。
- first passage time と repeated state ratio を集計する。

### Week 5

- drift / diffusion 推定を実装する。
- empirical drift field と density 図を作る。
- early-window outcome prediction を試す。

### Week 6

- Hanoi への最小横展開を行う。
- Pancake との共通点・差分を整理する。
- 発表スライドの骨子を作る。

### Buffer

- 追加実験。
- 図の作り直し。
- failure label の再定義。
- full hidden が重すぎた場合の軽量保存設計。

## 12. リスクとバックアップ

| リスク | 対応 |
|---|---|
| N=4 で成功/失敗が混在する T が見つからない | T 候補を増やす。seed 固定ではなく initial state を指定して難度を調整する。 |
| full hidden が重すぎる | relative で主解析を進め、full は代表例だけにする。 |
| PCA で軌道差が見えない | phase 別、層別、token window 別に見る。top layer だけでなく mid/low も確認する。 |
| drift/diffusion 推定がノイズに埋もれる | bin を粗くする。trajectory を phase ごとに分ける。first passage / repeated state など離散指標を主にする。 |
| Hanoi 横展開が間に合わない | Pancake の結果を主成果にし、Hanoi は preliminary にする。 |
| 方程式実証が弱い | `Δz_t = b(z_t) + ξ_t` の経験的推定と、outcome prediction までを最低ラインにする。 |

## 13. 実装時に別仕様書へ切り出す項目

- debug JSON と hidden NPZ の結合スキーマ
- full hidden pilot の保存形式
- PCA basis の fit / save / apply 手順
- PCA 後 trajectory の軽量保存形式
- `loop_trap` の定義としきい値
- token phase labeling の具体仕様
- drift/diffusion 推定スクリプトの入出力
- visual artifact の保存ディレクトリ規約

## 14. 9月以降の展望

- activation steering による推論軌道制御
- closed-loop control: hidden trajectory が failure basin に入りそうな時点で介入する
- 複数モデル比較
- 複数パズル横断の普遍性検証
- Fokker-Planck / Markov State Model / Koopman 解析の厳密化
- logical reasoning task への拡張
