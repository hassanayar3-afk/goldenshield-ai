"""Bounded in-memory rings for prices and hub events (deque maxlen=500)."""

from __future__ import annotations

import os
from collections import deque
from typing import Deque, TypeVar

T = TypeVar("T")

_DEFAULT_MAX = 500


def ring_maxlen() -> int:
    try:
        return int(os.getenv("MEMORY_BUFFER_MAXLEN", str(_DEFAULT_MAX)))
    except ValueError:
        return _DEFAULT_MAX


def new_ring() -> Deque[T]:
    return deque(maxlen=ring_maxlen())
