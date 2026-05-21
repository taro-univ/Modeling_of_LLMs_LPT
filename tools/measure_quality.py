#!/usr/bin/env python3
"""
tools/measure_quality.py — コード品質メトリクス計測ツール

radon を使って Cyclomatic Complexity (CC) と Maintainability Index (MI) を
全 Python ファイルに対して計測し、閾値違反をレポートする。

使い方:
    python3 tools/measure_quality.py              # 全ファイルをスキャン
    python3 tools/measure_quality.py --file runners/run_local.py
    python3 tools/measure_quality.py --json       # JSON 出力（CI 連携用）
    python3 tools/measure_quality.py --threshold-cc 10 --threshold-mi 20

閾値:
    CC >= 10 → 要リファクタリング (radon grade C 以上)
    MI < 20  → 保守性低（radon grade C 以下相当）
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# 閾値設定
# ---------------------------------------------------------------------------

DEFAULT_CC_THRESHOLD = 10   # Cyclomatic Complexity: この値以上は要リファクタ
DEFAULT_MI_THRESHOLD = 20   # Maintainability Index: この値以下は保守性低

# スキャン対象ディレクトリ（プロジェクトルートからの相対パス）
TARGET_DIRS = [
    "runners",
    "analysis",
    "envs",
    "db",
    "tests",
    "tools",
]

# スキャン除外パターン
EXCLUDE_PATTERNS = [
    "**/archive/**",
    "**/__pycache__/**",
    "**/.venv/**",
]


# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------

@dataclass
class FunctionCC:
    name: str
    lineno: int
    cc: int
    rank: str  # A–F


@dataclass
class FileMetrics:
    path: str
    loc: int
    cc_total: int
    cc_max: int
    cc_mean: float
    mi: float
    mi_rank: str  # A–C
    functions: list[FunctionCC] = field(default_factory=list)

    @property
    def cc_violations(self) -> list[FunctionCC]:
        return [f for f in self.functions if f.cc >= DEFAULT_CC_THRESHOLD]

    @property
    def mi_ok(self) -> bool:
        return self.mi >= DEFAULT_MI_THRESHOLD


# ---------------------------------------------------------------------------
# radon 呼び出しヘルパー
# ---------------------------------------------------------------------------

def _run(cmd: list[str], cwd: Path) -> str:
    """サブプロセスを実行して stdout を返す。失敗時は空文字列。"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(cwd),
        )
        return result.stdout
    except FileNotFoundError:
        return ""


def _check_radon(project_root: Path) -> bool:
    """radon がインストールされているか確認する。"""
    out = _run(["python3", "-m", "radon", "--version"], project_root)
    if not out.strip():
        print("[ERROR] radon が見つかりません。", file=sys.stderr)
        print("        pip install radon  でインストールしてください。", file=sys.stderr)
        return False
    return True


def _parse_cc_json(raw_json: str) -> dict[str, list[FunctionCC]]:
    """radon cc -j の出力を {filepath: [FunctionCC, ...]} に変換する。"""
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return {}

    result: dict[str, list[FunctionCC]] = {}
    for filepath, funcs in data.items():
        result[filepath] = [
            FunctionCC(
                name=f.get("name", "?"),
                lineno=f.get("lineno", 0),
                cc=f.get("complexity", 0),
                rank=f.get("rank", "?"),
            )
            for f in funcs
        ]
    return result


def _parse_mi_json(raw_json: str) -> dict[str, dict]:
    """radon mi -j の出力を {filepath: {mi, rank}} に変換する。"""
    try:
        return json.loads(raw_json)
    except json.JSONDecodeError:
        return {}


def _count_loc(filepath: Path) -> int:
    """非空行数を数える（コードの LOC として使用）。"""
    try:
        lines = filepath.read_text(encoding="utf-8").splitlines()
        return sum(1 for ln in lines if ln.strip())
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# メイン計測ロジック
# ---------------------------------------------------------------------------

def collect_python_files(
    project_root: Path,
    target_dirs: list[str],
    extra_files: Optional[list[str]] = None,
) -> list[Path]:
    """スキャン対象の .py ファイルを収集する。"""
    files: list[Path] = []

    if extra_files:
        for ef in extra_files:
            p = project_root / ef
            if p.exists():
                files.append(p)
        return files

    for d in target_dirs:
        dir_path = project_root / d
        if not dir_path.is_dir():
            continue
        files.extend(sorted(dir_path.rglob("*.py")))

    # 除外パターン（archive などは除外）
    filtered: list[Path] = []
    for f in files:
        rel = f.relative_to(project_root)
        skip = any(rel.match(pat) for pat in EXCLUDE_PATTERNS)
        if not skip:
            filtered.append(f)

    return filtered


def measure_all(
    project_root: Path,
    py_files: list[Path],
    cc_threshold: int = DEFAULT_CC_THRESHOLD,
    mi_threshold: int = DEFAULT_MI_THRESHOLD,
) -> list[FileMetrics]:
    """全ファイルの CC・MI を計測して FileMetrics リストを返す。"""
    if not py_files:
        return []

    # ファイルパス文字列（プロジェクトルート相対）
    rel_paths = [str(f.relative_to(project_root)) for f in py_files]

    # radon cc
    cc_raw = _run(
        ["python3", "-m", "radon", "cc", "-j", "-s"] + rel_paths,
        project_root,
    )
    cc_data = _parse_cc_json(cc_raw)

    # radon mi
    mi_raw = _run(
        ["python3", "-m", "radon", "mi", "-j", "-s"] + rel_paths,
        project_root,
    )
    mi_data = _parse_mi_json(mi_raw)

    metrics: list[FileMetrics] = []
    for f, rel in zip(py_files, rel_paths):
        funcs = cc_data.get(rel, [])
        mi_entry = mi_data.get(rel, {})

        cc_values = [fn.cc for fn in funcs] if funcs else [0]
        mi_val = mi_entry.get("mi", float("nan"))
        mi_rank = mi_entry.get("rank", "?")

        metrics.append(
            FileMetrics(
                path=rel,
                loc=_count_loc(f),
                cc_total=sum(cc_values),
                cc_max=max(cc_values),
                cc_mean=sum(cc_values) / len(cc_values) if cc_values else 0.0,
                mi=round(mi_val, 1) if mi_val == mi_val else float("nan"),
                mi_rank=mi_rank,
                functions=funcs,
            )
        )

    return sorted(metrics, key=lambda m: (-m.cc_max, -m.cc_total))


# ---------------------------------------------------------------------------
# レポート出力
# ---------------------------------------------------------------------------

def _rank_color(rank: str) -> str:
    """ターミナル ANSI 色コードを返す。"""
    return {
        "A": "\033[32m",   # green
        "B": "\033[32m",   # green
        "C": "\033[33m",   # yellow
        "D": "\033[31m",   # red
        "E": "\033[31m",   # red
        "F": "\033[31m",   # red
    }.get(rank, "")


RESET = "\033[0m"


def _print_file_row(
    m: FileMetrics,
    cc_threshold: int,
    mi_threshold: int,
    verbose: bool,
) -> bool:
    """1 ファイル分のテーブル行を出力する。違反があれば True を返す。"""
    cc_flag = " ⚠" if m.cc_max >= cc_threshold else "  "
    mi_flag = " ⚠" if not m.mi_ok else "  "
    mi_str  = f"{m.mi:.1f}" if m.mi == m.mi else "N/A"
    rank_c  = _rank_color(m.mi_rank)
    print(
        f"  {m.path:<42} {m.loc:>5} {m.cc_total:>7}{cc_flag} "
        f"{m.cc_max:>7}  {rank_c}{mi_str:>6} {m.mi_rank:>4}{RESET}{mi_flag}"
    )
    if verbose and m.cc_violations:
        for fn in sorted(m.cc_violations, key=lambda f: -f.cc):
            print(f"      L{fn.lineno:<5} {fn.name:<35} CC={fn.cc} ({fn.rank})")
    return m.cc_max >= cc_threshold or not m.mi_ok


def _collect_cc_violations(metrics: list[FileMetrics]) -> list[tuple[str, FunctionCC]]:
    """全ファイルの CC 違反関数を CC 降順で返す。"""
    violations: list[tuple[str, FunctionCC]] = [
        (m.path, fn) for m in metrics for fn in m.cc_violations
    ]
    violations.sort(key=lambda x: -x[1].cc)
    return violations


def _print_summary_block(
    metrics: list[FileMetrics],
    cc_threshold: int,
    mi_threshold: int,
    cc_viol_funcs: list[tuple[str, FunctionCC]],
    total_violations: int,
) -> None:
    """サマリーセクション（ファイル数・違反数・上位関数・合否）を出力する。"""
    total_files   = len(metrics)
    cc_viol_files = sum(1 for m in metrics if m.cc_max >= cc_threshold)
    mi_viol_files = sum(1 for m in metrics if not m.mi_ok)

    print(f"  スキャンファイル数: {total_files}")
    print(f"  CC ≥ {cc_threshold} のファイル: {cc_viol_files}")
    print(f"  MI < {mi_threshold} のファイル: {mi_viol_files}")

    if cc_viol_funcs:
        print()
        print("  ⚠ CC 上位関数（要リファクタ）:")
        for path, fn in cc_viol_funcs[:10]:
            print(f"      {path}:{fn.lineno}  {fn.name}  CC={fn.cc} ({fn.rank})")

    print()
    if total_violations == 0:
        print("  ✅ 全ファイルが閾値内に収まっています。")
    else:
        print(f"  ❌ {total_violations} ファイルが閾値を超えています。")


def print_report(
    metrics: list[FileMetrics],
    cc_threshold: int = DEFAULT_CC_THRESHOLD,
    mi_threshold: int = DEFAULT_MI_THRESHOLD,
    verbose: bool = False,
) -> int:
    """
    品質レポートをターミナルに出力する。

    Returns:
        violations: CC/MI 違反ファイル数（CI の exit code に使用）
    """
    print()
    print("=" * 72)
    print("  Code Quality Report — radon CC / MI")
    print("=" * 72)
    print(f"  閾値: CC ≥ {cc_threshold} → 要リファクタ  |  MI < {mi_threshold} → 保守性低")
    print()

    header = f"  {'ファイル':<42} {'LOC':>5} {'CC合計':>7} {'CC最大':>7} {'MI':>6} {'MI評価':>6}"
    print(header)
    print("  " + "-" * 70)

    violations = sum(
        1 for m in metrics
        if _print_file_row(m, cc_threshold, mi_threshold, verbose)
    )

    print()
    print("  " + "=" * 70)
    _print_summary_block(
        metrics, cc_threshold, mi_threshold,
        _collect_cc_violations(metrics), violations,
    )
    print("=" * 72)
    print()

    return violations


def print_json(metrics: list[FileMetrics]) -> None:
    """JSON 形式でメトリクスを出力する（CI 連携用）。"""
    out = []
    for m in metrics:
        out.append({
            "path": m.path,
            "loc": m.loc,
            "cc_total": m.cc_total,
            "cc_max": m.cc_max,
            "cc_mean": round(m.cc_mean, 2),
            "mi": m.mi,
            "mi_rank": m.mi_rank,
            "violations": {
                "cc": [
                    {"name": fn.name, "lineno": fn.lineno, "cc": fn.cc, "rank": fn.rank}
                    for fn in m.cc_violations
                ],
                "mi_low": not m.mi_ok,
            },
        })
    print(json.dumps(out, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# エントリポイント
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Python コードの CC / MI を計測して品質レポートを生成する。"
    )
    parser.add_argument(
        "--file", nargs="+", metavar="PATH",
        help="特定ファイルのみ計測（省略時は TARGET_DIRS 全体をスキャン）",
    )
    parser.add_argument(
        "--threshold-cc", type=int, default=DEFAULT_CC_THRESHOLD,
        help=f"CC 閾値（デフォルト: {DEFAULT_CC_THRESHOLD}）",
    )
    parser.add_argument(
        "--threshold-mi", type=int, default=DEFAULT_MI_THRESHOLD,
        help=f"MI 閾値（デフォルト: {DEFAULT_MI_THRESHOLD}）",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="JSON 形式で出力する（CI 連携用）",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="CC 違反関数の詳細を表示する",
    )
    parser.add_argument(
        "--root", default=".",
        help="プロジェクトルートディレクトリ（デフォルト: カレントディレクトリ）",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(args.root).resolve()

    if not _check_radon(project_root):
        sys.exit(2)

    py_files = collect_python_files(
        project_root,
        TARGET_DIRS,
        extra_files=args.file,
    )

    if not py_files:
        print("[WARN] スキャン対象のファイルが見つかりませんでした。")
        sys.exit(0)

    metrics = measure_all(
        project_root,
        py_files,
        cc_threshold=args.threshold_cc,
        mi_threshold=args.threshold_mi,
    )

    if args.json:
        print_json(metrics)
        return

    violations = print_report(
        metrics,
        cc_threshold=args.threshold_cc,
        mi_threshold=args.threshold_mi,
        verbose=args.verbose,
    )

    # 違反があれば exit code 1（git hook 連携用）
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
