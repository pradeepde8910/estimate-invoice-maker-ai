"""
API Key Manager — round-robin key rotation with automatic failover.
"""

import asyncio
import itertools
from typing import Optional


class KeyManager:
    """Thread-safe round-robin API key rotator."""

    def __init__(self, keys: list[str]):
        if not keys:
            raise ValueError("At least one API key is required.")
        self._keys = keys
        self._cycle = itertools.cycle(keys)
        self._lock = asyncio.Lock()
        self._failed: set[str] = set()

    async def get_key(self) -> str:
        """Return the next available key via round-robin."""
        async with self._lock:
            for _ in range(len(self._keys)):
                key = next(self._cycle)
                if key not in self._failed:
                    return key
            # If all keys have failed, reset and try again
            self._failed.clear()
            return next(self._cycle)

    async def mark_failed(self, key: str) -> None:
        """Mark a key as temporarily failed."""
        async with self._lock:
            self._failed.add(key)

    async def reset(self) -> None:
        """Reset all failed keys."""
        async with self._lock:
            self._failed.clear()

    @property
    def available_count(self) -> int:
        return len(self._keys) - len(self._failed)

    @property
    def total_count(self) -> int:
        return len(self._keys)
