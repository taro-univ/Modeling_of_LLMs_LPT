# 研究フロー ガイド

このファイルはアイデアを実験・モデリング実装に落とし込む標準ワークフローを定義する。
仕様書の置き場は [`specs/`](../specs/README.md)。

---

## フロー概観

```
User（アイデア投入）
  │
  ▼
Stage 1: ドラフト仕様書作成
  ├─ physics-agent        → Section 2（物理的要件）を埋める
  ├─ research-agent       → Section 3（関連文献）を埋める
  └─ implementation-agent → Section 4（アルゴリズム仕様・設計案）を埋める
  │
  ▼
Stage 2: 壁打ち（user ↔ orchestration）
  ├─ 保存則・対称性の確認
  ├─ アルゴリズムの詳細詰め
  ├─ 再現性情報の確定
  └─ 議事録: specs/log/<spec_id>/round*.md に記録
  │
  ⛔ GATE A ── ユーザーが「壁打ち終了・final 移行OK」を宣言するまで止まる
  │            Claude は自律的に final に昇格させない
  │
  ▼
Stage 3: 仕様書清書・確定（specs/final/ へ移動）
  │
  ⛔ GATE B ── final 仕様書の全文をユーザーに提示し、承認を得る
  │            「Codex を起動してよいですか？」を必ず確認する
  │            承認なしに codex コマンドを実行しない
  │
  ▼
Stage 4: 実装（Codex CLI に委譲）         ┐
  └─ codex --task-file specs/final/<id>.md │ 自律ゾーン
      --agent-profile .claude/agents/...   │ Claude/Codex が
      --auto-approve                        │ 自由に進める
  │                                         │ ユーザー割り込みなし
  ▼                                         │
Stage 5: 検証                              │
  ├─ quality-check-agent: コードレビュー    │
  └─ physics-agent: 物理式の事後確認        ┘
  │
  ⛔ GATE C ── pytest PASS + 検証レポートをユーザーに提示して止まる
  │            「実験を実行してよいですか？」を必ず確認する
  │            承認なしに run_local.py / sweep スクリプトを実行しない
  │
  ▼
Stage 6: 実験実行（run_local.py / sweep）
```

### ゲートの運用ルール

| ゲート | 停止条件 | Claude が提示するもの | 次に進む条件 |
|---|---|---|---|
| **GATE A** | Stage 2 終了後 | 壁打ちの決定事項まとめ・未解決事項一覧 | ユーザーが「final に移してOK」と明示 |
| **GATE B** | Stage 3 完了後 | `specs/final/<spec_id>.md` の全文 | ユーザーが「Codex 起動OK」と明示 |
| **GATE C** | Stage 5 完了後 | pytest 結果・quality-check 報告・physics 審査結果 | ユーザーが「実験GO」と明示 |

---

## Stage 1: ドラフト仕様書作成

### Orchestration（メインセッション）の動き

1. `specs/_template.md` をコピーして `specs/draft/SPEC-YYYY-MM-DD-NNN.md` を作成
2. Section 1（目的・動機）を user の説明から記述
3. physics-agent・research-agent・implementation-agent を（可能なら並行）起動
4. 各エージェントの出力を仕様書の対応 Section に転記

### 各エージェントへの依頼テンプレート

```
# physics-agent へ
仕様書 specs/draft/<spec_id>.md の Section 2（物理的要件）を埋めてください。
Section 1 の目的・動機を読んで、保存則・極限値・整合性・懸念点を記入し、判定を出してください。

# research-agent へ
仕様書 specs/draft/<spec_id>.md の Section 3（関連文献）を埋めてください。
Section 1 の目的と hypothesis_refs を読んで、先行研究・novelty・実装ヒントを調査してください。

# implementation-agent へ
仕様書 specs/draft/<spec_id>.md の Section 4（アルゴリズム仕様）を埋めてください。
Section 1〜3 を読んで、擬似コード・既存コードとの接続点・設計制約を記入してください。
この段階では実装しないこと。
```

---

## Stage 2: 壁打ち

### 議事録フォーマット

`specs/log/<spec_id>/round<N>.md` に以下の形式で記録する：

```markdown
# <spec_id> Round <N> — YYYY-MM-DD

## このラウンドの確認事項
<!-- 壁打ち開始時の未解決・要確認事項 -->

## 議論の要約
<!-- やり取りの要約（発言の逐語録は不要） -->

## 決定事項
<!-- このラウンドで確定した内容 -->

## 次ラウンドへの持ち越し
<!-- まだ詰まっていない点 -->
```

### 壁打ちの終了条件（必要条件）

以下がすべて揃った段階で、**Claude はユーザーに確認を促す（GATE A）**。
終了の最終判断はユーザーが行う。

- physics-agent 判定が「合格」または「条件付き合格（条件が明示されている）」
- アルゴリズムの意図と実装の境界がユーザーに確認済み
- 再現性情報（Section 5）が全項目埋まっている（commit_hash 以外）

> **⛔ GATE A**：条件が揃っても、ユーザーが「final に移してOK」と言うまで
> `specs/draft/` から `specs/final/` に移動しない。

---

## Stage 3: 仕様書清書・確定

GATE A 通過後、orchestration が以下を行う：

```bash
cp specs/draft/<spec_id>.md specs/final/<spec_id>.md
```

`specs/final/<spec_id>.md` の frontmatter を更新：

```yaml
status: final
finalized: YYYY-MM-DD
```

**清書完了後、Orchestration は仕様書の全文をユーザーに提示し、以下を確認する：**

```
仕様書 <spec_id> を specs/final/ に移動しました。
全文を確認してください。

[specs/final/<spec_id>.md の内容をここに貼る]

問題なければ「Codex 起動OK」とお知らせください。
```

> **⛔ GATE B**：ユーザーが「Codex 起動OK」と明示するまで `codex` コマンドを実行しない。
>
> **ルール**: `specs/final/` に入った仕様書は原則変更しない。
> 変更が必要な場合は新ラウンドの壁打ちを経て更新する。

---

## Stage 4: 実装（Codex CLI への委譲）

GATE B 通過後、orchestration が以下のコマンドを実行して Codex に委譲する：

```bash
codex --task-file specs/final/SPEC-YYYY-MM-DD-NNN.md \
      --agent-profile .claude/agents/implementation-agent.md \
      --auto-approve
```

**Orchestration はこのフェーズで Edit/Write を使用しない。** コードの変更はすべて Codex が行う。

Codex（実装エージェント）は `AGENTS.md` の指示に従い：

1. 仕様書 Section 1〜3 を読み、目的・物理要件・文献を把握する
2. Section 4 のアルゴリズム仕様・擬似コード・接続点を精読する
3. 接続先ソースファイルを確認し既存コードを把握する
4. Section 4 の設計に従いコードを実装する
5. `python3 -m pytest tests/ -v` を実行し PASS を確認する
6. `git commit` し、commit hash を Section 5 に記録する
7. `status: implemented` に更新する

---

## Stage 5: 検証（自律ゾーン）

Stage 4 完了後、orchestration が以下を自律的に実行する（ユーザー割り込みなし）：

### quality-check-agent のチェック項目

- Section 4（アルゴリズム仕様）通りに実装されているか
- Section 2（物理的要件）の保存則・対称性が実装で担保されているか
- Section 5（再現性情報）が完全に記録されているか（commit_hash を含む）
- OOP 設計・拡張耐性・命名・テスト網羅に問題がないか

### physics-agent の事後確認（該当時）

物理式（ハミルトニアン、ポテンシャル、外力、秩序変数）が含まれる実装の場合、
physics-agent が実装後に Section 2 との整合性を確認する。

### GATE C への到達

Stage 5 完了後、orchestration はユーザーに以下を提示して止まる：

```
Stage 4〜5 完了報告

【pytest 結果】
  ... （全テストの PASS/FAIL 一覧）

【quality-check-agent 報告】
  ... （指摘事項または「問題なし」）

【physics-agent 事後確認】（該当時）
  ... （整合性確認結果）

【commit hash】
  <hash>

実験を実行してよいですか？
```

> **⛔ GATE C**：ユーザーが「実験GO」と明示するまで
> `run_local.py` / sweep スクリプトを実行しない。

---

## Stage 6: 実験実行

GATE C 通過後、オーケストレーションは **Pipeline Orchestrator エージェント** に委譲する。

> **Stage 6 の鉄則**：GATE C 通過後はオーケストレーションが直接スクリプトを叩かない。
> 必ず Pipeline Orchestrator（`.claude/agents/pipeline-orchestrator.md`）を `Agent(subagent_type="general-purpose", ...)` で起動し、以下の情報を渡す。

```python
# オーケストレーション → Pipeline Orchestrator への委譲（Claude Code 内で実行）
Agent(
    subagent_type="general-purpose",
    description="Run sweep + post-processing",
    prompt="""
You are the Pipeline Orchestrator. Follow the instructions in
.claude/agents/pipeline-orchestrator.md exactly.

Parameters for this run:
- model_list: ["<model_id_1>", "<model_id_2>", ...]
- sweep_type: "full_sweep"   # or "collapse_phase_sweep" or "both"
- trials: 25
- run_pq_classify: true

Execute Phase 1 → Phase 2 → Phase 3 → Phase 4 in order.
Report back with the completion report from Phase 4.
"""
)
```

**単発実験（スイープではなく 1 条件のみ確認したい場合）はオーケストレーションが直接実行してよい：**

```bash
docker compose exec hanoi-minimal bash -c \
    "PYTHONPATH=/app python3 runners/run_local.py --N 3 --trials 5 --temperature 0.6"
```

---

## よくある間違いと防止策

| ❌ やりがちな間違い | ✅ 防止策 |
|---|---|
| 壁打ちの条件が揃ったら自動で final に移動する | GATE A：ユーザーの「OK」を待つ |
| final を書いたらすぐ Codex を起動する | GATE B：仕様書全文を提示してユーザーの「OK」を待つ |
| pytest PASS したらすぐ実験を走らせる | GATE C：検証レポートを提示してユーザーの「GO」を待つ |
| physics-agent 審査前に実装を始める | physics 判定が「合格」になるまで GATE A を通過しない |
| 壁打ちの議事録を残さずに仕様書を更新する | 仕様書の変更は必ず round*.md を起点にする |
| 再現性情報（seed, commit hash）を記録しないまま実行する | Section 5 が埋まっていることを GATE A の確認事項に含める |
| `specs/final/` の仕様書を実装中に変更する | final はロックとみなし、変更は壁打ち経由のみ |
| Orchestration が直接 Edit/Write でコードを変更する | Stage 4 以降のコード変更は Codex に委譲する |
