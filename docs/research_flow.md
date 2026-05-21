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
  ├─ physics-agent     → Section 2（物理的要件）を埋める
  ├─ research-agent    → Section 3（関連文献）を埋める
  └─ implementation-agent → Section 4（アルゴリズム仕様・設計案）を埋める
  │
  ▼
Stage 2: 壁打ち（user ↔ orchestration）
  ├─ 保存則・対称性の確認
  ├─ アルゴリズムの詳細詰め
  ├─ 再現性情報の確定
  └─ 議事録: specs/log/<spec_id>/round*.md に記録
  │
  ▼
Stage 3: 仕様書清書・確定
  ├─ draft/ → final/ にコピー
  └─ status: final に更新
  │
  ▼
Stage 4: 実装
  ├─ implementation-agent: final 仕様書を読んでから実装開始
  └─ 完了後に commit_hash を Section 5 に記録
  │
  ▼
Stage 5: 検証
  ├─ quality-check-agent: コードレビュー（仕様書との照合含む）
  └─ physics-agent: 物理式が含まれる場合は事後確認
  │
  ▼
Stage 6: テスト → 実行
  ├─ pytest 全テスト PASS
  └─ チェックリスト完了 → 実行
```

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

### 壁打ちの終了条件

以下がすべて満たされた時点で Stage 3 に進む：

- physics-agent 判定が「合格」または「条件付き合格（条件が明示されている）」
- アルゴリズムの意図と実装の境界が user に確認済み
- 再現性情報（Section 5）が全項目埋まっている（commit_hash 以外）

---

## Stage 3: 仕様書清書・確定

```bash
cp specs/draft/<spec_id>.md specs/final/<spec_id>.md
```

`specs/final/<spec_id>.md` の frontmatter を更新：

```yaml
status: final
finalized: YYYY-MM-DD
```

> **ルール**: `specs/final/` に入った仕様書は原則変更しない。
> 変更が必要な場合は新ラウンドの壁打ちを経て更新する。

---

## Stage 4: 実装

`implementation-agent` は実装開始前に必ず `specs/final/<spec_id>.md` を読む。
実装完了後：

1. `git commit` を行い、commit hash を Section 5 の `commit_hash` に記録する
2. `status: implemented` に更新する

---

## Stage 5: 検証

### quality-check-agent のチェック項目（仕様書照合分）

- Section 4（アルゴリズム仕様）通りに実装されているか
- Section 2（物理的要件）の保存則・対称性が実装で担保されているか
- Section 5（再現性情報）が完全に記録されているか（commit_hash を含む）

### physics-agent の事後確認（該当時）

物理式（ハミルトニアン、ポテンシャル、外力、秩序変数）が含まれる実装の場合、
physics-agent が実装後に Section 2 との整合性を確認する。

---

## Stage 6: テスト → 実行

```bash
# コンテナ内で
python3 -m pytest tests/ -v
# 全テスト PASS 後に実行
```

---

## よくある間違いと防止策

| ❌ やりがちな間違い | ✅ 防止策 |
|---|---|
| physics-agent 審査前に実装を始める | Stage 2.5 の判定が `合格` になるまで Stage 4 に進まない |
| 壁打ちの議事録を残さずに仕様書を更新する | 仕様書の変更は必ず round*.md を起点にする |
| 再現性情報（seed, commit hash）を記録しないまま実行する | Section 5 が埋まっていることを Stage 3 完了条件に含める |
| `specs/final/` の仕様書を実装中に変更する | final はロックとみなし、変更は壁打ち経由のみ |
| アルゴリズムと実装の境界が曖昧なまま実装に入る | Stage 2 の「決定事項」に必ず境界を明記する |
