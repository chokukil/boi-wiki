from __future__ import annotations

import json
import math
import re
import time
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, Iterator, Protocol
from urllib.parse import urlsplit, urlunsplit

import httpx

from .config import AgentV2Settings


PLACEHOLDER_MARKERS = ("example", "not-needed", "dummy-key", "change-me")


@dataclass
class ModelUsageScope:
    scope_id: str
    token_budget: int
    max_model_calls: int
    max_elapsed_seconds: int
    started_at: float
    events: list[dict[str, Any]]


@dataclass(frozen=True)
class ModelRuntimeProfile:
    provider: str
    model: str
    context_window_tokens: int
    max_output_tokens: int
    source: str


@dataclass(frozen=True)
class ContextBudgetResolution:
    requested_tokens: int
    effective_tokens: int
    context_window_tokens: int
    reserved_tokens: int
    max_output_tokens: int
    profile_source: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "requested_tokens": self.requested_tokens,
            "effective_tokens": self.effective_tokens,
            "context_window_tokens": self.context_window_tokens,
            "reserved_tokens": self.reserved_tokens,
            "max_output_tokens": self.max_output_tokens,
            "profile_source": self.profile_source,
        }


_MODEL_USAGE_SCOPE: ContextVar[ModelUsageScope | None] = ContextVar("boi_model_usage_scope", default=None)
_PROVIDER_USAGE_EVENTS: ContextVar[list[dict[str, Any]]] = ContextVar("boi_provider_usage_events", default=[])
_MODEL_RUNTIME_PROFILE_CACHE: dict[tuple[str, str, str], tuple[float, ModelRuntimeProfile]] = {}


def _estimate_tokens(value: Any) -> int:
    if not value:
        return 0
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return max(1, math.ceil(len(text.encode("utf-8")) / 4))


def begin_model_usage(
    scope_id: str,
    token_budget: int,
    *,
    max_model_calls: int = 20,
    max_elapsed_seconds: int = 300,
) -> Token:
    return _MODEL_USAGE_SCOPE.set(
        ModelUsageScope(
            scope_id=scope_id,
            token_budget=max(0, int(token_budget)),
            max_model_calls=max(0, int(max_model_calls)),
            max_elapsed_seconds=max(1, int(max_elapsed_seconds)),
            started_at=time.perf_counter(),
            events=[],
        )
    )


def update_model_usage_limits(*, max_model_calls: int, max_elapsed_seconds: int) -> None:
    scope = _MODEL_USAGE_SCOPE.get()
    if scope is None:
        return
    scope.max_model_calls = max(0, int(max_model_calls))
    scope.max_elapsed_seconds = max(1, int(max_elapsed_seconds))


def update_model_token_budget(token_budget: int) -> None:
    scope = _MODEL_USAGE_SCOPE.get()
    if scope is None:
        return
    scope.token_budget = max(0, int(token_budget))


def finish_model_usage(token: Token) -> dict[str, Any]:
    scope = _MODEL_USAGE_SCOPE.get()
    events = list(scope.events) if scope else []
    input_tokens = sum(int(item.get("input_tokens") or item.get("input_tokens_estimate") or 0) for item in events)
    output_tokens = sum(int(item.get("output_tokens") or item.get("output_tokens_estimate") or 0) for item in events)
    measured = [item for item in events if item.get("kind") in {"structured", "stream", "embedding"}]
    actual_count = sum(1 for item in measured if item.get("accounting") == "actual")
    accounting = "actual" if measured and actual_count == len(measured) else "mixed" if actual_count else "estimated"
    token_budget = int(scope.token_budget if scope else 0)
    summary = {
        "scope_id": str(scope.scope_id if scope else ""),
        "accounting": accounting,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "input_tokens_estimate": input_tokens,
        "output_tokens_estimate": output_tokens,
        "total_tokens_estimate": input_tokens + output_tokens,
        "token_budget": token_budget,
        "max_model_calls": int(scope.max_model_calls if scope else 0),
        "max_elapsed_seconds": int(scope.max_elapsed_seconds if scope else 0),
        "elapsed_ms": int((time.perf_counter() - scope.started_at) * 1000) if scope else 0,
        "remaining_tokens_estimate": max(0, token_budget - input_tokens - output_tokens) if token_budget else 0,
        "model_calls": sum(1 for item in events if item.get("kind") in {"structured", "stream"}),
        "embedding_calls": sum(1 for item in events if item.get("kind") == "embedding"),
        "events": events,
    }
    _MODEL_USAGE_SCOPE.reset(token)
    return summary


def _record_provider_usage(kind: str, usage: Any) -> None:
    if usage is None:
        return
    if not isinstance(usage, dict):
        usage = {
            name: getattr(usage, name, None)
            for name in ("input_tokens", "output_tokens", "total_tokens", "prompt_tokens", "completion_tokens")
        }
    input_tokens = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or input_tokens + output_tokens)
    if not (input_tokens or output_tokens or total_tokens):
        return
    events = list(_PROVIDER_USAGE_EVENTS.get())
    events.append(
        {
            "kind": kind,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }
    )
    _PROVIDER_USAGE_EVENTS.set(events[-20:])


def _consume_provider_usage(kind: str) -> dict[str, int]:
    events = list(_PROVIDER_USAGE_EVENTS.get())
    for index in range(len(events) - 1, -1, -1):
        if events[index].get("kind") == kind:
            usage = events.pop(index)
            _PROVIDER_USAGE_EVENTS.set(events)
            return {
                "input_tokens": int(usage.get("input_tokens") or 0),
                "output_tokens": int(usage.get("output_tokens") or 0),
                "total_tokens": int(usage.get("total_tokens") or 0),
            }
    return {}


def _configured(value: str) -> bool:
    lowered = (value or "").lower()
    return bool(value.strip()) and not any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def compact_error_body(value: str, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _lmstudio_native_base_url(settings: AgentV2Settings) -> str:
    if settings.lmstudio_native_base_url:
        return settings.lmstudio_native_base_url
    model_url = urlsplit(settings.model_base_url)
    embedding_url = urlsplit(settings.embedding_base_url)
    if not model_url.scheme or not model_url.netloc:
        return ""
    if (model_url.scheme, model_url.netloc) != (embedding_url.scheme, embedding_url.netloc):
        return ""
    path = model_url.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3]
    return urlunsplit((model_url.scheme, model_url.netloc, path.rstrip("/"), "", "")).rstrip("/")


def lmstudio_model_residency_state(settings: AgentV2Settings) -> dict[str, Any]:
    required = list(dict.fromkeys(item for item in (settings.model_name, settings.embedding_model) if item))
    configured = bool(settings.lmstudio_require_preloaded_models)
    return {
        "configured": configured,
        "management": "external",
        "status": "pending" if configured else "disabled",
        "ready": None,
        "generation_ready": None,
        "embedding_ready": None,
        "generation_model": settings.model_name,
        "embedding_model": settings.embedding_model,
        "required_models": required,
        "loaded_models": [],
        "manual_models": [],
        "jit_models": [],
        "jit_loading_detected": None,
        "openai_visible_models": [],
        "runtime_profiles": {},
        "generation_context_window": 0,
        "generation_max_context_window": 0,
        "missing_models": required if configured else [],
        "load_requests": [],
        "unload_requests": 0,
    }


def inspect_lmstudio_model_residency(settings: AgentV2Settings) -> dict[str, Any]:
    """Inspect externally managed LM Studio models without loading or unloading anything."""
    state = lmstudio_model_residency_state(settings)
    if not settings.lmstudio_require_preloaded_models:
        return state
    if settings.model_provider != "openai_compatible" or settings.embedding_provider not in {
        "openai",
        "openai_compatible",
    }:
        return {
            **state,
            "status": "skipped",
            "ready": False,
            "reason": "model providers are not LM Studio compatible",
        }
    native_base_url = _lmstudio_native_base_url(settings)
    if not native_base_url:
        return {
            **state,
            "status": "skipped",
            "ready": False,
            "reason": "generation and embedding models do not share one LM Studio server",
        }
    required = state["required_models"]
    if not required:
        return {**state, "status": "skipped", "ready": False, "reason": "no models are configured"}

    headers = (
        {"Authorization": f"Bearer {settings.model_api_key}"}
        if settings.model_api_key
        else {}
    )
    try:
        with httpx.Client(timeout=settings.lmstudio_startup_timeout_seconds) as client:
            response = client.get(f"{native_base_url}/api/v1/models", headers=headers)
            response.raise_for_status()
            rows = response.json().get("models") or []
            openai_response = client.get(f"{settings.model_base_url}/models", headers=headers)
            openai_response.raise_for_status()
            openai_rows = openai_response.json().get("data") or []
    except Exception as exc:
        return {
            **state,
            "status": "unavailable",
            "ready": False,
            "reason": f"{type(exc).__name__}: {compact_error_body(str(exc))}",
        }

    loaded: set[str] = set()
    manual: set[str] = set()
    jit: set[str] = set()
    runtime_profiles: dict[str, dict[str, int]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or "")
        instances = [item for item in row.get("loaded_instances") or [] if isinstance(item, dict)]
        if not key:
            continue
        loaded_context_lengths = [
            int((item.get("config") or {}).get("context_length") or 0)
            for item in instances
            if isinstance(item.get("config"), dict)
        ]
        runtime_profiles[key] = {
            "context_window_tokens": max(loaded_context_lengths or [0]),
            "max_context_window_tokens": int(row.get("max_context_length") or 0),
        }
        if not instances:
            continue
        loaded.add(key)
        if any(item.get("remaining_ttl_seconds") is None for item in instances):
            manual.add(key)
        if any(item.get("remaining_ttl_seconds") is not None for item in instances):
            jit.add(key)

    loaded_required = [model for model in required if model in loaded]
    manual_required = [model for model in required if model in manual]
    jit_required = [model for model in required if model in jit]
    missing = [model for model in required if model not in loaded]
    jit_only = [model for model in required if model in loaded and model not in manual]
    openai_visible = sorted(
        {
            str(row.get("id") or "")
            for row in openai_rows
            if isinstance(row, dict) and row.get("id")
        }
    )
    jit_loading_detected = any(model not in loaded for model in openai_visible)
    generation_profile = runtime_profiles.get(settings.model_name) or {}
    # JIT may remain enabled for other clients. The local guard only needs to
    # prove that every configured model already has a non-TTL instance, so our
    # requests cannot trigger a load or depend on an auto-evicted instance.
    generation_ready = bool(settings.model_name and settings.model_name in manual)
    embedding_ready = bool(settings.embedding_model and settings.embedding_model in manual)
    ready = generation_ready and embedding_ready
    status = "ready"
    if missing:
        status = "missing"
    elif jit_only:
        status = "jit_only"
    elif jit_required:
        status = "ready_with_jit_duplicates"
    elif jit_loading_detected:
        status = "ready_with_jit_enabled"
    return {
        **state,
        "status": status,
        "ready": ready,
        "generation_ready": generation_ready,
        "embedding_ready": embedding_ready,
        "loaded_models": loaded_required,
        "manual_models": manual_required,
        "jit_models": jit_required,
        "jit_loading_detected": jit_loading_detected,
        "openai_visible_models": openai_visible,
        "runtime_profiles": runtime_profiles,
        "generation_context_window": int(generation_profile.get("context_window_tokens") or 0),
        "generation_max_context_window": int(generation_profile.get("max_context_window_tokens") or 0),
        "missing_models": missing,
        "reason": (
            "Load every configured model manually without a TTL before retrying."
            if not ready
            else ""
        ),
    }


def _context_window_from_model_row(row: dict[str, Any]) -> int:
    for key in (
        "context_window",
        "context_window_tokens",
        "context_length",
        "max_context_length",
        "max_input_tokens",
    ):
        try:
            value = int(row.get(key) or 0)
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            return value
    return 0


def inspect_model_runtime_profile(
    settings: AgentV2Settings,
    *,
    residency_state: dict[str, Any] | None = None,
) -> ModelRuntimeProfile:
    """Resolve capacity from explicit config or read-only provider metadata.

    Model names never select a budget profile. Providers that do not publish a
    context window use the deployment fallback, which operators can override.
    """

    if settings.model_context_window_tokens > 0:
        return ModelRuntimeProfile(
            provider=settings.model_provider,
            model=settings.model_name,
            context_window_tokens=settings.model_context_window_tokens,
            max_output_tokens=settings.model_max_output_tokens,
            source="deployment_config",
        )

    state = residency_state or {}
    detected = int(state.get("generation_context_window") or 0)
    if detected > 0:
        return ModelRuntimeProfile(
            provider=settings.model_provider,
            model=settings.model_name,
            context_window_tokens=detected,
            max_output_tokens=settings.model_max_output_tokens,
            source="provider_runtime",
        )

    if settings.lmstudio_require_preloaded_models and settings.model_name:
        inspected = inspect_lmstudio_model_residency(settings)
        detected = int(inspected.get("generation_context_window") or 0)
        if detected > 0:
            return ModelRuntimeProfile(
                provider=settings.model_provider,
                model=settings.model_name,
                context_window_tokens=detected,
                max_output_tokens=settings.model_max_output_tokens,
                source="provider_runtime",
            )

    cache_key = (settings.model_provider, settings.model_base_url, settings.model_name)
    cached = _MODEL_RUNTIME_PROFILE_CACHE.get(cache_key)
    if cached and cached[0] > time.monotonic():
        return cached[1]

    if settings.model_base_url and settings.model_name:
        headers = (
            {"Authorization": f"Bearer {settings.model_api_key}"}
            if settings.model_api_key
            else {}
        )
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{settings.model_base_url}/models", headers=headers)
                response.raise_for_status()
                rows = response.json().get("data") or response.json().get("models") or []
            row = next(
                (
                    item
                    for item in rows
                    if isinstance(item, dict)
                    and str(item.get("id") or item.get("key") or "") == settings.model_name
                ),
                {},
            )
            detected = _context_window_from_model_row(row)
        except Exception:
            detected = 0
        if detected > 0:
            profile = ModelRuntimeProfile(
                provider=settings.model_provider,
                model=settings.model_name,
                context_window_tokens=detected,
                max_output_tokens=settings.model_max_output_tokens,
                source="provider_catalog",
            )
            _MODEL_RUNTIME_PROFILE_CACHE[cache_key] = (time.monotonic() + 60.0, profile)
            return profile

    profile = ModelRuntimeProfile(
        provider=settings.model_provider,
        model=settings.model_name,
        context_window_tokens=settings.model_context_fallback_tokens,
        max_output_tokens=settings.model_max_output_tokens,
        source="deployment_fallback",
    )
    _MODEL_RUNTIME_PROFILE_CACHE[cache_key] = (time.monotonic() + 60.0, profile)
    return profile


def resolve_context_budget(
    settings: AgentV2Settings,
    *,
    requested_tokens: int,
    residency_state: dict[str, Any] | None = None,
) -> ContextBudgetResolution:
    profile = inspect_model_runtime_profile(settings, residency_state=residency_state)
    reserved = min(
        settings.model_context_reserve_tokens,
        max(2_048, profile.context_window_tokens // 4),
    )
    usable = max(
        1_000,
        profile.context_window_tokens - profile.max_output_tokens - reserved,
    )
    requested = max(0, int(requested_tokens))
    effective = usable if requested == 0 else min(requested, usable)
    return ContextBudgetResolution(
        requested_tokens=requested,
        effective_tokens=effective,
        context_window_tokens=profile.context_window_tokens,
        reserved_tokens=reserved,
        max_output_tokens=profile.max_output_tokens,
        profile_source=profile.source,
    )


def ensure_lmstudio_model_residency(settings: AgentV2Settings) -> dict[str, Any]:
    """Compatibility wrapper for the former name; this still performs read-only inspection."""

    return inspect_lmstudio_model_residency(settings)


def require_lmstudio_models_preloaded(
    settings: AgentV2Settings,
    *,
    required_models: list[str] | tuple[str, ...] | None = None,
) -> None:
    if not settings.lmstudio_require_preloaded_models:
        return
    state = inspect_lmstudio_model_residency(settings)
    required = list(
        dict.fromkeys(
            model
            for model in (
                required_models
                if required_models is not None
                else (settings.model_name, settings.embedding_model)
            )
            if model
        )
    )
    manual = set(state.get("manual_models") or [])
    if required and all(model in manual for model in required):
        return
    loaded = set(state.get("loaded_models") or [])
    missing = ", ".join(model for model in required if model not in loaded)
    jit_only = ", ".join(
        model
        for model in required
        if model in loaded and model not in manual
    )
    detail = missing or jit_only or str(state.get("reason") or state.get("status") or "not ready")
    raise RuntimeError(
        "LM Studio preloaded model guard blocked JIT loading: "
        f"{detail}. Load the required model manually without a TTL before retrying."
    )


def parse_json_object(value: str) -> dict[str, Any]:
    clean = (value or "").strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*", "", clean)
        clean = re.sub(r"\s*```$", "", clean)
    try:
        payload = json.loads(clean)
    except json.JSONDecodeError:
        start = clean.find("{")
        end = clean.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("model did not return a JSON object")
        payload = json.loads(clean[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("model output must be a JSON object")
    return payload


class ModelGateway(Protocol):
    provider: str

    def readiness(self) -> dict[str, Any]: ...

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]: ...

    def stream_text(self, *, system: str, prompt: str) -> Iterator[str]: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def preflight(self) -> dict[str, Any]: ...


class OpenAIEmbeddingGateway:
    def __init__(self, settings: AgentV2Settings):
        self.settings = settings

    @property
    def ready(self) -> bool:
        provider = self.settings.embedding_provider
        credentials_ready = _configured(self.settings.embedding_api_key) if provider == "openai" else True
        return bool(
            provider in {"openai", "openai_compatible"}
            and self.settings.embedding_base_url
            and self.settings.embedding_model
            and credentials_ready
        )

    def readiness(self) -> dict[str, Any]:
        return {
            "embeddings": self.ready,
            "embedding_provider": self.settings.embedding_provider,
            "embedding_model": self.settings.embedding_model,
            "embedding_base_url": self.settings.embedding_base_url,
        }

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.ready:
            raise RuntimeError("embedding adapter is not configured")
        require_lmstudio_models_preloaded(
            self.settings,
            required_models=[self.settings.embedding_model],
        )
        headers = (
            {"Authorization": f"Bearer {self.settings.embedding_api_key}"}
            if self.settings.embedding_api_key
            else {}
        )
        response = httpx.post(
            f"{self.settings.embedding_base_url}/embeddings",
            headers=headers,
            json={"model": self.settings.embedding_model, "input": texts},
            timeout=60,
        )
        response.raise_for_status()
        body = response.json()
        _record_provider_usage("embedding", body.get("usage"))
        vectors = [list(item["embedding"]) for item in body.get("data") or []]
        if len(vectors) != len(texts):
            raise RuntimeError("embedding adapter returned an unexpected vector count")
        for vector in vectors:
            if len(vector) != self.settings.embedding_dimensions:
                raise RuntimeError(
                    f"embedding dimension mismatch: expected {self.settings.embedding_dimensions}, got {len(vector)}"
                )
        return vectors


class CompositeModelGateway:
    def __init__(self, generation: ModelGateway, embedding: OpenAIEmbeddingGateway):
        self.generation = generation
        self.embedding = embedding
        self.provider = generation.provider

    def readiness(self) -> dict[str, Any]:
        return {**self.generation.readiness(), **self.embedding.readiness()}

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        return self.generation.generate_structured(system=system, prompt=prompt, schema=schema)

    def stream_text(self, *, system: str, prompt: str) -> Iterator[str]:
        return self.generation.stream_text(system=system, prompt=prompt)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.embedding.embed(texts)

    def preflight(self) -> dict[str, Any]:
        return {**self.generation.preflight(), **self.embedding.readiness()}


class UsageTrackingGateway:
    """Adds scoped, provider-neutral usage visibility without changing model responses."""

    def __init__(self, delegate: ModelGateway):
        self.delegate = delegate
        self.provider = delegate.provider

    def readiness(self) -> dict[str, Any]:
        return {**self.delegate.readiness(), "usage_tracking": "provider_actual_with_estimate_fallback"}

    def preflight(self) -> dict[str, Any]:
        return {**self.delegate.preflight(), "usage_tracking": "provider_actual_with_estimate_fallback"}

    @staticmethod
    def _check_budget(input_tokens: int, *, kind: str) -> None:
        scope = _MODEL_USAGE_SCOPE.get()
        if not scope:
            return
        if time.perf_counter() - scope.started_at > scope.max_elapsed_seconds:
            raise RuntimeError("model elapsed-time budget exceeded before the next call")
        if kind in {"structured", "stream"}:
            model_calls = sum(
                1 for item in scope.events if item.get("kind") in {"structured", "stream"}
            )
            if model_calls >= scope.max_model_calls:
                raise RuntimeError("model call budget exceeded before the next call")
        if not scope.token_budget:
            return
        used = sum(
            int(item.get("input_tokens") or item.get("input_tokens_estimate") or 0)
            + int(item.get("output_tokens") or item.get("output_tokens_estimate") or 0)
            for item in scope.events
        )
        if used + input_tokens > scope.token_budget:
            raise RuntimeError("model token budget exceeded before the next call")

    def _record(
        self,
        *,
        kind: str,
        input_tokens: int,
        output_tokens: int,
        elapsed_ms: int,
        item_count: int = 1,
        status: str = "completed",
        actual_usage: dict[str, int] | None = None,
        error: str = "",
    ) -> None:
        scope = _MODEL_USAGE_SCOPE.get()
        if not scope:
            return
        readiness = self.delegate.readiness()
        actual_usage = actual_usage or {}
        event = {
                "kind": kind,
                "provider": self.provider,
                "model": readiness.get("embedding_model") if kind == "embedding" else readiness.get("model"),
                "input_tokens_estimate": input_tokens,
                "output_tokens_estimate": output_tokens,
                "item_count": item_count,
                "elapsed_ms": elapsed_ms,
                "status": status,
                "accounting": "actual" if actual_usage else "estimated",
            }
        if actual_usage:
            event.update(actual_usage)
        if error:
            event["error"] = error[:500]
        scope.events.append(event)

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        input_tokens = _estimate_tokens(system) + _estimate_tokens(prompt) + _estimate_tokens(schema)
        self._check_budget(input_tokens, kind="structured")
        started = time.perf_counter()
        try:
            result = self.delegate.generate_structured(system=system, prompt=prompt, schema=schema)
        except Exception as exc:
            self._record(
                kind="structured",
                input_tokens=input_tokens,
                output_tokens=0,
                elapsed_ms=int((time.perf_counter() - started) * 1000),
                status="failed",
                actual_usage=_consume_provider_usage("structured"),
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        self._record(
            kind="structured",
            input_tokens=input_tokens,
            output_tokens=_estimate_tokens(result),
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            actual_usage=_consume_provider_usage("structured"),
        )
        return result

    def stream_text(self, *, system: str, prompt: str) -> Iterator[str]:
        input_tokens = _estimate_tokens(system) + _estimate_tokens(prompt)
        self._check_budget(input_tokens, kind="stream")
        started = time.perf_counter()
        chunks: list[str] = []
        status = "completed"
        try:
            for chunk in self.delegate.stream_text(system=system, prompt=prompt):
                chunks.append(chunk)
                yield chunk
        except Exception:
            status = "failed"
            raise
        finally:
            self._record(
                kind="stream",
                input_tokens=input_tokens,
                output_tokens=_estimate_tokens("".join(chunks)),
                elapsed_ms=int((time.perf_counter() - started) * 1000),
                status=status,
                actual_usage=_consume_provider_usage("stream"),
            )

    def embed(self, texts: list[str]) -> list[list[float]]:
        input_tokens = _estimate_tokens(texts)
        self._check_budget(input_tokens, kind="embedding")
        started = time.perf_counter()
        try:
            result = self.delegate.embed(texts)
        except Exception:
            self._record(
                kind="embedding",
                input_tokens=input_tokens,
                output_tokens=0,
                elapsed_ms=int((time.perf_counter() - started) * 1000),
                item_count=len(texts),
                status="failed",
            )
            raise
        self._record(
            kind="embedding",
            input_tokens=input_tokens,
            output_tokens=0,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            item_count=len(texts),
            actual_usage=_consume_provider_usage("embedding"),
        )
        return result


@dataclass
class UnavailableModelGateway:
    reason: str
    provider: str = "unavailable"

    def readiness(self) -> dict[str, Any]:
        return {
            "configured": False,
            "generation": False,
            "streaming": False,
            "embeddings": False,
            "provider": self.provider,
            "reason": self.reason,
        }

    def _raise(self) -> None:
        raise RuntimeError(self.reason)

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        self._raise()

    def stream_text(self, *, system: str, prompt: str) -> Iterator[str]:
        self._raise()
        yield ""

    def embed(self, texts: list[str]) -> list[list[float]]:
        self._raise()

    def preflight(self) -> dict[str, Any]:
        return {**self.readiness(), "ok": False}


class OpenAIResponsesGateway:
    provider = "openai_responses"

    def __init__(self, settings: AgentV2Settings):
        from openai import OpenAI

        self.settings = settings
        self.client = OpenAI(api_key=settings.model_api_key, base_url=settings.model_base_url)

    @property
    def generation_ready(self) -> bool:
        return _configured(self.settings.model_api_key) and bool(self.settings.model_name)

    @property
    def embedding_ready(self) -> bool:
        return _configured(self.settings.model_api_key) and bool(self.settings.embedding_model)

    def readiness(self) -> dict[str, Any]:
        return {
            "configured": self.generation_ready,
            "generation": self.generation_ready,
            "streaming": self.generation_ready,
            "embeddings": self.embedding_ready,
            "provider": self.provider,
            "model": self.settings.model_name,
            "embedding_model": self.settings.embedding_model,
            "reasoning_effort": self.settings.model_reasoning_effort or "provider_default",
            "max_output_tokens": self.settings.model_max_output_tokens,
        }

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if not self.generation_ready:
            raise RuntimeError("OpenAI Responses model is not configured")
        response = self.client.responses.create(
            model=self.settings.model_name,
            instructions=system,
            input=prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "boi_v2_draft",
                    "schema": schema,
                    "strict": False,
                }
            },
        )
        _record_provider_usage("structured", getattr(response, "usage", None))
        return parse_json_object(str(response.output_text or ""))

    def stream_text(self, *, system: str, prompt: str) -> Iterator[str]:
        if not self.generation_ready:
            raise RuntimeError("OpenAI Responses model is not configured")
        with self.client.responses.stream(model=self.settings.model_name, instructions=system, input=prompt) as stream:
            for event in stream:
                if getattr(event, "type", "") == "response.output_text.delta":
                    delta = str(getattr(event, "delta", "") or "")
                    if delta:
                        yield delta
            final_getter = getattr(stream, "get_final_response", None)
            if callable(final_getter):
                final_response = final_getter()
                _record_provider_usage("stream", getattr(final_response, "usage", None))

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.embedding_ready:
            raise RuntimeError("embedding model is not configured")
        response = self.client.embeddings.create(model=self.settings.embedding_model, input=texts)
        _record_provider_usage("embedding", getattr(response, "usage", None))
        vectors = [list(item.embedding) for item in response.data]
        for vector in vectors:
            if len(vector) != self.settings.embedding_dimensions:
                raise RuntimeError(
                    f"embedding dimension mismatch: expected {self.settings.embedding_dimensions}, got {len(vector)}"
                )
        return vectors

    def preflight(self) -> dict[str, Any]:
        result = self.readiness()
        if not self.generation_ready:
            return {**result, "ok": False, "reason": "generation model is not configured"}
        try:
            response = self.client.responses.create(
                model=self.settings.model_name,
                input="Reply with exactly: ok",
                max_output_tokens=16,
            )
            return {**result, "ok": bool(str(response.output_text or "").strip())}
        except Exception as exc:
            return {**result, "ok": False, "reason": f"{type(exc).__name__}: {exc}"}


class OpenAICompatibleGateway:
    provider = "openai_compatible"

    def __init__(self, settings: AgentV2Settings):
        self.settings = settings

    @property
    def generation_ready(self) -> bool:
        return bool(self.settings.model_base_url and self.settings.model_name)

    @property
    def embedding_ready(self) -> bool:
        return bool(self.settings.model_base_url and self.settings.embedding_model)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.settings.model_api_key}"} if self.settings.model_api_key else {}

    def readiness(self) -> dict[str, Any]:
        return {
            "configured": self.generation_ready,
            "generation": self.generation_ready,
            "streaming": self.generation_ready,
            "embeddings": self.embedding_ready,
            "provider": self.provider,
            "model": self.settings.model_name,
            "embedding_model": self.settings.embedding_model,
            "reasoning_effort": self.settings.model_reasoning_effort or "provider_default",
            "max_output_tokens": self.settings.model_max_output_tokens,
        }

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if not self.generation_ready:
            raise RuntimeError("OpenAI-compatible model is not configured")
        require_lmstudio_models_preloaded(
            self.settings,
            required_models=[self.settings.model_name],
        )
        request_payload: dict[str, Any] = {
            "model": self.settings.model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "boi_v2_response",
                    "strict": False,
                    "schema": schema,
                },
            },
            "temperature": 0,
            "max_tokens": self.settings.model_max_output_tokens,
        }
        if self.settings.model_reasoning_effort:
            request_payload["reasoning_effort"] = self.settings.model_reasoning_effort
        response = httpx.post(
            f"{self.settings.model_base_url}/chat/completions",
            headers=self._headers(),
            json=request_payload,
            timeout=60,
        )
        if not response.is_success:
            raise RuntimeError(
                f"OpenAI-compatible generation failed with HTTP {response.status_code}: "
                f"{compact_error_body(response.text)}"
            )
        body = response.json()
        _record_provider_usage("structured", body.get("usage"))
        choice = (body.get("choices") or [{}])[0]
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        content = str(message.get("content") or "")
        try:
            return parse_json_object(content)
        except ValueError as exc:
            raise RuntimeError(
                "OpenAI-compatible model did not return the required JSON "
                f"(finish_reason={choice.get('finish_reason') or 'unknown'}, "
                f"content_chars={len(content)}, reasoning_chars={len(str(message.get('reasoning_content') or ''))})"
            ) from exc

    def stream_text(self, *, system: str, prompt: str) -> Iterator[str]:
        # The v2 API streams execution state independently. Providers that do
        # not expose a compatible delta stream still return one answer chunk.
        payload = self.generate_structured(
            system=system,
            prompt=f"Return JSON with one field named text.\n{prompt}",
            schema={"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}},
        )
        structured_usage = _consume_provider_usage("structured")
        if structured_usage:
            _record_provider_usage("stream", structured_usage)
        yield str(payload.get("text") or "")

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.embedding_ready:
            raise RuntimeError("embedding model is not configured")
        require_lmstudio_models_preloaded(
            self.settings,
            required_models=[self.settings.embedding_model],
        )
        response = httpx.post(
            f"{self.settings.model_base_url}/embeddings",
            headers=self._headers(),
            json={"model": self.settings.embedding_model, "input": texts},
            timeout=60,
        )
        response.raise_for_status()
        body = response.json()
        _record_provider_usage("embedding", body.get("usage"))
        vectors = [list(item["embedding"]) for item in body.get("data") or []]
        for vector in vectors:
            if len(vector) != self.settings.embedding_dimensions:
                raise RuntimeError("embedding dimension mismatch")
        return vectors

    def preflight(self) -> dict[str, Any]:
        try:
            result = self.generate_structured(
                system="Return valid JSON.",
                prompt="Return {\"ok\": true}.",
                schema={"type": "object", "required": ["ok"]},
            )
            return {**self.readiness(), "ok": result.get("ok") is True}
        except Exception as exc:
            return {**self.readiness(), "ok": False, "reason": f"{type(exc).__name__}: {exc}"}


class AnthropicGateway:
    provider = "anthropic"

    def __init__(self, settings: AgentV2Settings):
        self.settings = settings

    def readiness(self) -> dict[str, Any]:
        configured = _configured(self.settings.model_api_key) and bool(self.settings.model_name)
        return {
            "configured": configured,
            "generation": configured,
            "streaming": configured,
            "embeddings": False,
            "provider": self.provider,
            "model": self.settings.model_name,
        }

    def generate_structured(self, *, system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if not self.readiness()["generation"]:
            raise RuntimeError("Anthropic model is not configured")
        response = httpx.post(
            f"{self.settings.model_base_url}/messages",
            headers={
                "x-api-key": self.settings.model_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.settings.model_name,
                "max_tokens": 2048,
                "system": system,
                "messages": [
                    {
                        "role": "user",
                        "content": f"{prompt}\nReturn one JSON object matching: {json.dumps(schema, ensure_ascii=False)}",
                    }
                ],
            },
            timeout=60,
        )
        response.raise_for_status()
        body = response.json()
        _record_provider_usage("structured", body.get("usage"))
        content = "".join(str(block.get("text") or "") for block in body.get("content") or [])
        return parse_json_object(content)

    def stream_text(self, *, system: str, prompt: str) -> Iterator[str]:
        result = self.generate_structured(
            system=system,
            prompt=f"Return JSON with one field named text.\n{prompt}",
            schema={"type": "object", "required": ["text"]},
        )
        structured_usage = _consume_provider_usage("structured")
        if structured_usage:
            _record_provider_usage("stream", structured_usage)
        yield str(result.get("text") or "")

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Anthropic adapter does not provide embeddings; configure a separate embedding provider")

    def preflight(self) -> dict[str, Any]:
        try:
            result = self.generate_structured(
                system="Return valid JSON.",
                prompt="Return {\"ok\": true}.",
                schema={"type": "object", "required": ["ok"]},
            )
            return {**self.readiness(), "ok": result.get("ok") is True}
        except Exception as exc:
            return {**self.readiness(), "ok": False, "reason": f"{type(exc).__name__}: {exc}"}


def build_model_gateway(settings: AgentV2Settings) -> ModelGateway:
    try:
        generation: ModelGateway
        if settings.model_provider == "openai_responses":
            generation = OpenAIResponsesGateway(settings)
        elif settings.model_provider == "openai_compatible":
            generation = OpenAICompatibleGateway(settings)
        elif settings.model_provider == "anthropic":
            generation = AnthropicGateway(settings)
        else:
            generation = UnavailableModelGateway(f"unsupported model provider: {settings.model_provider}")
        return UsageTrackingGateway(CompositeModelGateway(generation, OpenAIEmbeddingGateway(settings)))
    except Exception as exc:
        return UsageTrackingGateway(
            UnavailableModelGateway(f"model gateway unavailable: {type(exc).__name__}: {exc}")
        )
