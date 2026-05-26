# 03 マージ：ブランチの統合とコンフリクト解消

## マージとは

あるブランチの変更を別のブランチに取り込む操作。

```bash
# feature ブランチの変更を main に取り込む
git switch main
git merge feature/layer2-scaling
```

**マージは「取り込まれる側」のブランチにいて実行する。**

## マージの種類

### Fast-forward マージ（分岐がない場合）

```
main:    ○ ── ○
                \
feature:         ○ ── ○ ── ○

↓ git merge feature

main:    ○ ── ○ ── ○ ── ○ ── ○
                              ↑
                           main が追いつくだけ
```

`main` 側に変更がなければ、ポインタを前に進めるだけ（マージコミットは作られない）。

### 3-way マージ（分岐がある場合）

```
main:    ○ ── ○ ── ○ ── M   ← マージコミット
                  \    /
feature:           ○ ── ○
```

両方のブランチが独立して進んでいる場合、差分を統合してマージコミットが作られる。

## コンフリクト（競合）

同じファイルの同じ箇所を両ブランチで別々に変更したとき発生する。

```bash
git merge feature/new-analysis
# CONFLICT (content): Merge conflict in analysis/analyze_phase_diagram.py
# Automatic merge failed; fix conflicts and then commit the result.
```

コンフリクトが起きたファイルの中身：

```python
<<<<<<< HEAD                          # main 側の変更
BOUNDARY_THRESHOLD = 0.5
=======                               # ← 区切り線
BOUNDARY_THRESHOLD = 0.4             # feature 側の変更
>>>>>>> feature/new-analysis
```

### コンフリクトの解消手順

```bash
# 1. コンフリクトしているファイルを確認
git status
# both modified: analysis/analyze_phase_diagram.py

# 2. ファイルを編集して正しい状態にする
#    <<< === >>> のマーカーを全て消して、残したい内容に書き換える

# 3. 解消したファイルをステージ
git add analysis/analyze_phase_diagram.py

# 4. マージコミットを作成
git commit -m "merge feature/new-analysis: use 0.4 threshold"

# マージを中止したい場合（元の状態に戻す）
git merge --abort
```

## マージ前の確認

```bash
# feature が main に対してどんな変更をしているか確認
git diff main..feature/new-analysis

# どのコミットが追加されるか確認
git log main..feature/new-analysis --oneline
```

## マージ後の後片付け

```bash
# マージが完了したらブランチを削除（履歴は main に残る）
git branch -d feature/layer2-scaling

# リモートのブランチも削除
git push origin --delete feature/layer2-scaling
```

## rebase（マージの代替）

マージコミットを作らず、ブランチを `main` の先端に「付け替える」操作。

```
main:    ○ ── ○ ── ○
                  \
feature:           ○ ── ○

↓ git rebase main（feature ブランチにいる状態で）

main:    ○ ── ○ ── ○
                    \
feature:             ○'── ○'  ← コミットが付け替えられた（' は書き換えを示す）
```

```bash
git switch feature/new-analysis
git rebase main         # main の最新に追従させる
git switch main
git merge feature/new-analysis  # fast-forward でクリーンに統合できる
```

**使い分け：**

| | merge | rebase |
|---|---|---|
| 履歴 | 分岐・統合の記録が残る | 直線的でシンプル |
| 用途 | feature → main の統合 | feature を main に追従させる |
| 注意 | マージコミットが増える | push 済みのコミットには使わない |

このプロジェクト規模では `merge` だけ使えば十分。
