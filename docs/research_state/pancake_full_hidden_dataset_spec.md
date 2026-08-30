# Pancake full-hidden distribution dataset 取得仕様

作成日: 2026-08-20

目的: Pancake Sorting の確率分布の時間発展を後から複数の解析法で検討できるよう、
outcomeで選別しない generated-token full-hidden trajectory を取得する。解析器や
hidden類似度は取得系に含めない。

## 1. 固定する科学条件

正本configは
`configs/pancake_full_hidden_dataset_v1.json` とする。

```text
model: deepseek-ai/DeepSeek-R1-Distill-Qwen-14B
temperature: 0.6
repetition_penalty: 1.1
n_shot: 0
num_predict: 8192
early_stop: disabled
capture source: generated token only
token stride: 1
layers: all 48 Transformer layers
hidden size: 5120
dtype: float16
storage: chunked HDF5, gzip, 64-token CPU buffer
```

EOSに至らず8192 tokenへ到達したtrajectoryも捨てず、
`done_reason=length` の右側打ち切りデータとして保持する。成功・失敗・loopなどの
outcomeを見て再取得対象を選ばない。

hidden row `t` は、generated `token_ids[t]` をsampleする直前のcontext stateである。
EOSをsampleしたstepはgenerated text tokenに含めず、そのhiddenも保存しない。
EOS終了自体は `done_reason=eos` と `sampled_eos_token_id` に残す。

## 2. 実験行列

実在する6 cellを各100 trial、合計600 trajectory取得する。

| cell | 距離殻の全state数 | 選択state数 | allocation |
|---|---:|---:|---|
| N3/mm3 | 1 | 1 | 1 state x 100 seeds |
| N4/mm3 | 11 | 10 | 10 states x 10 seeds |
| N4/mm4 | 3 | 3 | 34 / 33 / 33 seeds |
| N5/mm3 | 35 | 10 | 10 states x 10 seeds |
| N5/mm4 | 48 | 10 | 10 states x 10 seeds |
| N5/mm5 | 20 | 10 | 10 states x 10 seeds |

N3/mm4--5、N4/mm5は該当stateがないので作らない。既存の代表stateをanchorとして
先頭に残し、残りは固定seed `20260820` で候補殻から選んだ。実際に使うstateと
trial allocationはconfigへ明記済みであり、実行時の再抽選は行わない。

runnerは各stateのBFS `min_moves`を再計算し、configと不一致ならmodel load前に停止する。
configから構築した `DATASET_PLAN.json` は600件の一意なtrial ID、state index、
state内反復番号を固定する。sampling RNG streamを別stateや別cellで再利用しないよう、
sample seedは固定plan順のglobal unique値 `1..600` を割り当てる。

## 3. trial artifact

```text
cells/N5_mm5/trials/N5_mm5_state01_trial001_seed501/
  raw/
    prompt.txt
    formatted_prompt.txt
    generated.txt
    generated_token_ids.npy
    spans_v1.json
    metadata.json
  hidden/
    hidden.h5
  debug/
    replay_v1.json
  labels/
    labels_v1.json
  checksums.json
  checksums.sha256
  checksums.md5
  COMPLETE.json
```

`hidden.h5` の主datasetは次の通り。

```text
hidden:          [T, 48, 5120] float16
token_ids:       [T] int32
token_positions: [T] int32, 0..T-1
layer_ids:       [48] int32, 1..48
```

hiddenは最大64 tokenだけCPU memoryへbufferし、trial末尾まで巨大配列をRAMへ
保持しない。HDF5は `hidden.h5.partial` に追記し、flush/close後に同一filesystem内で
`hidden.h5` へatomic renameする。trial directory自体も検証終了までは `.partial`
とし、最後にatomic renameする。中断したpartialは自動削除・上書きしない。

生成文、token ID、prompt、整形済みprompt、model/tokenizer revision、sampling seed、
終了理由、生成文SHA-256を残す。`spans_v1.json` はMove、`<think>`、`<final>`の
exact char spanを保存する。token spanはgenerated token IDsをretokenize結果と照合し、
完全一致した場合だけexactとして保存する。不一致時は推定値を作らず
`mapping_verified=false` でsmoke gateを落とし、rawから再処理できる状態を保つ。

## 4. debugとlabels

`replay_v1.json` は生成文から再生成でき、次を分離する。

- reasoning中のMove mention trajectory
- 全Move mention trajectory
- 最後のclosed `<final>`、またはopen `<final>`からEOFまでの提出trajectory

各mentionにはchar span、parsed `k`、合法性、state before/after、goalまでの厳密距離、
距離差、goal到達、既出stateかを保存する。

`labels_v1.json` はraw/hiddenとは別にversion管理する。v1では
`success_final`、`search_success_final_fail`、`search_fail`、`no_final`、
`length_censored` と、illegal/repeated-state/format/length等の直接観測flagだけを
rule生成する。rule misunderstanding、planning failure、state tracking failureなどの
原因推定は空で残し、人手または後続labelerが証拠span付きの新versionとして追加する。

## 5. cell lifecycle

production cellの状態遷移は固定する。

```text
GENERATING (100 trials)
  -> trial schema/finite/hash validation
  -> CELL_MANIFEST + LOCAL_COMPLETE
  -> rclone copy --immutable
  -> remote expected paths + sizes + MD5 validation
  -> remote CELL_COMPLETE.jsonを最後にcopyto
  -> markerを含むremote再検証
  -> local transfer receipt (REMOTE_VERIFIED)
  -> 明示flag時だけlocal cell削除
  -> 次cell
```

remote確認は「存在」だけではなく、予定file集合、size、Driveが返すMD5をlocalと
全件照合する。SHA-256もlocal manifestに残す。既存remote markerから再開する場合も
marker本体を読み、cell ID、remote path、現在のmanifest SHA-256との一致を確認する。
`.partial` が1つでもあればuploadしない。
転送はcopyだけを使い、sync/moveは使わない。quota、通信、hashのいずれかが失敗したら
localを保持してprocessを停止し、次cellを生成しない。再実行時は完成trialと
`REMOTE_VERIFIED` receiptを検証してskipする。

local削除は `--delete-local-after-verify` が指定され、cell IDとreceiptが一致し、
削除対象が `cells/` の直下であり、receiptのremote pathが当該cellを指し、receiptの
manifest SHA-256が削除直前の `CELL_MANIFEST.json` と一致する場合だけ行う。

disk preflightは既定でcell開始時550 GB、生成中200 GBを要求する。値はfilesystemの
実測に合わせてCLIで引き上げられる。production順は小さいcellからN3/mm3、N4/mm3、
N4/mm4、N5/mm3、N5/mm4、N5/mm5とする。

## 6. smokeと実行

まずplanだけを確認する。

```bash
python3 runners/pancake_full_hidden_dataset.py --dry-run
```

GPU環境でN3 schema smokeとN5 stress smokeを順に行う。remote rootは本番と分ける。

```bash
python3 runners/pancake_full_hidden_dataset.py \
  --smoke schema \
  --remote-root pancake-drive:LLM_LPT/full_hidden_v1_smoke

python3 runners/pancake_full_hidden_dataset.py \
  --smoke stress \
  --remote-root pancake-drive:LLM_LPT/full_hidden_v1_smoke
```

両方でHDF5 shape/finite/token alignment、span mapping、終了理由、実測時間、peak
RAM/VRAM、file size、remote hashを確認する。peak RAM/VRAMは外部monitor
（`/usr/bin/time -v`、`nvidia-smi`等）も併用する。

production実行例:

```bash
python3 runners/pancake_full_hidden_dataset.py \
  --remote-root pancake-drive:LLM_LPT/full_hidden_distribution_v1 \
  --delete-local-after-verify
```

最初は `--cells N3_mm3` だけでも実行できる。`--local-only` は1 cellを完成させた時点で
停止し、次cellへ進まない。

## 7. Google Drive接続

rcloneの認証情報はrepositoryへ置かない。

1. GPU hostでrcloneをinstallし、`rclone config` を実行する。
2. Google Drive remoteを例として `pancake-drive` という専用名で作る。tokenは通常の
   rclone config（例: `~/.config/rclone/rclone.conf`）にのみ保存する。
3. My Drive内に本実験専用rootを決め、`rclone lsd pancake-drive:` で接続確認する。
4. 本番前に数十byteのend-to-end testを実行する。

```bash
python3 runners/pancake_drive_integration_test.py \
  --remote-root pancake-drive:LLM_LPT/full_hidden_v1_integration_test
```

このtestはupload、remote size/MD5、同一転送のresume、再download後SHA-256一致まで
確認する。remote fixtureは目視確認用に自動削除しない。合格後、N3 schema smokeを
Driveへ送り、Drive上のmarkerとlocal receiptを確認してからstress smokeへ進む。

Driveの共有link、OAuth token、service-account JSON、rclone configはcommitしない。
24時間upload上限等で停止した場合は、上限回復後に同じcommandを再実行する。

## 8. ローカルテストと実環境gate

GPU、torch/transformers、h5py、rcloneを必要としないplan、replay、span、transfer障害系は
pytestで検証する。HDF5 writerの実file testはh5py導入済み環境で行う。

```bash
python3 -m pytest tests/test_pancake_full_hidden_dataset.py -q
python3 -m pytest tests/
```

本番開始前に残るintegration gate:

- h5pyを含むrequirementsをGPU環境へ反映
- model architectureが48 layers / hidden size 5120であること
- pinned model forward実装でhidden tuple各indexと最終normの位置を確認すること
- exact span mappingがsmokeでtrueになること
- N3/N5 smokeのHDF5再openとfinite検証
- small Drive integration testとsmoke実data transfer
- 実測file size、生成時間、upload throughput、RAM/VRAMからdisk thresholdを再確認

## 9. Non-goals

- hidden similarity、PCA、drift/diffusion、jump項のfit
- outcomeによるtrial選抜や追加sampling
- attention、MLP、KV cacheの保存
- inferred failure causeの自動確定
- remote検証前のlocal削除
