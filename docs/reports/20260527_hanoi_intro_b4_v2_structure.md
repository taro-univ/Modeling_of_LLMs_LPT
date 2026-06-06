# 構成表 — 20260527_hanoi_intro_b4_v2

**report_type:** progress
**output_stem:** 20260527_hanoi_intro_b4_v2
**stage:** structure（Stage 1 完了）
**元ファイル:** docs/reports/20260525_hanoi_intro_b4.md（25 枚）
**生成日:** 2026-05-27

---

| スライド番号 | タイトル | レイアウト種別 | 主要コンテンツ（箇条書き） | 数式 | 図 |
|---|---|---|---|---|---|
| 1 | LLMの推論行き詰まりを統計力学で測る | title | - メインタイトル: 「LLMの推論行き詰まりを統計力学で測る」 / - サブタイトル: 「Tower of Hanoi 実験による相転移の観測」 / - 発表者名・日付 | — | — |
| 2 | 今日話す内容 | toc | - 今日のゴール（LLMの推論挙動を物理で測る第一歩） / - 話す内容4点（行き詰まり現象→統計力学枠組み→実験結果→制御モデルへの道筋） / - 現在地を示すフロー図（現在地→相転移の観測→ハミルトニアン構築→制御モデル） | — | — |
| 3 | LLM って何をしているの？ | text | - LLMはトークン単位で確率的に次を予測する機械 / - 温度パラメータ $T$ がランダム性を制御（低$T$=保守的、高$T$=暴走気味） / - コード例:「ハノイの塔の第1手は」→「ディスク1をCに移す」 / - 「賢く見えるが複雑な問題では行き詰まる」 | $T$ | — |
| 4 | LLMが行き詰まる現象 | text | - 現象1: move loop（同じ手の繰り返し）のコード例 / - 現象2: no move（手が出ない）のコード例 / - なぜ重要か → 行き詰まりを検出・回避すれば推論品質が上がる / - 物理学のフレームワークで記述・制御する | — | — |
| 5 | Tower of Hanoi をパズルに選んだ理由 | text | - ルール説明（3本の棒、$N$枚のディスク、一度に1枚のみ移動） / - 初期状態→ゴール状態の ASCII 図 / - 選んだ理由3点: 解が一意・$N$で難しさを調節可能・状態空間の構造が明確 | $K(N) = 2^N - 1$ | — |
| 6 | 実験設定の概要 | table | - 制御パラメータ表（$T$: 0.2〜2.0、$N$: 2〜6） / - 測定量: 正解率 $m$（25試行）・隠れ状態 $\mathbf{h}$（$d \sim 4096$次元・3層）・early_stop ラベル / - 対象モデル: DeepSeek-R1-Distill-Qwen-7B（現在解析完了） | $T$, $N$, $m$, $\mathbf{h}$ | — |
| 7 | early_stop とは何か | table | - early_stop の5ラベル定義表（goal_reached / move_loop_repeat / move_loop_reverse / no_move_catchall / move_ceiling） / - 各ラベルの対応する相（Ordered / SG / PM） / - 直感的なイメージ（Ordered=正解、SG=ループ、PM=完全ランダム） | — | — |
| 8 | 相転移とは何か？（統計力学の直感） | text | - 水の相変化の比喩（氷→水→水蒸気）のASCII図 / - LLMの推論でも同じことが起きている仮説 / - Ordered→SG→PMの対応（正解→ループ→無手） / - $T$と$N$を変えて「状態」の切り替わりを調べる | $T$ | — |
| 9 | スピングラスとは何か？（B4向け直感） | text | - 通常の磁石（全スピン同方向=秩序）のASCII図 / - スピングラス（ランダム相互作用でバラバラ）のASCII図 / - スピングラスの特徴3点（メタ安定状態が多数存在・初期条件依存・外から見ると不定だが内部に構造） / - LLMのmove loopとの対応（ポテンシャルの局所的谷） | — | — |
| 10 | 理論枠組み ─ ハミルトニアンの定義 | equation | - LLM推論を「エネルギーポテンシャル上を動く粒子」としてモデリング / - Hopfield型ハミルトニアンの定義式と各記号の説明 / - 秩序変数 $m$（磁化に対応）の定義式 / - $m \to 1$: 秩序相、$m \to 0$: 無秩序相 | [block] $\mathcal{H}(\mathbf{h}) = -\frac{1}{2N_p} \sum_{\mu=1}^{K(N)} \left( \boldsymbol{\xi}^{\mu} \cdot \mathbf{h} \right)^2$; [block] $m = \frac{1}{R} \sum_{a=1}^{R} \mathbf{1}[\text{trial } a \text{ が正解}]$ | — |
| 11 | P(q) とは何か？ | equation | - 「試行間の隠れ状態の似ている度を分布にしたもの」の説明 / - 重複 $q_{ab}$ の定義式（コサイン類似度） / - Edwards-Anderson 秩序変数 $q_{EA}$ の定義式 / - $P(q)$ 分布の形状と相の対応（一峰→Ordered/PM、双峰→SG）のASCII図 | [block] $q_{ab} = \frac{\mathbf{h}^{(a)} \cdot \mathbf{h}^{(b)}}{\|\mathbf{h}^{(a)}\|\|\mathbf{h}^{(b)}\|}$; [block] $q_{EA} = \sqrt{\langle q^2 \rangle}$ | — |
| 12 | 実験で何を測っているか | flow | - 実験パイプライン5ステップのフロー（LLM実行→隠れ状態保存→コサイン類似度計算→P(q)分布生成→相判定） / - 25試行→300ペアの計算量 / - 測定量の整理: 精度 $m$・$q_{EA}$・$P(q)$ | $q_{ab}$, $q_{EA}$, $m$, $P(q)$ | — |
| 13 | 実験結果 ─ 精度の相図（accuracy heatmap） | figure-full | - 相図の読み方（左上=秩序相、右=低精度、下=崩壊） / - 相転移点 $T_c(N)$（$N$増加で低温側にシフト） / - 「$N$が増えると同じ$T$でも崩壊が速くなる」 | $T_c(N)$, $m$ | phase_diagram.png |
| 14 | 実験結果 ─ P(q) 分布の代表例 | figure-full | - グリッドの読み方（左上=鋭い一峰=Ordered、中央=幅広/二峰=SG、右=q≈0幅広=PM） / - $P(q)$の形状でラベルなし相同定の可能性を示す | $P(q)$, $T$, $N$ | pq_grid.png |
| 15 | 観測 1 ─ N 駆動の秩序崩壊 | table | - $N=2$〜$6$ 各行の特徴を記述した表 / - 物理的解釈: $N$増加→$K(N)=2^N-1$が指数増大→容量限界（Hopfield $\alpha_c \approx 0.138 N_p$）に対応 | $K(N) = 2^N - 1$, $\alpha_c$ | — |
| 16 | 観測 2 ─ T 駆動の遷移 | table | - Ordered→SG→PMの順の遷移の説明 / - 暫定転移温度表（$N=3$: $T_{c1} \approx 1.0$, $T_{c2} \approx 1.15$） / - $T$別試行結果内訳表（正解率・ループ率・PM率） / - SGシグナルは$T=0.7$〜$1.0$でピーク、$T \geq 1.2$で消滅 | $T_{c1}$, $T_{c2}$ | — |
| 17 | P(q) で見る 3 相の証拠 | table | - H3仮説（move loop=局所安定状態）の支持証拠 / - EXP-001（86セル分析）の結果表（領域・$P(q)$形状・解釈） / - 結論: $P(q)$双峰性はSG相の独立した証拠として機能 / - H3はsupported状態 | $P(q)$ | — |
| 18 | 散逸構造・$q_{EA}$ と精度の関係 | figure-left | - 重要な発見3点（$q_{EA}$と精度$m$の正相関・偏相関でも残る・$T$と独立した予測変数） / - 物理的解釈: 隠れ状態の試行間一貫性は$T$だけで決まらない | $q_{EA}$, $m$, $T$ | layer_comparison.png |
| 19 | 考察 ─ 何がわかって何がわからないか | two-col | - わかったこと3点（3相構造の存在・$P(q)$双峰性確認・$q_{EA}$の独立予測変数性） / - 現在検証中/わからないこと4点（スケーリング則$\alpha_s$未確定・3モデルの相図未取得・SG判定基準の定量化・制御外力の対応付け） / - open_questions.md U2〜U5 参照 | $T_c(N) = A \cdot N^{-\alpha_s}$, $q_{EA}$ | — |
| 20 | 最終ゴールと次のステップ | flow | - 制御モデル構築への3段階ロードマップのフロー図（段階1:相図観測→段階2:ハミルトニアン構築→段階3:制御モデル実装） / - 現在地: 段階1完了（7Bモデルのみ）、段階2への移行準備中 / - 次の優先タスク3件 / - 締切: 2026-06-30 モデリング完了 | — | — |
| 21 | まとめ ─ Take-home messages | summary | - Take-home message 1: LLMの推論行き詰まりを統計力学の相転移として記述できる（SG/PM/Ordered対応） / - Take-home message 2: $(T, N)$相図で3相構造（86セル取得済み） / - Take-home message 3: $P(q)$双峰性でSG相を同定し制御モデルへつなぐ（$q_{EA}$が精度の独立予測変数） | $q_{EA}$, $P(q)$ | — |
| 22 | 補足 ─ 実験パイプラインの全体像 | flow | - run_local.py → meta.json生成 → 各試行（LLM・moves評価・accuracy記録・隠れ状態npz追記） → summary.json保存 / - bash db/sync.sh → PostgreSQL同期 / - analysis/run_pipeline.py → 相図・P(q)・q_EA解析描画 / - 計算資源: RTX 5070, 12 GB VRAM（14B級はNF4量子化） | — | — |
| 23 | 補足 ─ early_stop 分類の詳細 | table | - 7ラベル（goal_reached / move_loop_repeat / move_loop_reverse / no_move_catchall / move_ceiling / stagnation_after_move / think_budget）の詳細表 / - 各アルゴリズム名・物理的解釈・相の対応 / - stagnation_after_move の相対応は現在検証中の注意書き / - 現行分類は physics-agent 審査で不合格（要再設計） | — | — |
| 24 | 補足 ─ 相分類の問題点と再設計 | two-col | - 現行分類の問題3点（行動ベース分類・stagnation_after_moveの判定不能・think_budgetはアーティファクト） / - P(q)ベース再設計方針のフロー図（ラベルベース→P(q)ベースへ） / - 目指すもの: ラベルに頼らない物理的に根拠のある相分類 | $\mathrm{BC}$, $p_{\mathrm{dip}}$, $q_{EA}$ | — |
| 25 | 記号定義表 | table | - design_system.yml の variable_mapping から生成した15行の対応表 / - コード変数・物理記号・意味の3列 / - 対象: temperature, N, accuracy, num_moves, q_ea, q_mean, q_var, q_bimodality_bc, q_dip_pval, layer_top, layer_mid, layer_low, K(N), goal_reached, move_loop_*, no_move_catchall/move_ceiling | $T$, $N$, $m$, $q_{EA}$, $\langle q \rangle$, $\mathrm{Var}(q)$, $\mathrm{BC}$, $p_{\mathrm{dip}}$, $K(N) = 2^N - 1$ | — |

---

## 補足メモ

**図ファイルの所在:** `docs/reports/20260525_hanoi_intro_b4_figures/`
- `phase_diagram.png` — スライド13（accuracy heatmap）
- `pq_grid.png` — スライド14（P(q) グリッド）
- `layer_comparison.png` — スライド18（層別 $q_{EA}$ vs 精度 scatter）

**physics-agent レビュー対象スライド:** 10, 11（PHYSICS-REVIEW-START/END マーカー済み）

**設計上の留意点（Marp 変換時）:**
- スライド10, 11 の数式はブロック数式を使用。Marp では `$$` ... `$$` で記述。
- スライド22, 24 のフロー図は現行 MD ではコードブロック（バッククォート）を使用。Marp では Mermaid または ASCII のまま維持。
- スライド23 の `stagnation_after_move` は open_questions.md U2 の未解決事項であり「現在検証中」として明示済み。
