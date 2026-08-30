# Pancake phase annotation rule

作成日: 2026-08-29  
位置づけ: Pancake generated completionのphase annotationにおける正本。

## 1. 目的

Pancake推論文を意味的なphaseに分割し、half-open char span
`[char_start, char_end)`からtoken spanとlayer 48 hidden rowへ同期する。

phaseの意味判定はCodex/LLMに候補作成を委譲してよい。ただし、決定的harnessによる
整合性検証と、人間による意味境界の確認・修正を必須とする。最終的な解析入力は、
人間が承認し保存したannotation artifactである。

## 2. annotation unitと不変条件

- primary phaseは相互排他とする。
- generated completion全体をgapとoverlapなしで分割する。
- char spanとtoken spanはhalf-open `[start, end)`とする。
- 意味的なepisodeを1 segmentとし、連続する同一phaseはまとめる。
- 原則として段落先頭を境界候補とする。段落内で機能が明確に変わる場合は、
  exact char boundaryで分割してよい。
- char境界がtoken内部を横切る場合は自動的に丸めず、境界を再審査する。
- annotation中はoutcome labelを見ない。outcomeはannotation完了後の解析でのみ結合する。

## 3. primary phase codebook

### `setup`

問題、操作、初期状態、目標の確認。探索中に問題と現在状態を完全に再提示した
局所的resetも含めてよい。

### `plan`

複数手にわたる戦略、algorithm、またはsubgoalの順序を設定・変更する。
単一のFlip候補や「Flip 4はどうか」という局所探索は含めない。

### `move_proposal`

現在の探索地点から、具体的な1手または短いFlip候補を提案する局所探索。
結果状態を実際に計算し始めた地点からは`state_simulation`とする。

### `state_simulation`

Flip後の具体的なstackを計算し、現在状態や状態列を追跡する。

### `verification`

状態、正しさ、進捗、目標到達、または手数を検査する。局所的な事実訂正が主の場合は
`self_correction`を優先する。

### `backtracking`

現在の探索枝を明示的に捨て、以前の状態や別戦略の開始点へ戻る。
単に別の局所手を並べるだけなら`move_proposal`とする。

### `self_correction`

直前の局所的な状態計算、手数、記述、または事実認識の誤りを訂正する。
探索枝全体を捨てる場合は`backtracking`とする。

### `loop_like`

既出の状態、Flip列、または議論を、新しい進展なしに反復する。replay上の
`repeated_state`は強い証拠だが、決定的eventと意味的な`loop_like` phaseは同一ではない。
判断根拠を`evidence_note`に残す。

### `final_commit`

実際の提出として使われる`<final>...</final>` block。推論文中でタグ名として
`<final>`に言及しただけの箇所は含めない。open finalは、実際の提出が始まり
EOFで打ち切られた場合に限り、開始tagからEOFまでを`final_commit`とする。

## 4. 境界判断の優先順位

同一段落に複数機能が混在する場合は、可能なら境界を分割する。分割が不自然な場合は、
次の優先順位と段落の支配的機能でprimary labelを決める。

```text
final_commit
-> self_correction
-> backtracking
-> loop_like
-> verification
-> state_simulation
-> move_proposal
-> plan
-> setup
```

`plan` / `move_proposal` / `state_simulation`の判断は次の順で行う。

1. 複数手の方針やsubgoal順序を設定する: `plan`
2. 具体的なFlip候補を出す: `move_proposal`
3. 候補後のstackを計算する: `state_simulation`

## 5. Codex/LLMへの委譲手順

1. 本ruleを最初に読む。
2. `generated.txt`、char位置付きreview text、必要な場合だけ`replay_v1.json`を読む。
3. outcome、PCA/UMAP座標、または比較対象の正解ラベルを見ずに候補境界を作る。
4. `phase_boundaries_manual_v1.csv`の対象trialだけを編集する。
5. 決定的harnessを実行する。
6. 人間が特に`plan` / `move_proposal`、`backtracking`、`loop_like`、final境界を確認する。
7. 修正があれば本fileの修正ログとCSVを同時に更新し、harnessを再実行する。
8. 人間の承認後にのみ、outcomeと結合して解析する。

## 6. 決定的harnessの必須検証

- generated text SHA-256が保存値と一致する。
- `generated_token_ids.npy`と同一revisionのretokenize結果が完全一致する。
- labelがcodebook内の9種類のどれかである。
- `segment_index`が0から連続する。
- char spanがcompletion全体をgap/overlapなしで分割する。
- token spanがtoken列全体をgap/overlapなしで分割する。
- char境界がtoken内部を横切らない。
- layer 48 hidden row数とgenerated token数が一致する。
- token span `[a, b)`のphase後状態を`hidden[b]`へ対応させる。
- `b == generated_token_count`ではafter-phase hidden rowを利用不可とする。

## 7. 修正ログの記録形式

意味ラベルまたは境界を人間が修正した場合、次を残す。

```text
Date:
Trial:
Segment / char span:
Before:
After:
Reason:
Reviewer:
Harness result:
```

## 8. 修正ログ

### 2026-08-29: seed 528 char 1724

```text
Date:
2026-08-29

Trial:
N5_mm5_state03_trial008_seed528

Segment / char span:
segment 8 / [1724, 1946)

Before:
plan

After:
move_proposal

Reason:
「2を近づけるにはFlip 4はどうか」という局所的な候補手の生成であり、
複数手にわたる戦略やsubgoal順序の設定ではない。

Reviewer:
human-reviewed Codex draft

Harness result:
passed: 94 segments、9-label constraint、continuous index、
char/token boundaryが整合。labelのみの変更で境界は不変。
```
