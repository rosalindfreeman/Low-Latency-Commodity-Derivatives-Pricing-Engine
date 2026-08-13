from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Hashable
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class _Entry(Generic[T]):
    value: T
    expires_at: float


class TTLCache(Generic[T]):
    def __init__(self, maxsize: int = 10_000, ttl_seconds: float = 10.0) -> None:
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self._data: OrderedDict[Hashable, _Entry[T]] = OrderedDict()

    def get(self, key: Hashable) -> T | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        if entry.expires_at < time.monotonic():
            del self._data[key]
            return None
        self._data.move_to_end(key)
        return entry.value

    def set(self, key: Hashable, value: T) -> None:
        self._data[key] = _Entry(value, time.monotonic() + self.ttl_seconds)
        self._data.move_to_end(key)
        while len(self._data) > self.maxsize:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)

