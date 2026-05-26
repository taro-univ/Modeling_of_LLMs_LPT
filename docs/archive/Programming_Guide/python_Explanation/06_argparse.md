# 06 argparse：コマンドライン引数の処理

実験スクリプトを `python run_hf.py --N 4 --temperature 0.8` のように実行するための仕組み。

## 基本パターン

```python
import argparse

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ハノイの塔で LLM の推論崩壊を検知する"
    )

    # 必須引数
    parser.add_argument("--N", type=int, required=True,
                        help="円盤の枚数")

    # デフォルト値付き引数
    parser.add_argument("--trials",      type=int,   default=None)
    parser.add_argument("--temperature", type=float, default=0.6)
    parser.add_argument("--model-id",    type=str,   default="deepseek-ai/...")
    parser.add_argument("--device",      type=str,   default="cuda:0")

    # フラグ（True/False のスイッチ）
    parser.add_argument("--no-early-stop",  action="store_true")
    parser.add_argument("--no-save-hidden", action="store_true")

    return parser.parse_args()
```

## 引数の取り出し

```python
def main() -> None:
    args = parse_args()

    N           = args.N               # --N の値
    temperature = args.temperature     # --temperature の値
    no_stop     = args.no_early_stop   # --no-early-stop が指定されたら True

    # None チェックしてデフォルト計算
    trials = args.trials if args.trials is not None else calc_default_trials(args.N)
```

`--no-early-stop` のように `-` を含む引数名は、`args.no_early_stop`（`_` に変換）でアクセスする。

## type の指定

| `type=` | 変換後の型 | 例 |
|---|---|---|
| `int` | 整数 | `--N 4` → `args.N == 4` |
| `float` | 浮動小数点 | `--temperature 0.8` → `args.temperature == 0.8` |
| `str` | 文字列 | `--device cuda:1` → `args.device == "cuda:1"` |

## action="store_true"

フラグ引数（引数を書いただけで `True` になる）。

```python
parser.add_argument("--no-early-stop", action="store_true")
# python run_hf.py --N 4 --no-early-stop  →  args.no_early_stop == True
# python run_hf.py --N 4                  →  args.no_early_stop == False
```

## run_hf.py の実行例と対応

```bash
# N=4、temperature=0.8、early_stop なし、hidden 保存なし
python runners/run_hf.py \
    --N 4 \
    --temperature 0.8 \
    --no-early-stop \
    --no-save-hidden

# フルオプション
python runners/run_hf.py \
    --N 5 \
    --trials 20 \
    --temperature 1.0 \
    --device cuda:1 \
    --es-loop-window 8 \
    --sweep-type phase_diagram
```

各フラグと `args` の対応：

| コマンド引数 | args 属性 | 型 |
|---|---|---|
| `--N` | `args.N` | int |
| `--trials` | `args.trials` | int \| None |
| `--temperature` | `args.temperature` | float |
| `--device` | `args.device` | str |
| `--no-early-stop` | `args.no_early_stop` | bool |
| `--no-save-hidden` | `args.no_save_hidden` | bool |
| `--sweep-type` | `args.sweep_type` | str |
