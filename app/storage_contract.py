"""Runtime contract proving that API and worker resolve the same storage root."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

WORKER_STORAGE_KEY = "clipia:runtime:worker_storage_dir"


class RedisStorageClient(Protocol):
    def get(self, key: str) -> str | bytes | None: ...

    def set(self, key: str, value: str) -> object: ...


def normalized_storage_dir(path: Path | str) -> str:
    """Return a stable, case-insensitive identity on Windows."""
    return os.path.normcase(str(Path(path).expanduser().resolve()))


def publish_worker_storage(client: RedisStorageClient, path: Path | str) -> str:
    resolved = normalized_storage_dir(path)
    client.set(WORKER_STORAGE_KEY, resolved)
    return resolved


def worker_storage_matches(client: RedisStorageClient, api_path: Path | str) -> bool | None:
    raw = client.get(WORKER_STORAGE_KEY)
    if raw is None:
        return None
    worker_path = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
    return normalized_storage_dir(worker_path) == normalized_storage_dir(api_path)
