---
spec_id: SPEC-YYYY-MM-DD-NNN
type: experiment | modeling | analysis
status: draft
hypothesis_refs: []
proposed: YYYY-MM-DD
finalized:
implemented:
---

# [タイトル]

## 1. 目的・動機
<!-- user が記述。どの仮説（H*）を検証・進展させるか、なぜ今か。
     対応する仮説番号を hypothesis_refs にも記入すること。 -->

---

## 2. 物理的要件【physics-agent 担当】

### 2.1 保存則・対称性の要件
<!-- 実験・モデルが満たすべき保存則、対称性、不変量 -->

### 2.2 極限値チェック項目
<!-- T→0, T→∞, N→∞, N=1 など、物理的に自明であるべき極限での挙動 -->

### 2.3 スピングラス・Hopfield・RSB との整合性
<!-- スピングラス理論的に満たすべき性質（P(q) の裾、q_EA、非自己平均性、超計量性など） -->

### 2.4 懸念点・要確認（物理）
<!-- physics-agent が指摘した要確認事項。壁打ちで詰める項目 -->

### 2.5 physics-agent 判定
- **判定**: 未審査
- **審査日**:
- **コメント**:

---

## 3. 関連文献【research-agent 担当】

### 3.1 直接関連する先行研究
<!-- 著者, タイトル, 年, URL（arxiv ID / DOI）, 重要度（高/中/低） -->

### 3.2 novelty 観点での位置づけ
<!-- 本研究との差分。何が既存にあって何がないか -->

### 3.3 実装ヒントになる文献
<!-- 実装チームへの理論ヒント -->

### 3.4 research-agent 確認
- **確認日**:
- **補足コメント**:

---

## 4. アルゴリズム仕様【implementation-agent 担当】

### 4.1 擬似コード / フロー
```
(擬似コードをここに記述)
```

### 4.2 既存コードとの接続点
<!-- どのファイル・関数を呼ぶか。何を新規作成するか。ファイルパス:行 で具体的に -->

### 4.3 設計上の制約・注意事項
<!-- OOP設計、拡張耐性、ModelProfile の継承など -->

### 4.4 implementation-agent 設計確認
- **確認日**:
- **コメント**:

---

## 5. 再現性情報

| 項目 | 値 |
|---|---|
| model_id | |
| temperature | |
| N | |
| trials | |
| random_seed | |
| device | |
| sweep_type | |
| docker_image | |
| commit_hash（実行時） | |

---

## 6. 壁打ち参照
<!-- 議事録は specs/log/<spec_id>/ に格納 -->

| ラウンド | ファイル | 日付 | 主な決定事項 |
|---|---|---|---|
| Round 1 | specs/log/SPEC-YYYY-MM-DD-NNN/round1.md | | |

---

## 7. 最終チェックリスト

### Stage 1 完了条件（ドラフト）
- [ ] physics-agent: Section 2 記入・判定済み
- [ ] research-agent: Section 3 記入済み
- [ ] implementation-agent: Section 4 記入済み

### Stage 2〜3 完了条件（壁打ち → 確定）
- [ ] 壁打ち完了（user 確定）
- [ ] status を `final` に更新
- [ ] `specs/final/<spec_id>.md` にコピー済み

### Stage 4〜6 完了条件（実装 → 実行）
- [ ] 実装完了（commit_hash を Section 5 に記録）
- [ ] quality-check-agent: レビュー合格
- [ ] physics-agent: 事後確認（物理式を含む場合）
- [ ] pytest: 全テスト PASS
- [ ] 実行完了

---

## 8. 変更履歴

| 日付 | 変更内容 | 担当 |
|---|---|---|
| YYYY-MM-DD | ドラフト作成 | user |
