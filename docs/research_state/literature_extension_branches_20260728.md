# Literature Extension Branches 2026-07-28

目的: `roadmap_2026_09_conference.md` の主線を保ったまま、関連論文から出た拡張実験案を branch 的に管理する。

この文書は正本ロードマップではない。主線へ入れる前の候補、依存関係、merge 条件、git 運用を明示するための作業台である。

## 1. 基本方針

ロードマップ本体は 2026年9月末発表までの main branch として扱う。

```text
mainline:
  T* 決定
  Pancake N=3/N=4 hidden pilot
  debug JSON と hidden NPZ の結合
  PCA trajectory
  outcome/event 別 drift-diffusion
  early-window prediction
```

関連論文から出た追加案は、すぐに本体へ混ぜない。まずこの文書で extension branch として管理し、実験的に有効だったものだけをロードマップへ merge する。

## 2. 採用判断と実行順

2026-07-28 時点の判断:

| item | 判断 | 扱い |
|---|---|---|
| `length_stop` と failure の分離 | 確定 | ロードマップ本体へ反映済み |
| failure onset oracle | 採用。ただし entropy 導入時に実装 | Extension B |
| token-hidden-event 統合テーブル | 採用。N=3 hidden pilot の次 | mainline/Extension A-B の接続 |
| entropy metrics | 採用。failure onset oracle とセット | Extension B |
| phase labeling | 採用。ただし hidden/PCA pilot 後 | Extension A |
| failure onset timeline 図 | 採用 | Extension B の成果図 |
| PCA 次元数選定 | 採用 | Extension C のうち最優先 |
| one-step prediction | 保留。主線優先 | Extension C の中優先 |
| jump norm / autocorrelation / occupancy | 保留。主線優先 | Extension C の中優先 |
| ablation | 保留。時間発展式を固めた後 | Extension C の中-低優先 |
| SLDS / regime switching | future / stretch | Extension C の後段 |
| false-state commitment | 後回し | 指標不足を感じた段階で検討 |
| general benchmark probe | pipeline 固定後に試す | Extension D |

推奨実行順:

```text
1. N=4 sweep 完了
2. T* 決定
3. N=5 budget 比較
4. Pancake min_moves 層化 debug sweep
5. N=3 min_moves=3 success hidden pilot
   - `--capture-timing token:8`
   - `--capture-mode relative`
   - trials=5
6. token-hidden-event 統合
7. PCA trajectory prototype
8. PCA 次元数選定
9. phase labeling prototype
10. entropy metrics + failure onset oracle
11. PCA trajectory + event/phase marker
12. failure onset timeline
13. drift/diffusion 推定
14. 必要なら one-step prediction / jump statistics / ablation
15. SLDS は余力または9月以降
16. general benchmark probe は pipeline 固定後
```

## 3. Extension A: Reasoning Phase Labeling

Source:

```text
Hidden Markov Modeling of Reasoning Dynamics in Large Language Models
```

狙い:

生成文を一様な text として扱わず、reasoning role / phase の遷移として分解する。Pancake では hidden trajectory と puzzle state trace に加えて、自然文上の役割遷移を同期させる。

Status:

```text
adopted after N=3 hidden/PCA pilot
```

Priority:

```text
medium-high
```

この extension は採用するが、最初の実行対象からは外す。まず N=3 min_moves=3 の成功例で `token:8`・3 relative layers の hidden trajectory を取得し、PCA と event annotation の pipeline を固める。その後、生成文から rule-based phase label が安定して付くかを確かめる。

理由:

- 確率的な時間発展を見る初期解析では、phase/event 周辺だけを過密に capture するより、`token:8` の均一サンプリングを正本にする方がよい。
- event / phase は最初は capture criterion ではなく、最寄り captured token への後処理 annotation とする。
- phase labeling を先に入れると、hidden dynamics より自然文分類の設計が前面に出すぎる。

初期 label 候補:

| label | 意味 |
|---|---|
| `problem_restatement` | 問題文・初期状態・goal の再記述 |
| `state_simulation` | stack 状態や Flip 後状態のシミュレーション |
| `move_proposal` | 候補手順の提案 |
| `verification` | 手順の検算・正しさ確認 |
| `backtracking` | "wait", "try again" などの戻り・修正 |
| `self_correction` | 以前の方針の明示的訂正 |
| `final_commit` | `<final>...</final>` 内の最終提出 |
| `loop_like` | 同じ状態・同じ move pattern の反復 |

最初は HMM を実装しない。`<think>`, `<final>`, `Flip k`, 検算語彙、訂正語彙などによる rule-based label で十分とする。

Mainline dependency:

```text
Pancake min_moves 層化 debug sweep 完了
N=3 min_moves=3 success hidden pilot 完了
token-hidden-event 統合と PCA trajectory prototype 完了
```

Merge condition:

- 代表 trial を目視して、phase label が解釈可能である。
- `success_final`, `search_success_final_fail`, `budget_censored_success_like`, `loop_trap` の違いを説明する助けになる。
- label が主観的すぎず、最低限のルールで再現できる。

Risk:

- 自然文 label がモデル・温度・プロンプトに依存しすぎる。
- phase labeling が本筋の hidden dynamics より前面に出すぎる。

Git branch:

```bash
git switch -c exp/pancake-phase-labeling
```

想定ファイル:

```text
analysis/label_pancake_reasoning_phases.py
docs/research_state/pancake_phase_labeling_spec.md
```

## 4. Extension B: Entropy / Critical Transition

Source:

```text
Dissecting Failure Dynamics in Large Language Model Reasoning
```

狙い:

token-level entropy spike を、critical transition の観測信号として hidden trajectory と puzzle event に重ねる。

Status:

```text
adopted after phase labeling
```

Priority:

```text
high, but not immediate
```

failure onset oracle はこの extension で実装する。Pancake/Hanoi では外部 LLM oracle ではなく、厳密な puzzle state transition と距離関数を oracle として使う。

failure onset 候補:

| event | 定義 |
|---|---|
| `first_wrong_move` | 最短/妥当な goal 方向から外れた最初の move |
| `first_distance_increase` | `v_trace` が悪化した最初の move |
| `first_goal_exit` | goal 到達後に goal から離れた最初の move |
| `first_final_error` | `<final>` 内で最初に誤った move |
| `loop_onset` | 状態反復または move pattern 反復が始まる点 |

これらは entropy metrics 保存後に、entropy spike との token lag を測るために使う。

Runner 側で保存する候補:

| metric | 定義 |
|---|---|
| `token_entropy` | `H_t = -sum_v p_t(v) log p_t(v)` |
| `top1_prob` | `max_v p_t(v)` |
| `sampled_token_prob` | 実際に sample された token の確率 |
| `logit_margin` | top1 logit と top2 logit の差 |

Analysis 側で計算する候補:

| metric | 意味 |
|---|---|
| `entropy_spike_count` | trial 内 entropy spike 数 |
| `entropy_at_flip` | `Flip k` mention 直前/直後の entropy |
| `entropy_before_first_wrong_move` | 正解軌道から逸脱する直前の entropy |
| `entropy_before_final` | `<final>` 開始前の entropy |
| `entropy_after_first_goal` | goal 到達後の wandering 時 entropy |
| `entropy_spike_to_event_lag` | spike から critical event までの token lag |

Mainline dependency:

```text
hidden/logits capture の実装タイミング
debug JSON と hidden NPZ の結合仕様
```

Merge condition:

- entropy 系 metric の保存コストが許容範囲である。
- N=3/N=4 small pilot で entropy timeline が出る。
- entropy spike が `Flip` 逸脱、`final_commit` 失敗、または `length_stop` 前の滞留と対応する兆候がある。
- entropy だけでなく hidden drift / puzzle event との結合で解釈できる。

Risk:

- entropy spike が単なる punctuation / formatting / tokenization boundary に強く反応する。
- 低エントロピーで自信を持って間違える failure もあり、entropy だけでは不十分。

Git branch:

```bash
git switch -c exp/pancake-entropy-metrics
```

想定ファイル:

```text
runners/run_local.py
tests/test_hidden_state_capture.py
analysis/plot_pancake_entropy_timeline.py
docs/research_state/pancake_entropy_metrics_spec.md
```

## 5. Extension C: Drift-Diffusion Validation / SLDS

Source:

```text
A Statistical Physics of Language Model Reasoning
```

狙い:

Fokker-Planck 方程式を直接解くことを主目的にせず、低次元 hidden trajectory の経験的 drift-diffusion モデルが、実際の軌道統計と task-level failure statistics をどこまで再現・予測できるかを検証する。

Status:

```text
partial adoption
```

Priority:

```text
medium
```

採用済み:

- PCA 次元数を統計的に決める。
- event/outcome 別の経験的 drift/diffusion を推定する。

保留:

- one-step prediction
- jump norm / autocorrelation / occupancy
- ablation

future / stretch:

- SLDS / regime switching

PCA 次元数は、40次元を機械的に真似しない。Pancake/Hanoi の hidden pilot で、以下を見て決める。

| criterion | 内容 |
|---|---|
| explained variance | 累積寄与率と各主成分の落ち方 |
| spectral gap | 固有値の段差 |
| visualization stability | 2D/3D 図の安定性 |
| downstream utility | outcome/event 分離や early-window prediction への効き |

初期候補:

```text
2D: 発表図
10D: 軽量 drift/diffusion
20-40D: validation / SLDS 候補
```

最初に行う検証:

| validation | 内容 |
|---|---|
| one-step prediction | `z_t` から `z_{t+1}` を予測し、R2 / MSE を見る |
| jump norm reproduction | 実軌道と生成/予測軌道の `||z_{t+1}-z_t||` 分布を比較 |
| autocorrelation | PCA coordinate や jump norm の自己相関を比較 |
| occupancy | success / failure / loop-like region の滞在頻度を比較 |
| first-passage statistics | `first_goal`, `final_start`, failure basin 到達時刻を比較 |
| early-window prediction | 生成前半の dynamics 指標から final outcome を予測 |

アブレーション候補:

| ablation | 確認すること |
|---|---|
| no phase | phase/event 条件なしで drift を推定 |
| no entropy | entropy 系 metric を外す |
| no puzzle event | `Flip`, `first_goal`, `final` marker を外す |
| no regime switching | 単一線形 dynamics で十分か |
| no PCA / high-D direct | 低次元化なしでノイズが増えるか |

SLDS は stretch とする。9月末の最低ラインは、event/outcome 別の経験的 drift-diffusion と early-window prediction まで。

Mainline dependency:

```text
PCA trajectory が保存済み
N=3 success / N=4 mixed hidden pilot がある
```

Merge condition:

- held-out trial で one-step prediction または early-window outcome prediction が baseline を上回る。
- `success_final`, `search_success_final_fail`, `loop_trap`, `budget_censored_success_like` の少なくとも一部が dynamics 指標で分離する。
- 発表に載せられる図が1つ以上できる。

Risk:

- SLDS 実装が重く、9月末本線を圧迫する。
- PCA 空間が outcome 分離に不十分な場合、validation が弱くなる。
- Markov性や低次元閉包の仮定が強すぎる。

Git branch:

```bash
git switch -c exp/pancake-slds-validation
```

想定ファイル:

```text
analysis/fit_pancake_hidden_pca.py
analysis/measure_pancake_drift_diffusion.py
analysis/validate_pancake_dynamics.py
docs/research_state/pancake_drift_diffusion_validation_spec.md
```

## 6. Extension D: General Benchmark Probe

Source:

```text
A Statistical Physics of Language Model Reasoning
Dissecting Failure Dynamics in Large Language Model Reasoning
```

狙い:

Pancake/Hanoi で評価指標と測定量の pipeline が固まった後、一般的な推論 benchmark に最小横展開できるかを試す。目的は主成果の置き換えではなく、toy problem criticism への備えと外的妥当性の確認である。

Status:

```text
future validation extension
```

Priority:

```text
low-medium
```

候補:

```text
MATH500
GSM-8K
StrategyQA
```

注意:

- 一般 benchmark では厳密な puzzle state oracle がない。
- failure onset 検出に外部 judge / oracle が必要になる。
- 9月末の主張は、Pancake/Hanoi の厳密状態遷移に基づく診断へ置く。

Merge condition:

- Pancake/Hanoi の解析 pipeline が固定済み。
- entropy / phase / hidden trajectory の最低限の測定が一般 benchmark でも走る。
- 結果が preliminary として主線を補強する。

Git branch:

```bash
git switch -c exp/general-benchmark-probe
```

想定ファイル:

```text
analysis/probe_general_benchmark_entropy.py
docs/research_state/general_benchmark_probe_plan.md
```

## 7. Git 運用

### 7.1 Branch categories

| branch prefix | 用途 |
|---|---|
| `docs/` | 文書だけの整理・仕様化 |
| `exp/` | 実験的解析・runner 拡張 |
| `fix/` | 既存機能のバグ修正 |
| `results/` | 実験結果整理・レポート作成 |

例:

```bash
git switch -c docs/literature-extension-branches
git switch -c exp/pancake-entropy-metrics
git switch -c exp/pancake-phase-labeling
git switch -c exp/pancake-slds-validation
git switch -c exp/general-benchmark-probe
```

### 7.2 Merge policy

ロードマップ本体へ merge する条件:

- 主線の目的に沿う。
- 追加の測定量・label・解析が、failure mode の説明力を上げる。
- テストまたは小規模 smoke test が通る。
- 保存容量・実行時間の増加が許容範囲である。
- `docs/research_state/` に仕様または結果メモが残っている。

merge しない条件:

- 面白いが9月末発表の主張に直結しない。
- label や metric の解釈が不安定。
- 実装が重く、T* 決定・hidden pilot・PCA 図作成を遅らせる。
- 既存結果との比較が難しい形で runner output schema を壊す。

### 7.3 Commit granularity

1 commit に混ぜるべきでないもの:

- 文書変更と runner 実装。
- runner 実装と大きな実験結果。
- phase labeling と entropy metrics。
- hidden schema 変更と PCA 解析実装。

推奨 commit 単位:

```text
docs: add literature extension branch plan
docs: specify pancake entropy metrics
exp: save token entropy in hidden capture npz
analysis: add pancake entropy timeline plot
analysis: add phase labeling prototype
analysis: add drift-diffusion validation metrics
```

### 7.4 Result handling

大きな実験結果は、branch 上で生成しても commit する前に確認する。

原則:

- small summary CSV/JSON と report markdown は commit 候補。
- 数GB級 hidden NPZ は commit しない。
- `results/debug_prompt/` の代表例は、必要なときだけ report に要約する。
- figure は発表に使う候補だけ commit する。

## 8. Roadmap への反映ルール

拡張案は、以下の状態を持つ。

| status | 意味 |
|---|---|
| `proposed` | 論文から出た案。未実装 |
| `pilot` | 小規模実装・少数 trial で確認中 |
| `candidate` | 発表に使えそうな結果が出た |
| `merged` | ロードマップ本体へ採用済み |
| `deferred` | 9月末後へ延期 |
| `rejected` | 本線と合わない、または効果が弱い |

ロードマップ本体には、`candidate` 以上になったものだけを具体タスクとして追加する。`proposed` / `pilot` はこの文書に留める。

## 9. References

- Jack David Carson, "A Statistical Physics of Language Model Reasoning", ICML 2025 R2-FM Workshop. https://icml.cc/virtual/2025/50932
- Wei Zhu, Jian Zhang, Lixing Yu, Kun Yue, Zhiwen Tang, "Dissecting Failure Dynamics in Large Language Model Reasoning", ACL 2026. https://aclanthology.org/2026.acl-long.401/
- Ruidi Chang, Jiawei Zhou, Hanjie Chen, "Hidden Markov Modeling of Reasoning Dynamics in Large Language Models", OpenReview / ICLR 2026 submission. https://openreview.net/forum?id=fr9t7r43am
