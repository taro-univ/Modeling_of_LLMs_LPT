# Hanoi puzzle: サイズ N・エントロピー・複雑性/複雑度の整理

## 0. 記号の方針

- パズルサイズは **\(N\) = 円盤数** とする。
- 3本杭のハノイグラフを **\(H_N\)** と書く。
- 論文によっては円盤数を \(n\)、ランダムCSPの変数数を \(N\) と書くため、スライドでは次を固定する。

| 対象 | スライド記号 | 意味 |
|---|---:|---|
| Tower of Hanoi | \(N\) | 円盤数 |
| Hanoi graph | \(H_N\) | 3本杭・\(N\)円盤の状態遷移グラフ |
| ランダムCSP / coloring | \(V\) または \(N_{\mathrm{var}}\) | 変数数・頂点数 |
| 制約密度 | \(c\) | coloringでは平均次数、SATでは節密度に対応 |

---

## 1. Hanoi graph の基本量

**主張:** Tower of Hanoi は、状態を頂点、合法手を辺にしたグラフ \(H_k^N\) として扱える。3本杭なら \(H_N = H_3^N\)。

- 状態数:

\[
|V(H_k^N)| = k^N,\qquad |V(H_N)| = 3^N
\]

- 3本杭の辺数:

\[
|E(H_N)|=\frac{3(3^N-1)}{2}
\]

- 標準問題の最短手数、つまりグラフ直径の代表値:

\[
d_{\mathrm{start}\to\mathrm{goal}}(N)=2^N-1
\]

- 状態空間エントロピー:

\[
S_{\mathrm{state}}(N)=\log |V(H_N)| = N\log 3
\]

円盤1枚あたりの状態エントロピーは \(\log 3\)。ただし、探索距離は \(2^N\) スケールなので、「状態数 \(3^N\)」と「最短解 \(2^N-1\)」を別々に見せるとよい。

**スライド用一言:**  
Hanoi は「有限だが指数的に広い状態空間」を持つ。サイズ \(N\) を1増やすと状態数は3倍、標準解長はほぼ2倍になる。

---

## 2. Zhang et al. 2015: Hanoi graph の全域木数と全域木エントロピー

対象論文: Zhongzhi Zhang, Shunqi Wu, Mingyun Li, Francesc Comellas, *The number and degree distribution of spanning trees in the Tower of Hanoi graph*, Theoretical Computer Science 609, 443-455, 2016. arXiv:1510.07949.

### 論文の主張

Hanoi graph \(H_N\) の自己相似構造を使うと、全域木数を厳密に数えられる。さらに、ランダムに選んだ全域木上で各頂点がどの次数を持つかも計算できる。

### 主結果

全域木数を \(s_N\) とすると、

\[
s_N
=3^{\frac{1}{4}3^N+\frac{1}{2}N-\frac{1}{4}}
 5^{\frac{1}{4}3^N-\frac{1}{2}N-\frac{1}{4}}.
\]

したがって、全域木エントロピーを

\[
h=\lim_{N\to\infty}\frac{\log s_N}{|V(H_N)|}
\]

と定義すると、

\[
h=\frac{1}{4}(\log 3+\log 5)
=\frac{1}{4}\log 15
\approx 0.677.
\]

### 複雑性/複雑度の読み替え

- \(s_N\) は全域木の数なので、「経路」ではなく「グラフ全体の接続構造の多様性」を測る量。
- \(\log s_N \sim h\,3^N\) なので、全域木の個数は

\[
s_N \asymp \exp(h\,3^N)
\]

となる。円盤数 \(N\) に対しては **二重指数的** に増える。
- ただし頂点数 \(|V|=3^N\) をサイズとみなすと、全域木数は通常の指数成長 \(\exp(h|V|)\)。

**スライド用一言:**  
Hanoi graph は状態数だけでも \(3^N\) だが、その上の全域木構造は \(\exp(0.677\cdot 3^N)\) 個ある。円盤数 \(N\) で見ると、構造的多様性はさらに急激に増える。

---

## 3. Istrate 2000: 計算複雑性と相転移

対象論文: Gabriel Istrate, *Computational Complexity and Phase Transitions*, arXiv:cs/0005032.

### 論文の主張

組合せ問題では、解が存在する領域から存在しない領域へ移る相転移近傍に難しいインスタンスが現れやすい。ただし、**NP完全性だけでは sharp threshold を保証しない**。

### 主結果

Schaefer 型の一般化SAT、特に clausal constraints について、sharp threshold を持つ条件を特徴づける。

threshold の幅は、確率パラメータ \(p\) に対して

\[
\frac{p_{1-\epsilon}(N)-p_\epsilon(N)}{p_{1/2}(N)}
\]

で見る。これが \(N\to\infty\) で0に行けば sharp threshold、0から離れていれば coarse threshold。

重要な結論:

- NP完全でも coarse threshold を持つ例がある。
- ただし clausal generalized SAT で sharp でない場合は、問題が多項式時間で解けるか、または \(0^N\), \(1^N\) のような自明な割当でかなり予測できる特殊な場合に限られる。

### Hanoi への使い方

Hanoi そのものはランダムSATではないが、実験で制約密度・温度・探索ノイズなどの制御パラメータを入れるなら、次の形で相転移を見る。

\[
P_{\mathrm{success}}(N,\lambda)
\]

をサイズ \(N\)、制御パラメータ \(\lambda\) での成功確率とし、

\[
w_N =
\frac{\lambda_{1-\epsilon}(N)-\lambda_{\epsilon}(N)}
{\lambda_{1/2}(N)}
\]

を遷移幅とする。

- \(w_N\to 0\): サイズ増大で急峻化。sharp transition 的。
- \(w_N\not\to 0\): 遷移がぼやける。coarse transition 的。

**スライド用一言:**  
「難しさ」は単にNP完全かどうかではなく、成功確率がどれだけ急に崩れるかで測る。Hanoi 実験では \(\lambda_{1/2}\) と幅 \(w_N\) をサイズごとに推定する。

---

## 4. Krzakala & Zdeborova 2007: ランダムCSPの解空間エントロピーと複雑度

対象論文: Florent Krzakala, Lenka Zdeborova, *Phase Transitions and Computational Difficulty in Random Constraint Satisfaction Problems*, J. Phys.: Conf. Ser. 95, 012012, 2008. arXiv:0711.0110.

### 論文の主張

ランダムCSP、特にランダムグラフの \(q\)-coloring では、制約密度 \(c\) を上げると解空間の幾何が段階的に変わる。アルゴリズム困難性は、単なるクラスタ化だけでなく、クラスタ内の凍結変数に強く関係する。

### 主結果: 解エントロピー

平均次数 \(c\)、色数 \(q\)、頂点数 \(V\) のランダムグラフ coloring で、低密度側の解エントロピー密度は

\[
s
=\frac{\log N_{\mathrm{sol}}}{V}
=\log q+\frac{c}{2}\log\left(1-\frac{1}{q}\right).
\]

ここで \(N_{\mathrm{sol}}\) は適切な coloring の個数。

### 主結果: 相の列

制約密度 \(c\) を増やすと、典型的に次の順で解空間が変化する。

| 相 | 閾値 | 意味 |
|---|---:|---|
| connected / simple | 低 \(c\) | 解が大きな1つのクラスタにある |
| clustering | \(c_d\) | 解空間が指数個のクラスタに分裂 |
| condensation | \(c_c\) | 少数の巨大クラスタが解の大半を占める |
| rigidity / freezing | \(c_r\) | 支配的クラスタ内に凍結変数が現れる |
| COL/UNCOL | \(c_s\) | 解が消える |

クラスタ数の複雑度は

\[
\Sigma = \frac{1}{V}\log N_{\mathrm{clusters}}
\]

として整理できる。クラスタ化では \(\Sigma>0\) になり、凝縮では解の重みが少数クラスタへ集中する。

### アルゴリズム困難性の主張

論文は、\(c_d\) を越えてクラスタ化しても、局所探索がただちに失敗するわけではないと述べる。困難性の本質は、クラスタが分かれること自体よりも、凍結変数が現れて近傍探索で動けなくなることにある。

**スライド用一言:**  
解空間は「数が減る」だけでなく「割れる」「偏る」「凍る」。Hanoi の探索実験でも、成功率だけでなく軌道の閉じ込め・バックトラック不能・同じ誤答クラスタへの集中を見るべき。

---

## 5. Hanoi 実験で採用する測度案

### サイズ

\[
N = \text{円盤数}
\]

状態数と標準解長:

\[
|V|=3^N,\qquad L^*(N)=2^N-1.
\]

### エントロピー

候補1: 状態空間エントロピー

\[
S_{\mathrm{state}}(N)=N\log 3.
\]

候補2: 有効訪問状態エントロピー

\[
S_{\mathrm{visit}}
=-\sum_{x\in H_N}p(x)\log p(x).
\]

候補3: 出力分布エントロピー

\[
S_{\mathrm{out}}
=-\sum_{\tau}p(\tau)\log p(\tau),
\]

ここで \(\tau\) は出力された手順、または正規化した軌道タイプ。

候補4: 全域木エントロピー

\[
h_{\mathrm{tree}}=\frac{1}{4}\log 15 \approx 0.677.
\]

これはHanoi graph 固有の構造量として背景に置く。実験値ではなく、理論的ベースライン。

### 複雑性

最短解長:

\[
L^*(N)=2^N-1.
\]

探索空間:

\[
|V|=3^N.
\]

全域木構造:

\[
s_N \asymp \exp(h_{\mathrm{tree}}3^N).
\]

LLM実験での実効複雑性:

\[
C_{\mathrm{eff}}(N,\lambda)
=-\log P_{\mathrm{success}}(N,\lambda).
\]

または、試行回数 \(R\) の成功率から

\[
\widehat{P}_{\mathrm{success}}=\frac{\#\mathrm{success}}{R}.
\]

### 複雑度

CSP文脈の「complexity」はクラスタ数の対数密度:

\[
\Sigma=\frac{1}{|V|}\log N_{\mathrm{clusters}}.
\]

Hanoi 実験では直接クラスタ数を定義しにくいので、次の代理量を使う。

- 誤答クラスタ数:

\[
\Sigma_{\mathrm{err}}
=\frac{1}{N}\log K_{\mathrm{err}},
\]

ここで \(K_{\mathrm{err}}\) は失敗軌道を類似度でクラスタリングした数。

- 行き詰まり状態の集中度:

\[
S_{\mathrm{trap}}
=-\sum_{z\in Z}p(z)\log p(z),
\]

ここで \(Z\) は失敗時の終端状態。

- 凍結度:

\[
F = \frac{\#\{\text{以後ほぼ変更されない円盤/サブゴール}\}}{N}.
\]

---

## 6. スライド構成案

### Slide 1: 問題設定

- \(N\) 円盤 Tower of Hanoi を対象にする。
- 状態グラフは \(H_N\)。
- 状態数は \(3^N\)、標準解長は \(2^N-1\)。
- 見たい量: エントロピー、成功確率、相転移幅、探索の閉じ込め。

### Slide 2: Hanoi graph の理論量

\[
|V(H_N)|=3^N,\quad
|E(H_N)|=\frac{3(3^N-1)}{2},\quad
L^*=2^N-1.
\]

メッセージ: \(N\) は小さく見えても、状態空間と解長は指数的に増える。

### Slide 3: 全域木エントロピー

\[
s_N
=3^{\frac{1}{4}3^N+\frac{1}{2}N-\frac{1}{4}}
 5^{\frac{1}{4}3^N-\frac{1}{2}N-\frac{1}{4}}
\]

\[
h_{\mathrm{tree}}
=\lim_{N\to\infty}\frac{\log s_N}{3^N}
=\frac{1}{4}\log 15
\approx 0.677.
\]

メッセージ: Hanoi graph の構造的多様性は \(\exp(0.677\cdot 3^N)\)。

### Slide 4: 相転移の見方

\[
P_{\mathrm{success}}(N,\lambda)
\]

\[
w_N =
\frac{\lambda_{1-\epsilon}(N)-\lambda_{\epsilon}(N)}
{\lambda_{1/2}(N)}.
\]

メッセージ: 成功率曲線が \(N\) とともに鋭くなるなら sharp transition 的。

### Slide 5: CSPからの類推

\[
s=\frac{\log N_{\mathrm{sol}}}{V}
=\log q+\frac{c}{2}\log\left(1-\frac{1}{q}\right),
\qquad
\Sigma=\frac{1}{V}\log N_{\mathrm{clusters}}.
\]

解空間の変化:

\[
\text{connected}
\to \text{clustered}
\to \text{condensed}
\to \text{frozen}
\to \text{unsat}.
\]

メッセージ: 困難性は「解が少ない」だけでなく、「解空間が分裂し、凍る」ことで増える。

### Slide 6: Hanoi/LLM 実験で測るもの

- \(S_{\mathrm{visit}}\): モデルが実際に探索した状態のエントロピー。
- \(C_{\mathrm{eff}}=-\log P_{\mathrm{success}}\): 成功困難性。
- \(S_{\mathrm{trap}}\): 失敗終端状態の多様性。
- \(F\): サブゴールや円盤配置の凍結度。
- \(w_N\): 成功率遷移の鋭さ。

メッセージ: Hanoi の \(N\) を上げながら、成功率だけでなく「探索がどこで閉じ込められるか」を測る。

---

## 7. まとめの主張

1. Tower of Hanoi のサイズ \(N\) は、状態数 \(3^N\) と標準解長 \(2^N-1\) を同時に増やす。
2. Hanoi graph の全域木エントロピーは厳密に

\[
h_{\mathrm{tree}}=\frac{1}{4}\log 15\approx0.677
\]

であり、構造的多様性の理論ベースラインになる。
3. Istrate の結果から、難しさはNP完全性だけでなく、閾値の鋭さ・粗さとして見るべき。
4. Krzakala & Zdeborova の結果から、困難性は解空間のクラスタ化よりも、凍結・閉じ込めに強く関係する。
5. Hanoi/LLM 実験では、\(P_{\mathrm{success}}\)、\(w_N\)、\(S_{\mathrm{visit}}\)、\(S_{\mathrm{trap}}\)、\(F\) をサイズ \(N\) ごとに追うのがよい。

---

## 参考文献・確認元

- Gabriel Istrate, *Computational Complexity and Phase Transitions*, arXiv:cs/0005032. https://arxiv.org/abs/cs/0005032
- Zhongzhi Zhang, Shunqi Wu, Mingyun Li, Francesc Comellas, *The number and degree distribution of spanning trees in the Tower of Hanoi graph*, arXiv:1510.07949. https://arxiv.org/abs/1510.07949
- Wikipedia, *Hanoi graph*. https://en.wikipedia.org/wiki/Hanoi_graph
- Florent Krzakala, Lenka Zdeborova, *Phase Transitions and Computational Difficulty in Random Constraint Satisfaction Problems*, arXiv:0711.0110. https://arxiv.org/abs/0711.0110
