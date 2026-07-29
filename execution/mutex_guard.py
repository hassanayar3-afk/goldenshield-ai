"""منع تضارب أوامر نفس الزوج."""

from __future__ import annotations


class MutexGuard:
    def __init__(self) -> None:
        self._locked: set[str] = set()

    def try_acquire(self, symbol: str) -> bool:
        if symbol in self._locked:
            return False
        self._locked.add(symbol)
        return True

    def release(self, symbol: str) -> None:
        self._locked.discard(symbol)

    def is_locked(self, symbol: str) -> bool:
        return symbol in self._locked

    def clear(self) -> None:
        self._locked.clear()
