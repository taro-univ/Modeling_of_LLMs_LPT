# specs/ — 仕様書管理

詳細なフロー定義は [`docs/research_flow.md`](../docs/research_flow.md) を参照。

## ディレクトリ構造

```
specs/
  _template.md      ← 仕様書テンプレート（コピーして使う）
  draft/            ← 壁打ち中の作業中仕様書
  final/            ← 確定仕様書（実装の正式な根拠）
  log/              ← 壁打ち議事録（<spec_id>/ サブディレクトリ単位）
```

## ライフサイクル

```
draft/<spec_id>.md を作成（_template.md をコピー）
  │
  ├─ physics-agent     → Section 2 を埋める
  ├─ research-agent    → Section 3 を埋める
  └─ implementation-agent → Section 4 を埋める
  │
  ▼
壁打ち（specs/log/<spec_id>/round*.md に記録）
  │
  ▼
draft/ → final/ にコピー（status: final に更新）
  │
  ▼
実装 → quality-check → pytest → 実行
```

## 命名規則

| 要素 | 規則 | 例 |
|---|---|---|
| spec_id | `SPEC-YYYY-MM-DD-NNN` | `SPEC-2026-05-21-001` |
| ファイル名 | `<spec_id>.md` | `SPEC-2026-05-21-001.md` |
| 壁打ち議事録 | `specs/log/<spec_id>/round<N>.md` | `specs/log/SPEC-2026-05-21-001/round1.md` |

## ステータス一覧

| status | 意味 |
|---|---|
| `draft` | 作成中・エージェント入力待ち |
| `review` | 壁打ち中 |
| `final` | user 確定済み・実装可能 |
| `implemented` | 実装完了・テスト PASS |
| `archived` | 完了または破棄 |
