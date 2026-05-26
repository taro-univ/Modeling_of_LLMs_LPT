# 01 Git基礎：リポジトリ・スナップショット・ステージング

## Git とは何か

ファイルの変更履歴を記録するバージョン管理システム。
「いつ・誰が・何を・なぜ変えたか」を保存し、任意の時点に戻れる。

```
時間 →
○ ── ○ ── ○ ── ○   コミット（スナップショット）の連なり
初回  追加  修正  現在
```

## 3つの領域

Git のファイル管理は3段階になっている：

```
作業ツリー（Working Tree）
  ↓ git add
ステージング（Index / Stage）
  ↓ git commit
リポジトリ（.git/）
```

| 領域 | 場所 | 説明 |
|---|---|---|
| **作業ツリー** | プロジェクトフォルダ | 実際に編集するファイル |
| **ステージング** | `.git/index`（内部） | 「次のコミットに含める」と宣言した変更の一時置き場 |
| **リポジトリ** | `.git/`（内部） | 確定したスナップショットの全履歴 |

## 基本コマンド

### 状態確認

```bash
git status
# 作業ツリーとステージングの状態を表示
# Changes to be committed: ステージ済み（次のコミットに含まれる）
# Changes not staged:      変更があるがステージされていない
# Untracked files:         Git が知らない新規ファイル
```

```bash
git log --oneline
# コミット履歴を1行で表示
# 1c5772c add some documents and Guide
# daefc80 Add README: ...
# 58192d4 Initial commit: ...
```

```bash
git diff                  # 作業ツリー vs ステージング（まだ add していない変更）
git diff --staged         # ステージング vs 最新コミット（add 済みの変更）
```

### ステージング → コミット

```bash
# ファイルをステージに追加
git add runners/run_hf.py
git add db/                      # ディレクトリごと
git add -p                       # 変更を部分的に選んでステージ（対話的）

# コミット（スナップショットを確定）
git commit -m "add temperature sweep to run_hf.py"
```

**コミットメッセージの書き方：**
- 何をしたかより **なぜしたか** を書く
- 動詞から始める（add / fix / refactor / update）
- 50文字以内が理想

```bash
# ステージせずに追跡済みファイルを全部コミット（新規ファイルは含まない）
git commit -am "fix early stop detection for disk loop"
```

## .gitignore

Git に無視させるファイルのリスト。このプロジェクトの `.gitignore`：

```gitignore
results/**/*.npz     # 隠れ状態ベクトル（大容量・再生成可能）
figures/             # グラフ画像（再生成可能）
__pycache__/         # Python のバイトコードキャッシュ
.claude/             # Claude Code の個人設定
.env                 # 秘密情報（パスワード等）
```

`.gitignore` に書いたファイルは `git add .` でもステージされず、`git status` にも出ない。

## コミットの確認と移動

```bash
# 特定のコミット時点のファイルを見る
git show 58192d4:runners/run_hf.py

# 特定のコミット時点に作業ツリーを戻す（履歴は消えない）
git checkout 58192d4

# main の最新に戻る
git checkout main
```

## このプロジェクトの現在地

```bash
git log --oneline
# 1c5772c add some documents and Guide   ← HEAD（現在地）
# daefc80 Add README: ...
# 58192d4 Initial commit: ...
```

`HEAD` は「今自分がいるコミット」を指すポインタ。
