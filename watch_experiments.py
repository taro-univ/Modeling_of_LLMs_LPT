#!/usr/bin/env python3
"""
Experiment monitor for Modeling_of_LLMs_LPT.
Usage:
    python3 watch_experiments.py           # one-shot
    watch -n 10 python3 watch_experiments.py   # refresh every 10s
    python3 watch_experiments.py --no-color    # no ANSI
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
RESULTS = ROOT / "results" / "hanoi"
LOGS_DIR = ROOT / "logs"

# ── Symmetric accuracy (B/C gauge-equivalent goal) ────────────────────────────
# summary.json の accuracy は取得時の env 定義に依存する（対称化前データは旧 C-only）。
# モニターでは move_texts から対称化 env で accuracy を再判定し、定義を一本化する。
sys.path.insert(0, str(ROOT))
try:
    from envs.hanoi_env import TowerOfHanoiEnv  # noqa: E402
    _ENV_OK = True
except Exception:
    _ENV_OK = False

_env_cache: dict = {}
_acc_cache: dict = {}  # (cell_path, summary_mtime) -> recomputed accuracy

def _env(n: int):
    if n not in _env_cache:
        _env_cache[n] = TowerOfHanoiEnv(n)
    return _env_cache[n]

def _symmetric_accuracy(cell_dir: Path, trials: list, n: int) -> float:
    """move_texts から対称化ゴール(B/C)で accuracy を再計算。npz 欠損時は summary 値にフォールバック。"""
    import numpy as np
    accs = []
    for t in trials:
        tn = t.get("trial")
        npz = cell_dir / f"trial_{tn:03d}_hidden.npz" if isinstance(tn, int) else None
        moves = None
        if npz is not None and npz.exists():
            try:
                z = np.load(npz, allow_pickle=True)
                if "move_texts" in z.files:
                    moves = [str(x) for x in z["move_texts"]]
            except Exception:
                moves = None
        if moves and moves[0] != "__fallback__":
            accs.append(1 if _env(n).goal_reached(moves) else 0)
        elif "accuracy" in t:
            accs.append(t["accuracy"])
    return sum(accs) / len(accs) if accs else 0.0

# ── ANSI colors ──────────────────────────────────────────────────────────────

def _supports_color(force_off: bool) -> bool:
    if force_off:
        return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

C: dict = {}

def setup_colors(enabled: bool) -> None:
    if enabled:
        C.update({
            "reset":  "\033[0m",
            "bold":   "\033[1m",
            "dim":    "\033[2m",
            "green":  "\033[32m",
            "yellow": "\033[33m",
            "red":    "\033[31m",
            "cyan":   "\033[36m",
            "blue":   "\033[34m",
            "magenta":"\033[35m",
            "white":  "\033[97m",
            "bg_dark":"\033[48;5;235m",
        })
    else:
        C.update({k: "" for k in [
            "reset","bold","dim","green","yellow","red",
            "cyan","blue","magenta","white","bg_dark",
        ]})

def c(text: str, *keys: str) -> str:
    prefix = "".join(C.get(k, "") for k in keys)
    return f"{prefix}{text}{C['reset']}" if prefix else text

# ── GPU ──────────────────────────────────────────────────────────────────────

def gpu_status() -> str:
    try:
        out = subprocess.check_output(
            ["nvidia-smi",
             "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader"],
            timeout=3, text=True
        ).strip()
        parts = [p.strip().rstrip(" %MiBC") for p in out.split(",")]
        util, mem_used, mem_total, temp = parts
        bar_len = 20
        pct = int(util) / 100
        filled = int(pct * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        color = "green" if int(util) < 50 else "yellow" if int(util) < 80 else "red"
        return (
            f"GPU  [{c(bar, color)}] {c(util+'%', color, 'bold')}  "
            f"VRAM {c(mem_used, 'cyan')}/{mem_total} MiB  "
            f"Temp {c(temp+'°C', 'yellow')}"
        )
    except Exception:
        return c("GPU  nvidia-smi unavailable", "dim")

# ── Docker ────────────────────────────────────────────────────────────────────

def docker_status() -> str:
    try:
        out = subprocess.check_output(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
            timeout=3, text=True
        ).strip()
        parts = []
        seen = set()
        for line in out.splitlines():
            name, status = line.split("\t", 1)
            short = (name.replace("modeling_of_llms_lpt-", "")
                        .replace("dev-app-", "")
                        .rstrip("-1").rstrip("-"))
            if short in seen:
                continue
            seen.add(short)
            color = "green" if "Up" in status else "red"
            uptime = re.search(r"Up (.+?)(?:\s*\(|$)", status)
            uptime_str = uptime.group(1).strip() if uptime else status[:12]
            healthy = " ✓" if "healthy" in status else ""
            parts.append(f"{c(short, color, 'bold')} ({uptime_str}{healthy})")
        return "Docker  " + "  |  ".join(parts) if parts else c("Docker  not running", "red")
    except Exception:
        return c("Docker  unavailable", "dim")

# ── Results scanning ──────────────────────────────────────────────────────────

def scan_sweep(sweep_dir: Path) -> dict:
    """Returns {model_slug: {cell_name: {"meta": bool, "summary": bool, "n_trials": int, "acc": float}}}"""
    data = {}
    if not sweep_dir.exists():
        return data
    for model_dir in sorted(sweep_dir.iterdir()):
        if not model_dir.is_dir():
            continue
        slug = model_dir.name
        data[slug] = {}
        for cell_dir in sorted(model_dir.iterdir()):
            if not cell_dir.is_dir():
                continue
            cell = cell_dir.name
            has_meta = (cell_dir / "meta.json").exists()
            has_summary = (cell_dir / "summary.json").exists()
            n_trials = 0
            acc = None
            if has_summary:
                try:
                    summary_path = cell_dir / "summary.json"
                    trials = json.loads(summary_path.read_text())
                    n_trials = len(trials)
                    n_disks = parse_cell_name(cell)[0]
                    key = (str(cell_dir), summary_path.stat().st_mtime)
                    if key in _acc_cache:
                        acc = _acc_cache[key]
                    elif _ENV_OK and n_disks > 0:
                        acc = _symmetric_accuracy(cell_dir, trials, n_disks)
                        _acc_cache[key] = acc
                    else:
                        accs = [t["accuracy"] for t in trials if "accuracy" in t]
                        acc = sum(accs) / len(accs) if accs else 0.0
                except Exception:
                    pass
            data[slug][cell] = {
                "meta": has_meta,
                "summary": has_summary,
                "n_trials": n_trials,
                "acc": acc,
            }
    return data

def parse_cell_name(cell: str) -> tuple[int, float]:
    m = re.match(r"N(\d+)_T(\d+)_(\d+)", cell)
    if not m:
        return (0, 0.0)
    n = int(m.group(1))
    t = float(f"{m.group(2)}.{m.group(3)}")
    return (n, t)

# ── Progress table ────────────────────────────────────────────────────────────

MODEL_LABELS = {
    "deepseek-r1-distill-qwen-7b":   "DS-R1-Qwen7B",
    "deepseek-r1-distill-qwen-14b":  "DS-R1-Qwen14B",
    "deepseek-r1-distill-llama-8b":  "DS-R1-Llama8B",
    "qwen3-8b":                      "Qwen3-8B",
    "qwen3-14b":                     "Qwen3-14B",
}

def progress_bar(done: int, total: int, width: int = 12) -> str:
    if total == 0:
        return "─" * width
    frac = done / total
    filled = int(frac * width)
    bar = "█" * filled + "░" * (width - filled)
    color = "green" if frac >= 1.0 else "yellow" if frac > 0 else "dim"
    return c(bar, color)

def acc_cell(acc: float | None) -> str:
    if acc is None:
        return c("  -- ", "dim")
    color = "green" if acc > 0.6 else "yellow" if acc > 0.2 else "red"
    return c(f"{acc:5.2f}", color)

def print_sweep_table(title: str, data: dict, target_trials: int = 25) -> None:
    if not data:
        print(c(f"  {title}: no data", "dim"))
        return

    all_ns = sorted({parse_cell_name(c)[0] for model in data.values() for c in model})
    n_cols = [str(n) for n in all_ns]

    col_w = max(len(v) for v in MODEL_LABELS.values()) + 2
    header = f"  {'Model':<{col_w}}"
    for n in n_cols:
        header += f" N={n} "
    header += "  Done/Total  Progress"
    print(c(f"\n  {title}", "bold", "cyan"))
    print(c("  " + "─" * (len(header) - 2), "dim"))
    print(c(header, "bold"))
    print(c("  " + "─" * (len(header) - 2), "dim"))

    for slug, cells in data.items():
        label = MODEL_LABELS.get(slug, slug[:14])
        row = f"  {label:<{col_w}}"

        done_total = len([v for v in cells.values() if v["summary"]])
        total = len(cells)

        for n in all_ns:
            n_cells = {k: v for k, v in cells.items() if parse_cell_name(k)[0] == n}
            n_done = sum(1 for v in n_cells.values() if v["summary"])
            n_total = len(n_cells)
            if n_total == 0:
                row += c(f" {'':^5}", "dim")
            elif n_done == n_total:
                row += c(f" {n_done:2d}/{n_total:<2d}", "green")
            elif n_done > 0:
                row += c(f" {n_done:2d}/{n_total:<2d}", "yellow")
            else:
                row += c(f" {n_done:2d}/{n_total:<2d}", "dim")

        bar = progress_bar(done_total, total)
        pct = f"{done_total/total*100:.0f}%" if total > 0 else "  -"
        row += f"  {c(str(done_total), 'bold')}/{total}  {bar} {pct}"
        print(row)

    print(c("  " + "─" * (len(header) - 2), "dim"))

# ── Waiting cells (in-progress) ───────────────────────────────────────────────

def find_waiting(data_by_sweep: dict[str, dict]) -> list[tuple]:
    waiting = []
    for sweep_type, data in data_by_sweep.items():
        for slug, cells in data.items():
            for cell, info in cells.items():
                if info["meta"] and not info["summary"]:
                    waiting.append((sweep_type, slug, cell))
    return waiting

# ── Accuracy heatmap ──────────────────────────────────────────────────────────

def print_accuracy_heatmap(data: dict, sweep_name: str) -> None:
    if not data:
        return
    all_ns = sorted({parse_cell_name(cell)[0] for model in data.values() for cell in model})
    if not all_ns:
        return

    print(c(f"\n  Accuracy overview — {sweep_name}", "bold", "blue"))
    label = "symmetric B/C goal" if _ENV_OK else "summary.json (env unavailable)"
    print(c(f"  (avg accuracy per N, completed cells only — {label})", "dim"))

    col_w = max(len(v) for v in MODEL_LABELS.values()) + 2
    header = f"  {'Model':<{col_w}}" + "".join(f"  N={n} " for n in all_ns)
    print(c("  " + "─" * (len(header) - 2), "dim"))
    print(c(header, "bold"))
    print(c("  " + "─" * (len(header) - 2), "dim"))

    for slug, cells in data.items():
        label = MODEL_LABELS.get(slug, slug[:14])
        row = f"  {label:<{col_w}}"
        for n in all_ns:
            n_cells = [v for k, v in cells.items()
                       if parse_cell_name(k)[0] == n and v["acc"] is not None]
            if not n_cells:
                row += c(f"   -- ", "dim")
            else:
                avg = sum(v["acc"] for v in n_cells) / len(n_cells)
                color = "green" if avg > 0.6 else "yellow" if avg > 0.2 else "red"
                row += c(f"  {avg:.2f} ", color)
        print(row)
    print(c("  " + "─" * (len(header) - 2), "dim"))

# ── Log tail ──────────────────────────────────────────────────────────────────

def print_log_tail(n_lines: int = 8) -> None:
    logs = sorted(LOGS_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True) if LOGS_DIR.exists() else []
    if not logs:
        return
    log = logs[0]
    mtime = datetime.fromtimestamp(log.stat().st_mtime).strftime("%m-%d %H:%M")
    print(c(f"\n  Recent log — {log.name}  (modified {mtime})", "bold", "magenta"))
    print(c("  " + "─" * 60, "dim"))
    try:
        lines = log.read_text(errors="replace").splitlines()
        for line in lines[-n_lines:]:
            clean = line.rstrip()
            if "error" in clean.lower() or "traceback" in clean.lower():
                print(f"  {c(clean, 'red')}")
            elif "done" in clean.lower() or "saved" in clean.lower() or "complete" in clean.lower():
                print(f"  {c(clean, 'green')}")
            elif clean.startswith("  ") or "python" in clean.lower():
                print(f"  {c(clean, 'dim')}")
            else:
                print(f"  {clean}")
    except Exception as e:
        print(c(f"  (read error: {e})", "red"))
    print(c("  " + "─" * 60, "dim"))

# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--no-acc", action="store_true", help="skip accuracy heatmap")
    args = parser.parse_args()

    setup_colors(_supports_color(args.no_color))

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print()
    print(c("  ══════════════════════════════════════════════════════════", "bold"))
    print(c(f"    Experiment Monitor  {now}", "bold", "white"))
    print(c("  ══════════════════════════════════════════════════════════", "bold"))
    print()
    print(f"  {gpu_status()}")
    print(f"  {docker_status()}")

    sweep_types = ["full_sweep", "collapse_phase", "stagnation_sweep"]
    data_by_sweep: dict[str, dict] = {}
    for st in sweep_types:
        data_by_sweep[st] = scan_sweep(RESULTS / st)

    for st in sweep_types:
        if data_by_sweep[st]:
            print_sweep_table(st.replace("_", " ").upper(), data_by_sweep[st])

    waiting = find_waiting(data_by_sweep)
    print(c("\n  IN PROGRESS (meta only — no summary yet)", "bold", "yellow"))
    print(c("  " + "─" * 60, "dim"))
    if waiting:
        for sweep_type, slug, cell in waiting:
            label = MODEL_LABELS.get(slug, slug)
            print(f"  {c('●', 'yellow')} {c(label, 'bold')}  {c(sweep_type, 'dim')}  {cell}")
    else:
        print(c("  (none — all started cells have summaries)", "dim", "green"))
    print(c("  " + "─" * 60, "dim"))

    if not args.no_acc:
        for st in ["full_sweep", "collapse_phase"]:
            if data_by_sweep.get(st):
                print_accuracy_heatmap(data_by_sweep[st], st.replace("_", " "))

    print_log_tail()

    total_cells = sum(
        len(cells)
        for data in data_by_sweep.values()
        for cells in data.values()
    )
    total_done = sum(
        sum(1 for v in cells.values() if v["summary"])
        for data in data_by_sweep.values()
        for cells in data.values()
    )
    print(c(f"\n  Total: {total_done}/{total_cells} cells complete\n", "bold"))


if __name__ == "__main__":
    main()
