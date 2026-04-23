# 02 ブランチ：並行作業と安全な実験

## ブランチとは

コミット履歴の「分岐点」。`main` を壊さずに新機能の開発や実験的な変更を試せる。

```
main:    ○ ── ○ ── ○ ──────────── ○  （安定版）
                    \            /
feature:             ○ ── ○ ── ○      （実験中）
```

ブランチは実体としてはコミットへの「ポインタ」に過ぎない。切り替えてもファイルは共有されず、作業ツリーが切り替わる。

## 基本コマンド

```bash
# ブランチ一覧（* が現在いるブランチ）
git branch
# * main

# ブランチを作成して切り替え（最もよく使う）
git switch -c feature/new-analysis
# -c: create の略。作成と切り替えを同時に行う

# 既存ブランチに切り替え
git switch main

# ブランチ一覧（リモートも含む）
git branch -a

# ブランチを削除（マージ済みのもの）
git branch -d feature/new-analysis
```

## HEAD とブランチの関係

```
main:    ○ ── ○ ── ○   ← main ポインタ
                    ↑
                   HEAD  ← 現在地（main にいるとき）

feature: ○ ── ○ ── ○ ── ○   ← feature ポインタ
                         ↑
                        HEAD  ← feature に切り替えた後
```

`git switch feature/xxx` すると `HEAD` が feature ブランチのポインタに移動し、作業ツリーがそのコミット時点の状態に切り替わる。

## この研究での使い方

**ブランチを切るべきタイミング：**

```bash
# Layer 2（スケーリング則実験）の設計を試すとき
git switch -c feature/layer2-scaling

# 既存のコードに影響する大きなリファクタリング
git switch -c refactor/early-stop-logic

# 新しい解析スクリプトの試作
git switch -c analysis/p-spin-fitting
```

**`main` に直接コミットしてよいケース：**
- ドキュメントの追加・修正
- `.gitignore` の更新
- 小さなバグ修正（1〜2行）

---

### 実践例：新しい解析を安全に試す

```bash
# 1. 現在の状態を確認
git status
git switch main
git pull origin main          # 最新の main に合わせる

# 2. 作業ブランチを作成
git switch -c analysis/slowing-down

# 3. 作業する
# analysis/analyze_slowing.py を編集...

# 4. こまめにコミット
git add analysis/analyze_slowing.py
git commit -m "add critical slowing detection near T_c"

# さらに作業...
git add analysis/analyze_slowing.py figures/
git commit -m "add variance plot for order parameter fluctuation"

# 5. main に戻って確認
git switch main
# → analysis/analyze_slowing.py は変更前の状態に戻る（main には影響なし）

# 6. 問題なければ main にマージ（→ 03_merge 参照）
```

## ブランチの命名規則

| プレフィックス | 用途 | 例 |
|---|---|---|
| `feature/` | 新機能・新実験 | `feature/layer2-scaling` |
| `analysis/` | 解析スクリプトの追加 | `analysis/p-spin-fitting` |
| `fix/` | バグ修正 | `fix/move-loop-detection` |
| `refactor/` | リファクタリング | `refactor/early-stop-logic` |
| `docs/` | ドキュメントのみ | `docs/add-lcm-hypothesis` |

## 作業の中断と再開

作業途中でブランチを切り替えたいとき、コミットしたくない変更は `stash` で一時退避できる：

```bash
# 作業中断：変更を一時退避
git stash
# → 作業ツリーがきれいになる（変更は stash に保存）

git switch main    # 別ブランチに切り替え可能に

# 作業再開：退避した変更を戻す
git switch analysis/slowing-down
git stash pop
```
