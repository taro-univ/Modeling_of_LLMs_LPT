"""解析用local data rootの設定。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_ROOT = REPO_ROOT / "local_data"
DATA_ROOT_ENV = "LPT_DATA_ROOT"


def resolve_data_root(
    cli_value: str | Path | None,
    *,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """local data rootを優先順位に従って解決する。

    Parameters
    ----------
    cli_value:
        ``--data-root`` で指定された値。
    environ:
        環境変数mapping。テスト時以外は ``os.environ`` を使う。

    Returns
    -------
    pathlib.Path
        ``CLI > LPT_DATA_ROOT > repository/local_data`` で選んだ絶対path。
    """
    source = os.environ if environ is None else environ
    raw = cli_value if cli_value is not None else source.get(DATA_ROOT_ENV)
    path = Path(raw).expanduser() if raw else DEFAULT_DATA_ROOT
    return path.resolve()
