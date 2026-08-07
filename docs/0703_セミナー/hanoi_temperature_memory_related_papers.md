# Hanoi 高温度での正答率上昇に接続しやすい先行研究 3 本

## 使い方の主張

Qwen 系で「高温度の N=4,5 だけ突然正答率が上がる」現象は、次の3段で説明するとセミナーで話しやすい。

1. 温度は単なるノイズではなく、推論経路の探索範囲を変える。
2. 低温デコードは高確率の反復パターンに固着し、move loop / no move を生みやすい。
3. Transformer attention は連想記憶・アトラクタ検索として解釈できるため、高温で別の解法アトラクタへ遷移した可能性がある。

---

## 1. On the Role of Temperature Sampling in Test-Time Scaling

- Yuheng Wu, Azalia Mirhoseini, Thierry Tambe, 2025
- arXiv: https://arxiv.org/abs/2510.02611

### 主張

LLM の推論性能はサンプル数だけでなく、温度方向にもスケールする。  
異なる温度は異なる問題集合を解くため、単一温度で多数サンプルするだけではモデルの潜在能力を十分に引き出せない。

### 手法

- Qwen3 系列を含む複数モデルで、推論ベンチマークを温度別に評価。
- AIME, MATH500, LiveCodeBench, Hi-ToM などで、単一温度の test-time scaling と複数温度の scaling を比較。
- 複数温度から生成した reasoning trace を voting する multi-temperature voting を提案。

### 結果

- 異なる温度が異なる問題を解くことを確認。
- Qwen3 系列と複数ベンチマーク平均で、温度方向の scaling により単一温度 TTS より追加で性能改善。
- 温度を上げることは単なる劣化ではなく、探索可能な reasoning boundary を広げる操作として解釈できる。

### Hanoi との接続

Hanoi の N=4,5 高温で正答率が上がる現象は、「高温でたまたま良くなった」よりも、「低温では到達できない解法軌道が高温で開いた」と説明しやすい。  
特に Qwen3 を実験対象に含むため、セミナーでは最初に出すべき論文。

---

## 2. The Curious Case of Neural Text Degeneration

- Ari Holtzman, Jan Buys, Li Du, Maxwell Forbes, Yejin Choi, ICLR 2020
- arXiv: https://arxiv.org/abs/1904.09751

### 主張

尤度最大化で訓練された言語モデルに対して、生成時にも高尤度系列だけを選ぶと、出力は退屈で反復的になりやすい。  
つまり、greedy decoding や beam search は自然な生成を保証せず、むしろ degeneration を起こす。

### 手法

- 人間のテキストと機械生成テキストの分布差を分析。
- greedy, beam search, sampling など複数の decoding strategy を比較。
- 確率分布の信頼できる上位部分だけからサンプルする nucleus sampling を提案。

### 結果

- 高確率系列を追う decoding は、反復・不自然・単調な出力を生みやすい。
- 確率的サンプリングは多様性を増やしつつ、低確率すぎる tail を切ることで品質も保てる。
- 同じモデルでも decoding strategy だけで生成品質が大きく変わる。

### Hanoi との接続

Hanoi の `move loop` は、まさに「高確率だが間違った局所パターンへの固着」と見なせる。  
低温ではモデルが安全そうな定型手順を繰り返し、高温ではその固着から抜けて別の手順を試す、という説明に使える。

---

## 3. Hopfield Networks is All You Need

- Hubert Ramsauer et al., 2020/2021
- arXiv: https://arxiv.org/abs/2008.02217

### 主張

Modern Hopfield network は非常に大きな記憶容量を持つ連想記憶モデルであり、その更新則は Transformer の attention と等価に解釈できる。  
Transformer attention は単なる重み付き平均ではなく、記憶・プロトタイプ・中間表現への検索機構として見られる。

### 手法

- 連続状態の modern Hopfield network を定式化。
- エネルギー最小点を、全体平均、部分集合の metastable state、単一パターン記憶の3種類に分類。
- Hopfield update と Transformer attention の数式的対応を示す。
- Hopfield layer を複数タスクに適用して性能を検証。

### 結果

- Modern Hopfield network は指数的な記憶容量と小さい retrieval error を持つ。
- Transformer の attention head は、層によって global averaging や metastable state への部分平均として解釈できる。
- attention を「記憶検索の力学」として語れる理論的足場を与える。

### Hanoi との接続

Hanoi 解法を「正しい手順アトラクタへの検索」と見ると、失敗は `move loop` や `no move` というスプリアス状態への落ち込みとして説明できる。  
高温で正答率が上がる場合、サンプリング温度が attention/hidden state の記憶検索そのものを変えるわけではないが、出力トークン選択を通じて次状態の軌道を変え、別のアトラクタ basin に入った可能性を議論できる。

---

## セミナーでのまとめ方

### 1枚目: 観測事実

- Qwen で N=4,5 の高温域に正答率上昇がある。
- 同じ領域で `move loop` / `no move` の比率がどう変わるかを NT 平面で示す。

### 2枚目: 低温崩壊の解釈

- 低温は最尤に近い経路を選びやすい。
- 最尤経路が正しいとは限らず、反復的 degeneration に落ちる。
- `move loop` はこの degeneration のタスク版と見なせる。

### 3枚目: 高温で回復する解釈

- 温度上昇により別の reasoning trace が探索される。
- Qwen3 の温度 scaling 論文は、異なる温度が異なる問題集合を解くことを示す。
- Hanoi でも N=4,5 にだけ「探索で救える難易度帯」がある可能性がある。

### 4枚目: 記憶容量・アトラクタへの接続

- Transformer attention は Hopfield 的な連想記憶として解釈できる。
- Hanoi の失敗は、正解アトラクタではなくスプリアスアトラクタに落ちる現象として話せる。
- 高温はスプリアス状態からの脱出を助けるが、高すぎると軌道が壊れる、という相転移的説明につながる。

## 一言で言う仮説

Qwen の N=4,5 高温回復は、低温での高確率・反復的な崩壊軌道から、温度上昇によって別の推論アトラクタへ遷移できた結果かもしれない。
