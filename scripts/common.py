from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def serialize_json(value: Any, *, compact: bool = False) -> str:
    if compact:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        ) + "\n"

    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as handle:
        handle.write(text)
        temporary_path = Path(handle.name)

    os.replace(temporary_path, path)


def write_json_atomic(
    path: Path,
    value: Any,
    *,
    compact: bool = False,
) -> None:
    write_text_atomic(
        path,
        serialize_json(value, compact=compact),
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def meaningful_json_signature(
    value: Any,
    ignored_keys: set[str] | None = None,
) -> str:
    ignored = ignored_keys or set()

    def clean(item: Any) -> Any:
        if isinstance(item, dict):
            return {
                key: clean(child)
                for key, child in item.items()
                if key not in ignored
            }
        if isinstance(item, list):
            return [clean(child) for child in item]
        return item

    payload = json.dumps(
        clean(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return sha256_bytes(payload)
