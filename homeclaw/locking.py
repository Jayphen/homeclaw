"""Per-key async lock pool — prevents concurrent read-modify-write races."""

import asyncio


class LockPool:
    """A pool of asyncio.Lock instances keyed by string.

    Usage:
        pool = LockPool()
        async with pool.lock_for("alice"):
            # only one coroutine can hold this lock at a time
            ...
    """

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}

    def lock_for(self, key: str) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]
