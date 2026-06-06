# 05 この研究でのワークフロー

## 基本方針

| ブランチ | 役割 |
|---|---|
| `main` | 動く状態が保証されたコード。実験結果 JSON も含む |
| `feature/xxx` | 新機能・実験的な変更。壊れていても構わない |

`main` には動作確認済みのものだけをマージする。

## シナリオ①：新しい解析スクリプトを追加する

```bash
# 1. main を最新にする
git switch main
git pull origin main

# 2. ブランチを作成
git switch -c analysis/p-spin-hamiltonian

# 3. 作業（こまめにコミット）
# analysis/analyze_pspin.py を新規作成...
git add analysis/analyze_pspin.py
git commit -m "add p-spin Hamiltonian parameter estimation"

# もう少し作業...
git add analysis/analyze_pspin.py figures/
git commit -m "add J_p vs N plot"

# 4. main に統合
git switch main
git merge analysis/p-spin-hamiltonian

# 5. GitHub に push
git push origin main

# 6. ブランチを削除
git branch -d analysis/p-spin-hamiltonian
```

## シナリオ②：実験スクリプトを変更して実験を回す

run_hf.py に手を入れるのは影響が大きいのでブランチで保護する。

```bash
git switch -c feature/layer2-qwen14b

# run_scaling_sweep.sh や run_hf.py を修正...
git commit -am "support Qwen-14B model in scaling sweep"

# Docker コンテナで実験実行
docker compose exec hanoi-minimal bash runners/scripts/run_scaling_sweep.sh --model Qwen14B --dry-run

# 結果が出たら summary.json もコミット
git add results/hanoi/scaling/
git commit -m "add Qwen14B scaling sweep results (N=2-5)"

# main にマージして push
git switch main
git merge feature/layer2-qwen14b
git push origin main
git branch -d feature/layer2-qwen14b
```

## シナリオ③：試した変更を捨てる

ブランチで作業していれば `main` は無傷。

```bash
git switch -c experiment/try-new-early-stop

# いろいろ変更したが結局うまくいかなかった...

# ブランチごと捨てる（-D は強制削除）
git switch main
git branch -D experiment/try-new-early-stop

# → main は変更前の状態のまま
```

## コミット前のチェックリスト

```bash
# 何が変わっているか確認
git status
git diff --staged

# テスト（実験スクリプトが動くか）
docker compose exec hanoi-minimal python3 runners/run_hf.py --N 2 --trials 2 --no-save-hidden

# コミット
git commit -m "..."
```

## よく使うコマンド早見表

```bash
# 現在地の確認
git status
git log --oneline --graph --all    # 全ブランチの履歴をグラフで表示

# ブランチ操作
git switch -c feature/xxx          # 作成して切り替え
git switch main                    # main に戻る
git branch -d feature/xxx          # ブランチ削除（マージ済み）
git branch -D feature/xxx          # ブランチ強制削除

# 変更の記録
git add <file>                     # ステージ
git add -p                         # 変更を選んでステージ（対話的）
git commit -m "..."                # コミット
git commit -am "..."               # 追跡済みファイルを全部コミット

# 取り消し
git restore <file>                 # 作業ツリーの変更を取り消す（コミット前）
git restore --staged <file>        # ステージを取り消す（コミット前）
git revert <commit>                # コミットを打ち消す新コミットを作る（履歴は消えない）

# リモート
git pull origin main               # リモートの最新を取り込む
git push origin main               # リモートに送る
git push -u origin feature/xxx     # 新しいブランチを初めて push

# 一時退避
git stash                          # 変更を一時退避
git stash pop                      # 退避した変更を戻す

# 確認
git show <commit>:<file>           # 特定コミット時点のファイルを見る
git log --oneline -10              # 最新10コミットを表示
git diff main..feature/xxx         # ブランチ間の差分
```

## NG 操作

```bash
# push 済みコミットを rebase しない（他の人の履歴が壊れる）
git rebase origin/main  # ← ローカルブランチのみに使う

# --force push は原則しない（共有リポジトリでは特に）
git push --force origin main  # ← 禁止

# main で直接大きな変更をコミットしない
# → 必ずブランチを切る
```
