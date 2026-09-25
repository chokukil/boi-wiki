from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from .models import Principal


DomainHandler = Callable[[Principal, dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]]


class DomainServiceGateway:
    """Injected bridge to the existing BoI domain services.

    Agent v2 owns orchestration state, but SOP/Event/Action/Skill drafts and
    executions remain owned by the same services used by the ordinary Web API.
    """

    def __init__(self, handlers: dict[str, DomainHandler] | None = None) -> None:
        self._handlers = dict(handlers or {})

    def supports(self, operation: str) -> bool:
        return operation in self._handlers

    def operations(self) -> list[str]:
        return sorted(self._handlers)

    def execute(self, operation: str, principal: Principal, payload: dict[str, Any]) -> dict[str, Any]:
        handler = self._handlers.get(operation)
        if handler is None:
            raise RuntimeError(f"domain operation is unavailable: {operation}")
        result = handler(principal, payload)
        if inspect.isawaitable(result):
            close = getattr(result, "close", None)
            if callable(close):
                close()
            raise RuntimeError(f"domain operation requires async execution: {operation}")
        if not isinstance(result, dict):
            raise RuntimeError(f"domain operation returned an invalid result: {operation}")
        return result

    async def execute_async(
        self,
        operation: str,
        principal: Principal,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        handler = self._handlers.get(operation)
        if handler is None:
            raise RuntimeError(f"domain operation is unavailable: {operation}")
        result = handler(principal, payload)
        if inspect.isawaitable(result):
            result = await result
        if not isinstance(result, dict):
            raise RuntimeError(f"domain operation returned an invalid result: {operation}")
        return result
