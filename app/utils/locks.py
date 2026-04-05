from __future__ import annotations

import asyncio
import threading

_locks: dict[str, asyncio.Lock] = {}
_guard = threading.Lock()


def get_lock(key: str) -> asyncio.Lock:
    with _guard:
        lock = _locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _locks[key] = lock
        return lock
