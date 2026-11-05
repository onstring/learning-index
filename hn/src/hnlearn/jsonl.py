"""JSON Lines helpers with resume support."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def read(path: Path) -> Iterator[dict[str, Any]]:
    """Yield one dict per line. A missing file yields nothing.

    A torn final line (no trailing newline, left by a killed writer) is skipped with a
    warning; ``append`` repairs it. Any other bad line raises.
    """
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                if not line.endswith("\n"):
                    log.warning("%s:%d: ignoring torn final line", path.name, n)
                    return
                raise ValueError(f"{path.name}:{n}: invalid JSON ({e.msg})") from e


def append(path: Path, row: dict[str, Any]) -> None:
    """Append one row, first discarding any torn line left by a previous crash."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")
    with path.open("a+b") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        if size > 0:
            f.seek(-1, os.SEEK_END)
            if f.read(1) != b"\n":
                _truncate_torn_line(f, size)
        f.write(data)


def _truncate_torn_line(f: Any, size: int) -> None:
    """Cut the file back to its last newline (or to empty), dropping the partial line."""
    f.seek(0)
    content = f.read(size)
    keep = content.rfind(b"\n") + 1
    log.warning("%s: discarding torn final line", getattr(f, "name", "?"))
    f.seek(keep)
    f.truncate()


def done_keys(path: Path, key: str) -> set[Any]:
    """Values of ``key`` already present in the file, for skipping finished rows."""
    return {row[key] for row in read(path) if key in row}


def require_keys(row: dict[str, Any], keys: Iterable[str], where: str) -> None:
    """Raise ValueError naming the missing keys, so a malformed input stops the stage."""
    missing = [k for k in keys if k not in row]
    if missing:
        raise ValueError(f"{where} missing: {', '.join(missing)}")


def write_json(path: Path, obj: Any) -> None:
    """Write a pretty-printed JSON document atomically, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def replace_with(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    """Atomically replace ``path`` with ``rows``. Returns the row count."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    n = 0
    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    os.replace(tmp, path)
    return n
