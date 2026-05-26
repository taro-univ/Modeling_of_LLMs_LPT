# Open Questions

未解決の論点。**未定項目は未定として明示し、勝手に埋めない**。

論点が解消したら `research_state/hypotheses.md` または `todo.md` に移動して本ファイルから削除する。

---

## 理論／モデリング

### U1：L2（隠れ状態空間）の次元縮約方針

$d \sim 4096$ の hidden state をそのままハミルトニアンや RSB 解析の対象にはできない。次元縮約方針は**未定**。

候補（フィジックスエージェントへ委譲予定）：

- (i) **層選択での縮約**：`make_capture_layers` の top/mid/low のいずれかに絞る（既に取得済み）
- (ii) **線形射影**：PCA / probing classifier で「正解方向」「ループ方向」など低次元部分空間を抽出
- (iii) **低次元秩序変数の手構築**：`evaluate_state` の $V(x)$ を hidden state から線形回帰で読み出した $\hat V(h)$ を 1 次元秩序変数化
- (iv) **collective variable**：移動ステップ間の hidden state 差分 $\Delta h_t$ のノルム・自己相関のような巨視量
- (v) **格子模型への粗視化**：トークン列レベルの離散変数（move 系列）を Ising/Potts スピンに対応

### U2：SG 相の判定基準

現在は早期終了ラベル `move_loop_*` を SG 相のシグナルとして暫定採用しているが、$P(q)$ 分布との関係が**定式化されていない**。

- $P(q)$ がどのような形（裾の重さ、双峰性、$q_\text{EA}$ の有限性等）なら SG と判定するか
- ラベルベースの分類と $P(q)$ ベースの分類が一致するか

→ `todo.md` P1 で着手予定。

### U3：臨界指数 $\alpha$ の抽出

$T_c(N) = A \cdot N^{-\alpha}$ の指数 $\alpha$ を統計的に有意に抽出するには現状の試行数では不足。**仮説本体からは外している**（`hypotheses.md` 棚上げ参照）。

データが大幅に増えた段階で復活検討。

### U4：制御外力 ↔ 推論時駆動の対応付け

H4 段階 2。**最終フェーズの抽象論点**。

シミュレーション上の制御外力 $f$ を実 LLM 推論にどう「翻訳」するか。プロンプト介入／hidden state ベクトル加算（steering）／サンプリング温度の動的調整／logit ブースト のいずれが対応するかは、シミュレーション結果が出るまで判断保留。

### U5：介入レベルの選択

制御モデルがどのレベルで介入するかは**未定**。

- (a) モニタ型（検出のみ）
- (b) プロンプトレベル（few-shot やヒント注入）
- (c) 隠れ状態レベル（steering vector）
- (d) サンプリングレベル（温度・top-p のオンライン調整／logit ブースト）

シミュレーション結果に応じて決定する方針。

---

## 実装／実験

### U6：1 sweep の実時間

未計測。`results/hanoi/.../meta.json` の timestamp から推定可能なはずだが未着手。

### ~~U7：14B 級モデルの 12GB VRAM 適合性~~（解消済み）

deepseek-r1-distill-qwen-14B の NF4 量子化で RTX 5070 12GB へのロード・生成が**実機確認済み**（full_sweep・collapse_phase の全試行が完走）。Qwen3-14B は未確認だが同サイズ帯なので問題ないと想定。

### U8：他パズルの具体的選定

「解が一意」以外は制約なし、と決めたが**具体的なパズル名は未確定**。リサーチエージェントが候補を提案 → user が決定する流れ。

候補例（参考、未承認）：sliding puzzle、迷路、論理パズル、簡単な数式の逆算、グラフ探索の最短路問題、など。

---

### U10：ハミルトニアンの相互作用次数 $p$ の決定（2026-05-25 追加）

physics-agent 審査で球面 $p$-スピン型が推奨枠組みとなったが、$p$ の値が未確定。

- $p=2$: 標準 Hopfield。Tc2 の N 非依存性を説明できない
- $p=3$: LLM の attention（Q×K×V）が3次相互作用であることから物理的に示唆的
- $p \to \infty$: Modern Hopfield / softmax attention に対応（Ramsauer et al. 2020）

各 $p$ で Tc1/Td/Tc^stat の解析的表式が異なる。Crisanti-Sommers (1992) の結果を参照して決定する。

→ リサーチエージェントへの依頼案件（Crisanti-Sommers 1992、Cugliandolo-Kurchan 1993）

### U11：記憶パターン $\xi^\mu$ の同定方法（2026-05-25 追加）

推奨 Hamiltoian の実証フィットには $\xi^1$（正解経路）と $\xi^{\mu>1}$（ループ basin）の同定が必要。

- $\xi^1$: goal_reached trial の hidden state を Move 完了ステップで平均する（経験的方針）
- $\xi^{\mu>1}$: move_loop_repeat trial をループパターン (src, dst) でクラスタリングし、各クラスタ内の hidden state を平均する

→ user の方針確認待ち（open_questions.md U10 と並行）

### U12：球面拘束の実測検証（2026-05-25 追加）

推奨 Hamiltonian の球面拘束（$\|h\|^2 = d$）の根拠として LayerNorm/RMSNorm を挙げたが、実際に hidden state のノルムが層内でほぼ一定か未検証。

既取得 npz から $\|h^\alpha\|$ の分布を N, T, layer（top/mid/low）ごとに測定して確認する。

→ 小規模追加実験で確認可能。実施前に U10/U11 の方針が固まってから着手。

---

## 既存リソース・サーベイ

### U9：「LLM × 統計力学」既存研究の体系的サーベイ

- 既に意識している文献：西森スピングラス、散逸構造、Hopfield is All You Need、Apple 推論崩壊論文（読み進め中）
- 系統的サーベイは未実施 → リサーチエージェント着手案件

重複研究の回避と、本研究の novelty positioning のため必要。
