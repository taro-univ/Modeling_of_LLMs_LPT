# 研究ノート運用とセッション開始フロー

作成日: 2026-07-27

目的: 思いつきで実験が散らばること、一気にやろうとして疲れることを避け、最小の努力量で研究成果を最大化するための運用を定義する。

## 1. 基本方針

研究ノートは「全部考える場所」ではなく、「今日の実験・実装・理論作業を1つに絞るための道具」として使う。

重要な原則:

- 1日1ゴールだけ決める。
- 実験は走らせる前に Question と Stop rule を書く。
- 思いつきは捨てずに Idea Parking へ逃がす。
- 毎日の最後に Result / Next を3行だけ書く。
- 週1回だけ棚卸しする。

## 2. ノートのページ構成

前から:

```text
Daily Page
Experiment Page
```

後ろから:

```text
Idea Parking
用語メモ
論文メモ
```

清書しない。見返せる程度でよい。色分けや装飾に時間を使わない。

## 3. Daily Page

毎日1ページ。作業開始前に書く。

```text
Date:
Today’s one goal:
Time budget:
Energy: high / mid / low

Must:
Can:
Don’t:

End condition:
```

例:

```text
Date: 2026-07-28
Today’s one goal:
Pancake N=3/N=4 の T* 候補を出す。

Time budget: 2h
Energy: mid

Must:
- debug sweep script を作る
- small sweep を開始する
- final_accuracy / no_final / loop_trap を集計する

Can:
- relative token hidden smoke を1本だけ走らせる

Don’t:
- full hidden に入らない
- activation steering に入らない
- Koopman / Lyapunov に広げない
- 3パズル横展開をしない

End condition:
T* 候補と次の実験条件を1つ書く。
```

`Don’t` は特に重要。興味が広がったときに、その日の作業範囲を守るために使う。

## 4. Experiment Page

実験ごとに1ページ。走らせる前に必ず書く。

```text
Experiment:
Question:
Expected outcomes:
Command / config:
Success criteria:
Stop rule:
Result:
Next:
```

例:

```text
Experiment:
Pancake T* small sweep

Question:
N=4 で成功/失敗が混在する temperature はどこか。

Expected outcomes:
- T=0.0 は成功寄りまたは no_final 寄り
- T=0.6/0.9 で混在する可能性

Command / config:
N = 3, 4
T = 0.0, 0.3, 0.6, 0.9, 1.0
trials = 5
num_predict = 4096

Success criteria:
T* 候補を1つ選べる。

Stop rule:
各 T 5 trials 以上は今日は増やさない。

Result:
...

Next:
...
```

`Stop rule` は必須。面白くなって追加で試し続けることを防ぐ。

## 5. Idea Parking

作業中に出た思いつきは、すぐ実行せずここへ逃がす。

```text
Idea:
Why interesting:
Cost: S / M / L
When to revisit:
```

例:

```text
Idea:
activation steering で loop_trap から抜けられるか。

Why interesting:
hidden-state dynamics の制御に直結する。

Cost:
L

When to revisit:
9月発表後、または drift 指標ができた後。
```

目的は「今やらないが捨てない」こと。発想を殺さず、当日の作業は散らさない。

## 6. 理論・論文メモ

長くまとめすぎない。自分の実験で使う形だけ書く。

```text
Concept:
Definition:
How used in my experiment:
Figure idea:
```

例:

```text
Concept:
first-passage time

Definition:
軌道が特定の領域またはイベントに初めて到達する時刻。

How used in my experiment:
hidden trajectory が <final> 領域または goal passage に到達する token を測る。

Figure idea:
success / failure で first-passage time の分布を比較する。
```

## 7. セッション開始フロー

新しい作業セッションでは、Codex/Claude は次の順番で進める。

1. 最新 handoff を読む。
2. `docs/research_state/roadmap_2026_09_conference.md` と `docs/research_state/todo.md` を必要に応じて確認する。
3. 今日の候補タスクを、実験・実装・理論に分けて提示する。
4. ユーザーと今日の one goal / Must / Can / Don’t / End condition に合意する。
5. 研究ノートに書くべき Daily Page と Experiment Page の内容を提示する。
6. 合意した範囲だけ実行する。
7. 作業中に出た追加アイデアは Idea Parking に送る。
8. 終了時に Result / Next を整理し、必要なら handoff を更新する。

## 8. セッション終了フロー

終了時に必ず確認する。

```text
今日の one goal は達成したか。
達成していないなら、どこで止まったか。
次にやるべき1手は何か。
Idea Parking に逃がすべき思いつきは何か。
handoff に残すべき変更・実験・観測は何か。
```

終了時の最小記録:

```text
Result:
- ...

Next:
- ...

Park:
- ...
```

## 9. 改善点・注意

- 合意前に「今日やらないこと」を必ず決める。
- 実験を追加する場合は、既存の Stop rule を破る理由を書く。
- 大きな理論展開は、実験結果に必要になった段階で入れる。
- full hidden や activation steering のような重い作業は、Daily Page の `Can` ではなく、別日の `Today’s one goal` にする。
- 週1回だけ、Idea Parking を `Kill / Park / Continue` に分ける。

週次レビュー:

```text
This week found:
This week failed:
Next week one theme:
Kill / Park / Continue:
```
