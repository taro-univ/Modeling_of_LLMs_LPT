# 04 リモート：GitHub との同期

## リモートとは

GitHub などのサーバー上にあるリポジトリ。`origin` という名前で登録されている。

```bash
git remote -v
# origin  git@github.com:taro-univ/Modeling_of_LLMs_LPT.git (fetch)
# origin  git@github.com:taro-univ/Modeling_of_LLMs_LPT.git (push)
```

`origin` はリモートリポジトリへの「ニックネーム」。

## ローカルとリモートの関係

```
GitHub (origin)
  └── origin/main   ← リモートのブランチ（ローカルにコピーされた追跡ブランチ）

ローカル
  └── main          ← 自分の手元のブランチ
```

`origin/main` はリモートの状態を反映したローカルのコピー。`git fetch` で更新される。

## 基本コマンド

### push — ローカル → リモート

```bash
git push origin main
# ローカルの main を origin（GitHub）の main に送る

# ブランチを初めてリモートに送るとき
git push -u origin feature/layer2-scaling
# -u: upstream を設定（以降は git push だけで OK になる）
```

### pull — リモート → ローカル（fetch + merge）

```bash
git pull origin main
# origin/main の最新をローカルの main に取り込む
# = git fetch + git merge origin/main の組み合わせ
```

### fetch — リモートの状態をローカルに反映（マージはしない）

```bash
git fetch origin
# リモートの変更をダウンロードするだけ
# ローカルの作業ツリーは変わらない

git log origin/main --oneline   # リモートの最新を確認してから
git merge origin/main           # 手動でマージ
```

`pull` は `fetch` + `merge` を一括でやる。
確認してからマージしたい場合は `fetch` を使う。

## よく使うパターン

### 作業開始前に最新を取り込む

```bash
git switch main
git pull origin main    # 最新の状態にする
git switch -c feature/new-experiment
```

### 作業後に push する

```bash
git add analysis/analyze_slowing.py
git commit -m "add variance divergence near T_c"
git push origin feature/new-experiment
```

### main を最新に保つ

```bash
git switch main
git pull origin main
```

## push が拒否されるケース

```bash
git push origin main
# ! [rejected] main -> main (non-fast-forward)
# hint: Updates were rejected because the tip of your current branch is behind
```

リモートに自分が知らない新しいコミットがある場合に起きる。

対処：
```bash
git pull origin main    # リモートの変更を取り込む（コンフリクトが出たら解消）
git push origin main    # 再度 push
```

## このプロジェクトの運用

```
GitHub (origin/main)
    ↑ push（実験ログ・コード確定後）
ローカル main
    ← pull（作業開始前）
    ↑ merge（ブランチ作業完了後）
ローカル feature/xxx
    （実験的な変更・新機能）
```

`.gitignore` の設定により：
- `results/**/*.npz`（隠れ状態・大容量）→ push されない
- `figures/`（グラフ）→ push されない
- `results/**/*.json`（実験サマリ）→ push される（軽量・解析に必要）
- `docs/`、`runners/`、`analysis/` → push される
