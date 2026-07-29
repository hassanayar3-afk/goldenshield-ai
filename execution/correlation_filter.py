"""فلتر الارتباط بين الأزواج — منع تراكم المخاطر."""

from __future__ import annotations

from config.settings import get_settings


class CorrelationFilter:
    def __init__(self, groups: tuple[tuple[str, ...], ...] | None = None) -> None:
        settings = get_settings()
        source = groups if groups is not None else settings.correlation_groups
        self._groups = [frozenset(group) for group in source]

    def can_open(self, symbol: str, open_symbols: set[str]) -> tuple[bool, str]:
        for group in self._groups:
            if symbol not in group:
                continue
            correlated = group & open_symbols
            if correlated:
                others = ", ".join(sorted(correlated))
                return False, f"ارتباط عالي مع مراكز مفتوحة: {others}"
        return True, ""
