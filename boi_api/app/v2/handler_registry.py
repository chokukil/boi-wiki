from __future__ import annotations

from collections.abc import Callable
from typing import Any


class CapabilityHandlerRegistry:
    """Runtime plugin registry for already validated capability contracts."""

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[Any], Any]] = {}

    def register(self, handler_id: str, handler: Callable[[Any], Any]) -> None:
        candidate = str(handler_id or "").strip()
        if not candidate:
            raise ValueError("handler_id is required")
        if candidate in self._handlers:
            raise ValueError(f"duplicate capability handler: {candidate}")
        self._handlers[candidate] = handler

    def execute(self, handler_id: str, context: Any) -> Any:
        try:
            handler = self._handlers[handler_id]
        except KeyError as exc:
            raise KeyError(f"unregistered capability handler: {handler_id}") from exc
        return handler(context)

    def registered_ids(self) -> set[str]:
        return set(self._handlers)
