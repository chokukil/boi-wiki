from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def deep_subagent_budget_limit(
    token_budget: int,
    max_input_tokens: int,
    *,
    hard_limit: int = 4,
    min_window_tokens: int = 16_000,
) -> int:
    """Reserve parent/review windows without treating provider capacity as mandatory spend."""
    if token_budget <= 0 or max_input_tokens <= 0:
        return 0
    planning_window = min(max_input_tokens, max(4_000, int(min_window_tokens)))
    available = token_budget // planning_window - 2
    return max(0, min(int(hard_limit), available))


@dataclass(frozen=True)
class AgentV2Settings:
    enabled: bool
    default_enabled: bool
    content_root: Path
    runtime_root: Path
    history_seed_root: Path | None
    agent_catalog_root: Path
    event_catalog_root: Path
    action_catalog_root: Path
    workflow_catalog_root: Path
    action_skill_catalog_root: Path
    database_dsn: str
    require_postgres: bool
    embedding_provider: str
    embedding_base_url: str
    embedding_api_key: str
    embedding_model: str
    embedding_dimensions: int
    model_provider: str
    model_base_url: str
    model_api_key: str
    model_name: str
    deep_model: str
    model_reasoning_effort: str
    model_max_output_tokens: int
    model_context_window_tokens: int
    model_context_fallback_tokens: int
    model_context_reserve_tokens: int
    retrieval_candidate_limit: int
    deep_max_input_tokens: int
    deep_min_window_tokens: int
    model_route: str
    gpt55_test_mode: bool
    lmstudio_require_preloaded_models: bool
    lmstudio_native_base_url: str
    lmstudio_startup_timeout_seconds: int
    pat_hash_secret: str
    offer_ttl_seconds: int
    response_budget_bytes: int
    run_token_budget: int
    deep_token_budget: int
    independent_review: bool
    claim_grounding_enabled: bool
    minio_endpoint: str
    minio_bucket: str
    mcp_external_url: str
    worker_stale_seconds: int
    boi_api_url: str
    service_token: str

    @classmethod
    def from_environment(
        cls,
        *,
        repo_root: Path,
        content_root: Path | None = None,
        runtime_root: Path | None = None,
        history_seed_root: Path | None = None,
    ) -> "AgentV2Settings":
        resolved_content = content_root or Path(os.getenv("BOI_CONTENT_ROOT") or repo_root / "data" / "boi")
        resolved_runtime = runtime_root or Path(os.getenv("BOI_RUNTIME_ROOT") or repo_root / ".tmp" / "boi-runtime")
        explicit_seed = os.getenv("BOI_RUNTIME_HISTORY_SEED_ROOT")
        resolved_seed = history_seed_root
        if resolved_seed is None and explicit_seed:
            resolved_seed = Path(explicit_seed)
        gpt55_test_mode = _flag("BOI_GPT55_TEST_MODE", False)
        local_base_url = os.getenv("BOI_LLM_BASE_URL") or ""
        local_api_key = os.getenv("BOI_LLM_API_KEY") or ""
        local_model = os.getenv("BOI_AGENT_LLM_MODEL") or os.getenv("BOI_LLM_MODEL") or ""
        openai_base_url = os.getenv("OPENAI_API_URL") if gpt55_test_mode else ""
        openai_api_key = os.getenv("OPENAI_API_KEY") if gpt55_test_mode else ""
        openai_model = os.getenv("OPENAI_API_MODEL") if gpt55_test_mode else ""
        model_provider = (os.getenv("BOI_V2_MODEL_PROVIDER") or "openai_compatible").strip().lower()
        model_base_url = (
            os.getenv("BOI_V2_MODEL_BASE_URL")
            or local_base_url
            or openai_base_url
            or ""
        )
        model_api_key = (
            os.getenv("BOI_V2_MODEL_API_KEY")
            or local_api_key
            or openai_api_key
            or ""
        )
        model_name = os.getenv("BOI_V2_MODEL") or local_model or openai_model or ""
        deep_model = (os.getenv("BOI_DEEPAGENTS_MODEL") or model_name).strip()
        # Runtime model selection is explicit provider configuration. Never
        # rewrite a configured model because of its name; the same contract
        # must work for local and managed providers.
        model_route = "configured"
        dimensions = max(1, int(os.getenv("BOI_EMBEDDING_DIMENSIONS", "1536") or "1536"))
        embedding_base_url = (
            os.getenv("BOI_EMBEDDING_BASE_URL")
            or local_base_url
            or (model_base_url if model_provider != "anthropic" else "")
            or openai_base_url
            or ""
        )
        embedding_api_key = (
            os.getenv("BOI_EMBEDDING_API_KEY")
            or local_api_key
            or (model_api_key if model_provider != "anthropic" else "")
            or openai_api_key
            or ""
        )
        return cls(
            enabled=_flag("BOI_AGENT_V2_ENABLED", True),
            default_enabled=_flag("BOI_AGENT_V2_DEFAULT", False),
            content_root=resolved_content,
            runtime_root=resolved_runtime,
            history_seed_root=resolved_seed,
            agent_catalog_root=Path(os.getenv("AGENT_CATALOG_ROOT") or repo_root / "data" / "agent_catalog"),
            event_catalog_root=Path(os.getenv("EVENT_CATALOG_ROOT") or repo_root / "data" / "event_catalog"),
            action_catalog_root=Path(os.getenv("ACTION_CATALOG_ROOT") or repo_root / "data" / "action_catalog"),
            workflow_catalog_root=Path(os.getenv("WORKFLOW_CATALOG_ROOT") or repo_root / "data" / "workflow_catalog"),
            action_skill_catalog_root=Path(
                os.getenv("ACTION_SKILL_CATALOG_ROOT") or repo_root / "data" / "action_skill_catalog"
            ),
            database_dsn=os.getenv("BOI_AGENT_V2_DATABASE_URL") or os.getenv("BOI_PGVECTOR_DSN") or "",
            require_postgres=_flag("BOI_AGENT_V2_REQUIRE_POSTGRES", False),
            embedding_provider=(os.getenv("BOI_EMBEDDING_PROVIDER") or "openai").strip().lower(),
            embedding_base_url=embedding_base_url.rstrip("/"),
            embedding_api_key=embedding_api_key,
            embedding_model=(os.getenv("BOI_EMBEDDING_MODEL") or "").strip(),
            embedding_dimensions=dimensions,
            model_provider=model_provider,
            model_base_url=model_base_url.rstrip("/"),
            model_api_key=model_api_key,
            model_name=model_name,
            deep_model=deep_model,
            model_reasoning_effort=(os.getenv("BOI_V2_REASONING_EFFORT") or "").strip().lower(),
            model_max_output_tokens=max(
                512,
                min(int(os.getenv("BOI_V2_MAX_OUTPUT_TOKENS", "8192") or "8192"), 32_768),
            ),
            model_context_window_tokens=max(
                0,
                min(int(os.getenv("BOI_V2_MODEL_CONTEXT_WINDOW", "0") or "0"), 2_000_000),
            ),
            model_context_fallback_tokens=max(
                16_384,
                min(int(os.getenv("BOI_V2_MODEL_CONTEXT_FALLBACK", "131072") or "131072"), 2_000_000),
            ),
            model_context_reserve_tokens=max(
                2_048,
                min(int(os.getenv("BOI_V2_MODEL_CONTEXT_RESERVE", "8192") or "8192"), 131_072),
            ),
            retrieval_candidate_limit=max(
                12,
                min(int(os.getenv("BOI_AGENT_V2_RETRIEVAL_CANDIDATE_LIMIT", "48") or "48"), 500),
            ),
            deep_max_input_tokens=max(
                0,
                min(int(os.getenv("BOI_DEEPAGENTS_MAX_INPUT_TOKENS", "0") or "0"), 2_000_000),
            ),
            deep_min_window_tokens=max(
                4_000,
                min(int(os.getenv("BOI_DEEPAGENTS_MIN_WINDOW_TOKENS", "16000") or "16000"), 262_144),
            ),
            model_route=model_route,
            gpt55_test_mode=gpt55_test_mode,
            lmstudio_require_preloaded_models=_flag(
                "BOI_LMSTUDIO_REQUIRE_PRELOADED_MODELS",
                _flag("BOI_LMSTUDIO_KEEP_MODELS_LOADED", False),
            ),
            lmstudio_native_base_url=(os.getenv("BOI_LMSTUDIO_NATIVE_BASE_URL") or "").strip().rstrip("/"),
            lmstudio_startup_timeout_seconds=max(
                5,
                min(int(os.getenv("BOI_LMSTUDIO_STARTUP_TIMEOUT_SECONDS", "120") or "120"), 600),
            ),
            pat_hash_secret=(os.getenv("BOI_PAT_HASH_SECRET") or os.getenv("BOI_SESSION_SECRET") or "").strip(),
            offer_ttl_seconds=max(60, int(os.getenv("BOI_AGENT_V2_OFFER_TTL_SECONDS", "900") or "900")),
            response_budget_bytes=max(4096, int(os.getenv("BOI_AGENT_V2_RESPONSE_BUDGET_BYTES", "262144") or "262144")),
            run_token_budget=max(4000, int(os.getenv("BOI_AGENT_V2_RUN_TOKEN_BUDGET", "4000000") or "4000000")),
            deep_token_budget=max(4000, int(os.getenv("BOI_AGENT_V2_DEEP_TOKEN_BUDGET", "1000000") or "1000000")),
            independent_review=_flag("BOI_AGENT_V2_INDEPENDENT_REVIEW", True),
            claim_grounding_enabled=_flag("BOI_AGENT_CLAIM_GROUNDING_ENABLED", True),
            minio_endpoint=(os.getenv("BOI_DATALAKE_MINIO_ENDPOINT") or "").strip(),
            minio_bucket=(os.getenv("BOI_DATALAKE_BUCKET") or "boi-datalake").strip(),
            mcp_external_url=cls._mcp_v2_url(os.getenv("BOI_WIKI_MCP_EXTERNAL_URL") or "http://localhost:8200"),
            worker_stale_seconds=max(30, int(os.getenv("BOI_AGENT_V2_WORKER_STALE_SECONDS", "90") or "90")),
            boi_api_url=(os.getenv("BOI_API_URL") or "http://127.0.0.1:8765").strip().rstrip("/"),
            service_token=(os.getenv("BOI_API_SERVICE_TOKEN") or os.getenv("SERVICE_TOKEN") or "").strip(),
        )

    @staticmethod
    def _mcp_v2_url(value: str) -> str:
        clean = str(value or "").strip().rstrip("/")
        return clean if clean.endswith("/mcp/v2") else clean + "/mcp/v2"
