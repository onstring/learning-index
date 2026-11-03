"""JSON Lines helpers with resume support."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any


def read(path: Path) -> Iterator[dict[str, Any]]:
    """Yield one dict per line. A missing file yields nothing; a bad line raises."""
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path.name}:{n}: invalid JSON ({e.msg})") from e


def append(path: Path, row: dict[str, Any]) -> None:
    """Append one row and flush, so a killed run keeps every finished row."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def done_keys(path: Path, key: str) -> set[Any]:
    """Values of ``key`` already present in the file, for skipping finished rows."""
    return {row[key] for row in read(path) if key in row}


def require_keys(row: dict[str, Any], keys: Iterable[str], where: str) -> None:
    """Raise ValueError naming the missing keys, so a malformed input stops the stage."""
    missing = [k for k in keys if k not in row]
    if missing:
        raise ValueError(f"{where} missing: {', '.join(missing)}")


def write_json(path: Path, obj: Any) -> None:
    """Write a pretty-printed JSON document, creating parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
