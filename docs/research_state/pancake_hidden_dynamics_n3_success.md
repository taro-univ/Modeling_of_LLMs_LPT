# Pancake hidden dynamics note — N=3 success probe

対象:
`results/pancake/hidden_success_probe/deepseek-r1-distill-qwen-14b/N3_seed1_mm3_success_token8_noes_T0_6/`

条件: N=3, initial_state=`[1,3,2]`, min_moves=3, T=0.6, `capture_timing=token:8`,
`capture_mode=relative`, `hidden_dtype=float16`, `--no-early-stop`。

解析出力:
`figures/pancake_hidden_success_probe/N3_seed1_mm3_success_token8_noes_T0_6/layer_token_dynamics/`

## 1. 解析方針

PCA は可視化・診断に限定し、時間発展式の候補は元の hidden 空間の drift / cosine / event alignment を主に使う。
対象は generated 区間のみ。prompt 先頭 special token が mid/low 層の norm 外れ値になるため、prompt を混ぜて
PCA や drift を読むのは避ける。

hidden は token と layer の2軸で扱う。

```text
h[t, l]  t = generated token:8 row
         l = low -> mid -> top = [-36, -24, -1]
```

見る差分は2種類:

```text
token drift:  Δ_t h[t,l] = h[t,l] - h[t-1,l]
depth drift:  Δ_l h[t,l] = h[t,l] - h[t,l-1]
```

## 2. 数値結果

基本:

- generated rows: 98
- layers: low=`-36`, mid=`-24`, top=`-1`
- hidden_dim: 5120
- event join: 14 move mentions のうち 12 が token:8 row に対応
- final answer 末尾の 2 moves は generated 終端に近く、次の stride row が無いため unmapped

同層 token drift:

| layer | median `||Δ_t h||` | p95 `||Δ_t h||` | median cosine |
|---:|---:|---:|---:|
| -36 | 79.3 | 98.2 | 0.499 |
| -24 | 114.8 | 134.6 | 0.488 |
| -1 | 162.4 | 250.8 | 0.236 |

depth drift:

| transition | median `||Δ_l h||` | median cosine |
|---|---:|---:|
| low -> mid | 78.7 | 0.715 |
| mid -> top | 171.4 | 0.114 |

token velocity と同 token 内 depth update の alignment:

| transition | median cosine |
|---|---:|
| low token velocity vs low->mid update | -0.089 |
| mid token velocity vs mid->top update | -0.262 |

PCA 診断:

| 対象 | 40 components の説明分散 | 80%到達 | 90%到達 | 95%到達 |
|---|---:|---:|---:|---:|
| layer-token grid（層ごと z-score 後に混合） | 0.409 | 139 | 189 | 225 |
| low layer only | 0.803 | 40 | 56 | 68 |
| mid layer only | 0.774 | 44 | 62 | 75 |
| top layer only | 0.872 | 28 | 47 | 64 |

結論: 現時点で layer-token grid 全体を 40 次元に落とすのは情報を落としすぎる。層別 PCA なら
40 次元は 80% 前後を保つが、90% 以上を要求するなら low/mid/top で 56/62/47 成分が必要。
したがって時間発展式の推定は、まず元の 5120 次元または層別の十分な次元で行う。

## 3. Move event との対応

reasoning 中の move mentions は、最初に `Flip 3 -> Flip 2` で距離 3->2->1 まで進むが、その後に
逆向き move も混ざる。final answer は `Flip 2 -> Flip 3 -> Flip 2` で正答する。

重要なのは、`moves_all_mentions` 上の状態遷移と final answer の状態遷移が一致しないこと。つまり、
reasoning text 内の move mention は「実際にコミットされた手」ではなく、候補軌道の探索・リハーサルとして扱うべき。

## 4. 時間発展方程式の仮説

### 仮説1: 二重時間発展モデル

token 時間と layer 深度を別の発展方向として扱う。

```text
h[t+1,l] = h[t,l] + G_l(h[t,l], q[t], e[t]) + noise
h[t,l+1] = h[t,l] + F_l(h[t,l], q[t]) 
```

`q[t]` は text phase / distance / candidate state、`e[t]` は move mention event。
今回の数値では `Δ_t` と `Δ_l` の alignment が負なので、layer 方向は token 方向の単純な細分ではない。
よって 1 本の連続時間だけでなく、token 発展 `G_l` と depth 発展 `F_l` を分けるのが自然。

### 仮説2: depth は predictor-corrector cascade

low->mid は cosine 0.715 と近く、mid->top は drift が大きく cosine 0.114 とほぼ向きが変わる。

```text
h_mid = h_low + F_low(h_low)
h_top = h_mid + C(h_mid, task_context)
```

low->mid は表現の滑らかな更新、mid->top は出力・方策側への corrective jump と見る。Tuned Lens 系の考え方では、
層ごとに表現基底が回転・シフトしうるので、raw hidden の層間距離をそのまま「同じ空間の微小時間」とは読まない。
ただし、このプローブでは affine translator は未学習なので、まず raw residual geometry として扱う。

### 仮説3: move mention は連続 drift 上の impulse

通常 token drift に加え、move mention 近傍で状態候補が更新される impulse が入る。

```text
dh_l = b_l(h_l, phase) dt + Σ_k I[t=t_k] J_l(move_k, state_k) + σ_l dW_t
```

ここで `t_k` は move mention token。今回の move event では distance が下がる event と上がる event が混在するため、
impulse の符号は「最短降下」だけで決まらない。`delta_distance` を event label として、下降 impulse / 逆行 impulse を
分けて推定する必要がある。

### 仮説4: hidden の速度は distance-to-goal の単純な勾配ではない

top layer の token drift は distance=3 で大きめだが、distance=1/2/3 の差は1 trialでは統計的に弱い。
また final success でも reasoning 中の candidate trajectory は逆行する。したがって

```text
dh = -∇U(distance_to_goal) dt + noise
```

という単一ポテンシャル勾配だけでは足りない。候補としては、

```text
dh = -∇U_task(h) dt + A_phase(h) dt + impulse(move mentions) + noise
```

のように、task-level attractor と reasoning phase / move impulse を分ける。

### 仮説5: 層別 Koopman / DMD 型の局所線形モデル

層別 PCA では 40 成分で 77-87% 程度、90% には 47-62 成分が必要。層を混ぜた grid PCA は
40 成分で 41% しか説明しない。したがって、もし低次元線形発展を試すなら、

```text
z_l[t+1] = A_l z_l[t] + B_l u[t] + η[t]
```

を層別に立て、`z_l` は層別 PCA で 90% 以上を保つ次元にする。`u[t]` は move mention / phase / distance。
Koopman/DMD 系の枠組みは「非線形力学を observables 上で線形に見る」ための候補だが、今回の n=1 trajectory では
推定はしない。N=3 の複数 trial、または N=4/5 を含む複数軌道が揃ってから検証する。

## 5. 参考文献からの位置づけ

- Neural ODE は層列を連続深度の発展として見る理論的足場になる。ただし今回の `Δ_t` と `Δ_l` は別方向なので、
  そのまま単一 ODE にしない。
- Tuned Lens / Logit Lens は transformer の層ごとの中間表現を読む発想を与える。一方で Tuned Lens 側は
  層ごとの基底ずれを affine translator で補正するので、raw hidden の層間距離を直接比較する際の注意点にもなる。
- Diffusion maps / coarse-graining 系は、高次元 stochastic dynamics から低次元 coarse variables を選ぶときの
  候補。ただし今回の PCA 診断では global 40D は不十分なので、低次元化は層別・統計根拠付きで行う。
- Koopman/DMD 系は、観測量上で高次元または非線形の発展を線形作用素として近似する候補。現時点では仮説段階。

参照:

- Chen et al., Neural Ordinary Differential Equations, arXiv:1806.07366.
- Belrose et al., Eliciting Latent Predictions from Transformers with the Tuned Lens, arXiv:2303.08112.
- Coifman et al., Diffusion maps, reduction coordinates, and low dimensional representation of stochastic systems.
- Klus et al., Data-driven approximation of the Koopman generator.
