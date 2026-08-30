"""Object storage abstraction (ADR 0011). `LocalFileSystemStore` is used in
development and tests; a `CloudStorageStore` implementation is added when
Milestone 11 wires up real GCP infrastructure. Application code depends only
on `ObjectStore`, never on a concrete backend.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Protocol


class ObjectStore(Protocol):
    def put(self, source_path: str | Path, *, key: str | None = None) -> str: ...

    def get(self, key: str) -> Path: ...

    def delete(self, key: str) -> None: ...


class LocalFileSystemStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, source_path: str | Path, *, key: str | None = None) -> str:
        key = key or str(uuid.uuid4())
        destination = self.root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination)
        return key

    def get(self, key: str) -> Path:
        path = self.root / key
        if not path.exists():
            raise FileNotFoundError(key)
        return path

    def delete(self, key: str) -> None:
        path = self.root / key
        path.unlink(missing_ok=True)
