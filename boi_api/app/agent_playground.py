from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException
from pydantic import BaseModel, Field

from .agent_playground_credentials import PlaygroundCredentialService, TokenCreateRequest
from .auth import AuthIdentity


LANGFLOW_MIN_VERSION = (1, 11, 0)
LANGFLOW_MAX_VERSION = (1, 12, 0)
CANONICAL_FLOW_NAME = "BoI Wiki Agent Loop"
CANONICAL_FLOW_ENDPOINT = "boi-wiki-agent-loop"
CANONICAL_FLOW_VERSION = "1.1.0"
MODEL_AGENT_FLOW_NAME = "BoI Wiki Agent Loop - Model Agent Example"
MODEL_AGENT_FLOW_ENDPOINT = "boi-wiki-agent-loop-model-agent"
COMPONENT_BUNDLE_VERSION = "1.1.0"
COMPONENT_BUNDLE_MODE = "read_only_extension"
REQUIRED_BUNDLE_COMPONENTS = (
    "BoIWikiKnowledge",
    "BoIWikiSave",
    "BoIModelAgent",
)
PROJECT_PREFIX = "boi-"
BOI_PAT_VARIABLE_NAME = "BOI_WIKI_PAT"
BOI_LLM_API_KEY_VARIABLE_NAME = "BOI_LLM_API_KEY"
MAX_ENDPOINTS = 5
FLOW_VALIDATION_STAGES = (
    "discovered",
    "structural_validated",
    "build_validated",
    "runtime_validated",
    "task_validated",
    "action_ready",
    "action_linked",
    "blocked",
)
FLOW_VALIDATION_RANK = {
    stage: index
    for index, stage in enumerate(stage for stage in FLOW_VALIDATION_STAGES if stage != "blocked")
}
SECRET_PATTERNS = (
    re.compile(r"boi_pat_[0-9a-f]{16}_[A-Za-z0-9_-]{16,}"),
    re.compile(r"boi_run_[0-9a-f]{16}_[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
)
HTTP_SCHEME_RE = re.compile(r"^(https?):/{0,2}", re.IGNORECASE)
OTHER_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def advance_flow_validation_status(current: str, candidate: str) -> str:
    """Keep successful Flow validation state monotonic; blocked is terminal."""

    current = str(current or "")
    candidate = str(candidate or "")
    if current == "blocked":
        return current
    if current in FLOW_VALIDATION_RANK and candidate in FLOW_VALIDATION_RANK:
        return current if FLOW_VALIDATION_RANK[current] >= FLOW_VALIDATION_RANK[candidate] else candidate
    return candidate or current or "discovered"


def parse_version(value: str) -> tuple[int, int, int]:
    parts = str(value or "").split("-", 1)[0].split(".")
    try:
        values = [int(item) for item in parts[:3]]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"invalid Langflow version: {value}") from exc
    if len(values) < 2:
        raise HTTPException(status_code=422, detail=f"invalid Langflow version: {value}")
    while len(values) < 3:
        values.append(0)
    return tuple(values)  # type: ignore[return-value]


def require_langflow_111(value: str) -> None:
    parsed = parse_version(value)
    if not (LANGFLOW_MIN_VERSION <= parsed < LANGFLOW_MAX_VERSION):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "langflow_version_mismatch",
                "message": "Agent Playground requires Langflow >=1.11.0,<1.12.0",
                "actual_version": value,
            },
        )


def normalize_langflow_endpoint(value: str) -> str:
    candidate = str(value or "").strip().strip("<>\"'").strip()
    if match := HTTP_SCHEME_RE.match(candidate):
        candidate = f"{match.group(1).lower()}://{candidate[match.end():]}"
    elif match := OTHER_SCHEME_RE.match(candidate):
        candidate = f"https://{candidate[match.end():]}"
    else:
        candidate = f"https://{candidate}"
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=422, detail="Langflow endpoint must be an http(s) URL")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=422, detail="Langflow endpoint must not contain credentials")
    normalized = urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), "", "", ""))
    allowed_hosts = {
        item.strip().lower()
        for item in os.getenv("BOI_AGENT_PLAYGROUND_ALLOWED_LANGFLOW_HOSTS", "").split(",")
        if item.strip()
    }
    if os.getenv("BOI_AUTH_MODE", "dev").strip().lower() != "dev" and not allowed_hosts:
        raise HTTPException(
            status_code=503,
            detail="BOI_AGENT_PLAYGROUND_ALLOWED_LANGFLOW_HOSTS is required outside development",
        )
    if allowed_hosts and str(parsed.hostname).lower() not in allowed_hosts:
        raise HTTPException(status_code=422, detail="Langflow endpoint host is not allowlisted")
    return normalized


def agent_hub_api_origin() -> str:
    configured = str(
        os.getenv("AGENT_HUB_API_URL")
        or os.getenv("AGENT_HUB_EXTERNAL_URL")
        or ""
    ).strip()
    if not configured:
        raise HTTPException(status_code=503, detail="Agent Hub API URL is not configured")
    parsed = urlsplit(configured)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=503, detail="Agent Hub API URL must be an http(s) URL")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=503, detail="Agent Hub API URL must not contain credentials")
    if os.getenv("AGENT_HUB_API_URL"):
        return configured.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), "", "", "")).rstrip("/")


def require_role(principal: AuthIdentity, *roles: str) -> None:
    if principal.is_admin or any(role in principal.roles for role in roles):
        return
    raise HTTPException(status_code=403, detail=f"required role: {' or '.join(roles)}")


class PlaygroundConnectRequest(BaseModel):
    endpoint: str = Field(min_length=1, max_length=1000)
    api_key: str = Field(min_length=8, max_length=1000)


class PlaygroundEndpointCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    base_url: str = Field(min_length=1, max_length=1000)
    api_key: str = Field(min_length=8, max_length=1000)
    make_default: bool = False


class PlaygroundEndpointUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    base_url: str | None = Field(default=None, min_length=1, max_length=1000)
    api_key: str | None = Field(default=None, min_length=8, max_length=1000)
    active: bool | None = None
    make_default: bool = False


class PlaygroundEndpointTestRequest(BaseModel):
    base_url: str = Field(min_length=1, max_length=1000)
    api_key: str = Field(min_length=8, max_length=1000)


class PlaygroundBootstrapRequest(BaseModel):
    endpoint_id: str = Field(default="", max_length=100)
    smoke_question: str = Field(default="BoI Wiki에서 Agent Playground 기준 Flow 설명을 찾아줘.", max_length=2000)


class PlaygroundFlowTestRequest(BaseModel):
    endpoint_id: str = Field(default="", max_length=100)
    project_id: str = Field(default="", max_length=500)
    question: str = Field(min_length=1, max_length=8000)
    business_context: str = Field(default="", max_length=8000)
    task_ref: str = Field(default="", max_length=1000)
    page_ref: str = Field(default="", max_length=1000)
    context_id: str = Field(default="", max_length=500)
    sop_ref: str = Field(default="", max_length=1000)
    sop_stage: str = Field(default="", max_length=500)
    event_ref: str = Field(default="", max_length=1000)
    action_ref: str = Field(default="", max_length=1000)
    prior_results: list[Any] = Field(default_factory=list, max_length=100)
    required_evidence: list[str] = Field(default_factory=list, max_length=100)
    missing_evidence: list[str] = Field(default_factory=list, max_length=100)
    save_mode: Literal["preview", "private_draft"] = "preview"
    title: str = Field(default="Agent Playground 테스트 초안", max_length=200)


class PlaygroundDeploymentRequest(BaseModel):
    endpoint_id: str = Field(min_length=1, max_length=100)
    project_id: str = Field(min_length=1, max_length=500)
    flow_id: str = Field(min_length=1, max_length=500)
    flow_url: str = Field(default="", max_length=2000)
    agent_hub_flow_url: str = Field(default="", max_length=2000)
    endpoint_name: str = Field(default=CANONICAL_FLOW_ENDPOINT, max_length=200)
    asset_version: str = Field(default=CANONICAL_FLOW_VERSION, max_length=100)
    artifact_checksum: str = Field(default="", max_length=128)
    agent_hub_asset_id: str = Field(default="", max_length=500)
    agent_hub_endpoint_id: str = Field(default="", max_length=500)
    agent_hub_deployment_id: str = Field(default="", max_length=500)


class PlaygroundHubAdoptionBeginRequest(BaseModel):
    endpoint_id: str = Field(min_length=1, max_length=100)
    project_id: str = Field(min_length=1, max_length=500)
    asset_ids: list[str] = Field(min_length=1, max_length=50)
    validation_profile: Literal[
        "generic_action",
        "boi_knowledge",
        "boi_knowledge_draft",
    ] = "boi_knowledge_draft"


class PlaygroundHubAdoptionConfirmRequest(BaseModel):
    flow_id: str = Field(min_length=1, max_length=500)


class PlaygroundFlowValidationRequest(BaseModel):
    endpoint_id: str = Field(min_length=1, max_length=100)
    project_id: str = Field(min_length=1, max_length=500)
    artifact_version: str = Field(default=CANONICAL_FLOW_VERSION, max_length=100)
    artifact_checksum: str = Field(default="", max_length=128)
    question: str = Field(
        default="현재 업무와 관련된 BoI Wiki 근거와 Ontology 관계를 알려줘.",
        min_length=1,
        max_length=4000,
    )
    task_ref: str = Field(default="", max_length=1000)


class PlaygroundRotateCredentialRequest(BaseModel):
    endpoint_id: str = Field(default="", max_length=100)
    reason: str = Field(default="manual rotation", max_length=500)


class SecretCipher:
    def __init__(self, secret: str):
        if not str(secret or "").strip():
            raise RuntimeError("BOI_AGENT_PLAYGROUND_ENCRYPTION_KEY is required")
        self._key = hashlib.sha256(secret.encode("utf-8")).digest()

    def encrypt(self, value: str, *, owner: str) -> str:
        nonce = os.urandom(12)
        encrypted = AESGCM(self._key).encrypt(nonce, value.encode("utf-8"), owner.encode("utf-8"))
        return base64.urlsafe_b64encode(nonce + encrypted).decode("ascii")

    def decrypt(self, value: str, *, owner: str) -> str:
        packed = base64.urlsafe_b64decode(value.encode("ascii"))
        return AESGCM(self._key).decrypt(packed[:12], packed[12:], owner.encode("utf-8")).decode("utf-8")


class LangflowPublicApiV1:
    """The only Langflow compatibility boundary used by Agent Playground."""

    HEALTH_PATH = "/health"
    VERSION_PATH = "/api/v1/version"
    WHOAMI_PATH = "/api/v1/users/whoami"
    PROJECTS_PATH = "/api/v1/projects/"
    FLOWS_PATH = "/api/v1/flows/"
    VARIABLES_PATH = "/api/v1/variables/"
    CATALOG_PATH = "/api/v1/all"
    RUN_PATH = "/api/v1/run/{flow_id}"

    def __init__(self, transport: Any):
        self._transport = transport

    def inspect_connection(self, endpoint: str, api_key: str) -> dict[str, Any]:
        self._transport("GET", endpoint, self.HEALTH_PATH, api_key)
        version_payload = self._transport("GET", endpoint, self.VERSION_PATH, api_key).json()
        version = str(version_payload.get("version") or version_payload.get("main_version") or "")
        require_langflow_111(version)
        whoami = self._transport("GET", endpoint, self.WHOAMI_PATH, api_key).json()
        projects = self.projects(endpoint, api_key)
        return {
            "base_url": endpoint,
            "endpoint": endpoint,
            "version": version,
            "langflow_user_id": str(whoami.get("id") or ""),
            "langflow_username": str(whoami.get("username") or ""),
            "is_active": bool(whoami.get("is_active", True)),
            "is_superuser": bool(whoami.get("is_superuser", False)),
            "project_count": len(projects),
        }

    def projects(self, endpoint: str, api_key: str) -> list[dict[str, Any]]:
        payload = self._transport("GET", endpoint, self.PROJECTS_PATH, api_key).json()
        return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []

    def ensure_project(
        self,
        endpoint: str,
        api_key: str,
        *,
        name: str,
        description: str,
    ) -> dict[str, Any]:
        existing = next(
            (item for item in self.projects(endpoint, api_key) if str(item.get("name") or "") == name),
            None,
        )
        if existing:
            return existing
        payload = self._transport(
            "POST",
            endpoint,
            self.PROJECTS_PATH,
            api_key,
            expected={200, 201},
            json={"name": name, "description": description},
        ).json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="Langflow project create returned an invalid response")
        return payload

    def variables(self, endpoint: str, api_key: str) -> list[dict[str, Any]]:
        payload = self._transport("GET", endpoint, self.VARIABLES_PATH, api_key).json()
        return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []

    def verify_component_bundle(self, endpoint: str, api_key: str) -> dict[str, Any]:
        payload = self._transport("GET", endpoint, self.CATALOG_PATH, api_key).json()
        serialized = json.dumps(payload, ensure_ascii=False, default=str)
        components = {
            name: name in serialized
            for name in REQUIRED_BUNDLE_COMPONENTS
        }
        missing = [name for name, present in components.items() if not present]
        if missing:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "boi_component_bundle_missing",
                    "message": "BoI read-only component bundle is not available in Langflow",
                    "missing": missing,
                },
            )
        return {
            "verified": True,
            "components": components,
        }

    def put_credential(
        self,
        endpoint: str,
        api_key: str,
        *,
        name: str,
        value: str,
    ) -> dict[str, Any]:
        existing = next(
            (item for item in self.variables(endpoint, api_key) if str(item.get("name") or "") == name),
            None,
        )
        body: dict[str, Any] = {
            "name": name,
            "value": value,
            "type": "Credential",
            "default_fields": [],
        }
        if existing:
            body["id"] = existing["id"]
            payload = self._transport(
                "PATCH",
                endpoint,
                f"/api/v1/variables/{existing['id']}",
                api_key,
                json=body,
            ).json()
        else:
            payload = self._transport(
                "POST",
                endpoint,
                self.VARIABLES_PATH,
                api_key,
                expected={200, 201},
                json=body,
            ).json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="Langflow credential API returned an invalid response")
        return payload

    def flows(self, endpoint: str, api_key: str) -> list[dict[str, Any]]:
        payload = self._transport("GET", endpoint, self.FLOWS_PATH, api_key).json()
        return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []

    def flow(self, endpoint: str, api_key: str, flow_id: str) -> dict[str, Any]:
        payload = self._transport(
            "GET",
            endpoint,
            f"/api/v1/flows/{flow_id}",
            api_key,
        ).json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="Langflow Flow API returned an invalid response")
        return payload

    def create_flow(
        self,
        endpoint: str,
        api_key: str,
        *,
        name: str,
        description: str,
        data: dict[str, Any],
        project_id: str,
    ) -> dict[str, Any]:
        payload = self._transport(
            "POST",
            endpoint,
            self.FLOWS_PATH,
            api_key,
            expected={200, 201},
            json={
                "name": name,
                "description": description,
                "data": data,
                "folder_id": project_id,
                "project_id": project_id,
            },
            timeout=120,
        ).json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="Langflow create did not return a Flow")
        return payload

    def run(
        self,
        endpoint: str,
        api_key: str,
        flow_id: str,
        *,
        input_value: str,
        run_token: str = "",
    ) -> dict[str, Any]:
        payload = self._transport(
            "POST",
            endpoint,
            self.RUN_PATH.format(flow_id=flow_id),
            api_key,
            headers=(
                {"X-LANGFLOW-GLOBAL-VAR-BOI_RUN_TOKEN": run_token}
                if run_token
                else {}
            ),
            json={"input_value": input_value, "input_type": "chat", "output_type": "chat"},
            timeout=180,
        ).json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="Langflow run returned an invalid response")
        return payload


class AgentPlaygroundService:
    def __init__(
        self,
        runtime_root: Path,
        repo_root: Path,
        credential_service: PlaygroundCredentialService,
    ):
        self.root = runtime_root / "agent-playground"
        self.repo_root = repo_root
        self.pat_service = credential_service
        encryption_secret = os.getenv("BOI_AGENT_PLAYGROUND_ENCRYPTION_KEY") or (
            "dev-only-agent-playground-encryption-key"
            if os.getenv("BOI_AUTH_MODE", "dev").strip().lower() == "dev"
            else ""
        )
        self.cipher = SecretCipher(encryption_secret)
        self.encryption_configured = bool(os.getenv("BOI_AGENT_PLAYGROUND_ENCRYPTION_KEY"))
        self._lock = threading.RLock()
        # Resolve through a lambda so tests and validation transports can replace
        # `_request` without changing the public compatibility adapter.
        self.langflow = LangflowPublicApiV1(lambda *args, **kwargs: self._request(*args, **kwargs))

    def _path(self, employee_id: str) -> Path:
        safe_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", employee_id).strip("-")
        return self.root / "users" / f"{safe_id}.json"

    def _read(self, employee_id: str) -> dict[str, Any]:
        path = self._path(employee_id)
        if not path.exists():
            return {"employee_id": employee_id, "created_at": now_iso(), "updated_at": now_iso()}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=500, detail="Agent Playground state is unreadable") from exc
        if str(payload.get("employee_id") or "") != employee_id:
            raise HTTPException(status_code=500, detail="Agent Playground ownership invariant failed")
        return payload

    def _write(self, employee_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if str(payload.get("employee_id") or "") != employee_id:
            raise HTTPException(status_code=500, detail="Agent Playground owner must come from AuthIdentity")
        with self._lock:
            path = self._path(employee_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            payload["updated_at"] = now_iso()
            temporary = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
            temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        return payload

    @staticmethod
    def _public_connection(connection: dict[str, Any]) -> dict[str, Any]:
        public = {
            key: value
            for key, value in connection.items()
            if key not in {"api_key_encrypted"}
        }
        base_url = str(public.get("base_url") or public.get("endpoint") or "")
        public["base_url"] = base_url
        public["endpoint"] = base_url
        public["has_api_key"] = bool(connection.get("api_key_encrypted"))
        return public

    def _endpoint_records(self, record: dict[str, Any]) -> list[dict[str, Any]]:
        endpoints = [item for item in record.get("endpoints") or [] if isinstance(item, dict)]
        legacy = record.get("connection") if isinstance(record.get("connection"), dict) else {}
        if not endpoints and legacy:
            base_url = str(legacy.get("base_url") or legacy.get("endpoint") or "")
            endpoint_id = str(legacy.get("endpoint_id") or f"ep-{hashlib.sha256(base_url.encode()).hexdigest()[:16]}")
            endpoints = [
                {
                    **legacy,
                    "endpoint_id": endpoint_id,
                    "name": str(legacy.get("name") or "Personal Langflow"),
                    "base_url": base_url,
                    "endpoint": base_url,
                    "active": bool(legacy.get("active", True)),
                }
            ]
            record["endpoints"] = endpoints
            record["default_endpoint_id"] = endpoint_id
        if endpoints and not record.get("default_endpoint_id"):
            record["default_endpoint_id"] = str(endpoints[0].get("endpoint_id") or "")
        return endpoints

    def _endpoint_setups(self, record: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Return endpoint-scoped setup records and migrate legacy singular state in memory."""

        raw = record.get("endpoint_setups")
        setups: dict[str, dict[str, Any]] = {
            str(key): value
            for key, value in (raw.items() if isinstance(raw, dict) else [])
            if str(key) and isinstance(value, dict)
        }
        endpoints = self._endpoint_records(record)
        legacy_project = record.get("project") if isinstance(record.get("project"), dict) else {}
        legacy_flow = record.get("canonical_flow") if isinstance(record.get("canonical_flow"), dict) else {}
        legacy_credential = (
            record.get("wiki_credential") if isinstance(record.get("wiki_credential"), dict) else {}
        )
        credentials = (
            record.get("wiki_credentials") if isinstance(record.get("wiki_credentials"), dict) else {}
        )
        canonical_flows = [
            item for item in record.get("canonical_flows") or [] if isinstance(item, dict)
        ]
        last_test = record.get("last_test") if isinstance(record.get("last_test"), dict) else {}
        registry = [item for item in record.get("flow_registry") or [] if isinstance(item, dict)]
        only_endpoint_id = str(endpoints[0].get("endpoint_id") or "") if len(endpoints) == 1 else ""

        for endpoint in endpoints:
            endpoint_id = str(endpoint.get("endpoint_id") or "")
            if not endpoint_id:
                continue
            setup = dict(setups.get(endpoint_id) or {})
            project = setup.get("project") if isinstance(setup.get("project"), dict) else {}
            if not project and (
                str(legacy_project.get("endpoint_id") or "") == endpoint_id
                or (only_endpoint_id == endpoint_id and legacy_project)
            ):
                project = dict(legacy_project)
            flow = setup.get("canonical_flow") if isinstance(setup.get("canonical_flow"), dict) else {}
            if not flow:
                flow = next(
                    (
                        dict(item)
                        for item in canonical_flows
                        if str(item.get("endpoint_id") or "") == endpoint_id
                    ),
                    {},
                )
            if not flow and (
                str(legacy_flow.get("endpoint_id") or "") == endpoint_id
                or (only_endpoint_id == endpoint_id and legacy_flow)
            ):
                flow = dict(legacy_flow)
            credential = (
                setup.get("wiki_credential")
                if isinstance(setup.get("wiki_credential"), dict)
                else {}
            )
            if not credential:
                candidate = credentials.get(endpoint_id)
                if isinstance(candidate, dict):
                    credential = dict(candidate)
            if not credential and only_endpoint_id == endpoint_id and legacy_credential:
                credential = dict(legacy_credential)
            flow_id = str(flow.get("id") or "")
            registry_item = next(
                (
                    item
                    for item in registry
                    if str(item.get("endpoint_id") or "") == endpoint_id
                    and str(item.get("flow_id") or "") == flow_id
                ),
                {},
            )
            if flow and not flow.get("checksum"):
                flow["checksum"] = str(registry_item.get("artifact_checksum") or "")
            smoke = setup.get("smoke") if isinstance(setup.get("smoke"), dict) else {}
            if (
                not smoke
                and str(last_test.get("status") or "") == "passed"
                and str(last_test.get("mode") or "") == "preview"
                and str(last_test.get("endpoint_id") or "") == endpoint_id
                and str(last_test.get("flow_id") or "") == flow_id
            ):
                smoke = {
                    "status": "passed",
                    "checked_at": str(last_test.get("tested_at") or ""),
                    "flow_id": flow_id,
                    "session_id": str(last_test.get("session_id") or ""),
                }
            if project:
                setup["project"] = project
            if credential:
                setup["wiki_credential"] = credential
            if flow:
                setup["canonical_flow"] = flow
            if project or credential or flow:
                setup.setdefault(
                    "bundle",
                    {
                        "version": COMPONENT_BUNDLE_VERSION,
                        "mode": COMPONENT_BUNDLE_MODE,
                        "verified": False,
                        "components": {},
                    },
                )
            if smoke:
                setup["smoke"] = smoke
            setup["endpoint_id"] = endpoint_id
            setup.setdefault("onboarding_status", "not_started")
            setup.setdefault("current_step", "connection")
            setup.setdefault("last_error", "")
            setups[endpoint_id] = setup
        record["endpoint_setups"] = setups
        return setups

    def _endpoint_setup(self, record: dict[str, Any], endpoint_id: str) -> dict[str, Any]:
        setups = self._endpoint_setups(record)
        setup = setups.setdefault(
            endpoint_id,
            {
                "endpoint_id": endpoint_id,
                "onboarding_status": "not_started",
                "current_step": "connection",
                "last_error": "",
            },
        )
        return setup

    def _setup_readiness(
        self,
        endpoint: dict[str, Any] | None,
        setup: dict[str, Any] | None,
    ) -> dict[str, Any]:
        endpoint = endpoint or {}
        setup = setup or {}
        project = setup.get("project") if isinstance(setup.get("project"), dict) else {}
        credential = (
            setup.get("wiki_credential")
            if isinstance(setup.get("wiki_credential"), dict)
            else {}
        )
        flow = setup.get("canonical_flow") if isinstance(setup.get("canonical_flow"), dict) else {}
        smoke = setup.get("smoke") if isinstance(setup.get("smoke"), dict) else {}
        bundle = setup.get("bundle") if isinstance(setup.get("bundle"), dict) else {}
        canonical_checksum = self._canonical_checksum()
        checks = {
            "connection": (
                bool(endpoint)
                and bool(endpoint.get("active", True))
                and str(endpoint.get("status") or "") == "connected"
                and bool(endpoint.get("has_api_key"))
                and str(endpoint.get("version") or "").startswith("1.11.")
            ),
            "project": bool(project.get("id")) and bool(project.get("name")),
            "wiki_credential": (
                bool(credential.get("token_id"))
                and str(credential.get("variable_name") or "") == BOI_PAT_VARIABLE_NAME
            ),
            "bundle": (
                str(bundle.get("version") or "") == COMPONENT_BUNDLE_VERSION
                and str(bundle.get("mode") or "") == COMPONENT_BUNDLE_MODE
                and bool(bundle.get("verified"))
                and all(
                    bool((bundle.get("components") or {}).get(name))
                    for name in REQUIRED_BUNDLE_COMPONENTS
                )
            ),
            "canonical_flow": (
                bool(flow.get("id"))
                and str(flow.get("version") or "") == CANONICAL_FLOW_VERSION
                and str(flow.get("checksum") or "") == canonical_checksum
            ),
            "preview_smoke": (
                str(smoke.get("status") or "") == "passed"
                and str(smoke.get("flow_id") or "") == str(flow.get("id") or "")
            ),
        }
        return {"ready": all(checks.values()), "checks": checks}

    @staticmethod
    def _public_setup(setup: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
        project = setup.get("project") if isinstance(setup.get("project"), dict) else {}
        flow = setup.get("canonical_flow") if isinstance(setup.get("canonical_flow"), dict) else {}
        smoke = setup.get("smoke") if isinstance(setup.get("smoke"), dict) else {}
        bundle = setup.get("bundle") if isinstance(setup.get("bundle"), dict) else {}
        credential = (
            setup.get("wiki_credential")
            if isinstance(setup.get("wiki_credential"), dict)
            else {}
        )
        return {
            "endpoint_id": str(setup.get("endpoint_id") or ""),
            "project": {
                "id": str(project.get("id") or ""),
                "name": str(project.get("name") or ""),
            },
            "wiki": {
                "status": "connected" if credential.get("token_id") else "not_connected",
                "credential_variable": (
                    BOI_PAT_VARIABLE_NAME if credential.get("token_id") else ""
                ),
                "pat_expires_at": credential.get("expires_at"),
            },
            "canonical_flow": {
                "id": str(flow.get("id") or ""),
                "name": str(flow.get("name") or ""),
                "endpoint_name": str(flow.get("endpoint_name") or ""),
                "version": str(flow.get("version") or ""),
                "checksum": str(flow.get("checksum") or ""),
                "flow_url": str(flow.get("flow_url") or ""),
                "project_id": str(flow.get("project_id") or ""),
            },
            "bundle": {
                "version": str(bundle.get("version") or ""),
                "mode": str(bundle.get("mode") or ""),
                "verified": bool(bundle.get("verified")),
                "components": {
                    name: bool((bundle.get("components") or {}).get(name))
                    for name in REQUIRED_BUNDLE_COMPONENTS
                },
            },
            "smoke": {
                "status": str(smoke.get("status") or "not_run"),
                "checked_at": str(smoke.get("checked_at") or ""),
                "flow_id": str(smoke.get("flow_id") or ""),
            },
            "onboarding_status": str(setup.get("onboarding_status") or "not_started"),
            "current_step": str(setup.get("current_step") or "connection"),
            "last_error": str(setup.get("last_error") or ""),
            "readiness": readiness,
        }

    def _onboarding(
        self,
        principal: AuthIdentity,
        endpoint: dict[str, Any] | None,
        setup: dict[str, Any] | None,
    ) -> dict[str, Any]:
        readiness = self._setup_readiness(endpoint, setup)
        checks = readiness["checks"]
        setup = setup or {}
        has_endpoint = bool(endpoint)
        knowledge_ready = checks["project"] and checks["wiki_credential"] and checks["bundle"]
        flow_ready = checks["canonical_flow"] and checks["preview_smoke"]
        steps = [
            {
                "id": "identity",
                "state": "complete",
                "message": f"{principal.display_name} · {principal.employee_id}",
                "recoverable": False,
            },
            {
                "id": "connection",
                "state": "complete" if checks["connection"] else ("current" if has_endpoint else "pending"),
                "message": (
                    "Langflow 1.11 연결과 API Key 소유자를 확인했습니다."
                    if checks["connection"]
                    else str((endpoint or {}).get("last_error") or "Langflow 연결 키가 필요합니다.")
                ),
                "recoverable": True,
            },
            {
                "id": "knowledge",
                "state": "complete" if knowledge_ready else ("current" if checks["connection"] else "pending"),
                "message": (
                    "개인 프로젝트와 BoI 지식 연결이 준비됐습니다."
                    if knowledge_ready
                    else "개인 프로젝트와 BoI 지식 연결을 자동 준비합니다."
                ),
                "recoverable": True,
            },
            {
                "id": "flow",
                "state": "complete" if flow_ready else ("current" if knowledge_ready else "pending"),
                "message": (
                    "기준 Flow preview smoke를 통과했습니다."
                    if flow_ready
                    else "기준 Flow를 설치하고 실제 preview를 확인합니다."
                ),
                "recoverable": True,
            },
        ]
        if readiness["ready"]:
            status = "ready"
            current_step = "complete"
            next_action = "open_workbench"
        elif not has_endpoint:
            status = "not_started"
            current_step = "connection"
            next_action = "open_langflow_settings"
        elif not checks["connection"]:
            status = "not_started"
            current_step = "connection"
            next_action = "test_connection"
        elif str(setup.get("onboarding_status") or "") == "error":
            status = "error"
            failed_step = str(setup.get("current_step") or "knowledge")
            # Every bootstrap failure must land on the stage that owns the
            # idempotent retry action. The stepper still records the exact
            # failed phase so a Flow-smoke failure is not mislabeled.
            current_step = "knowledge"
            next_action = "retry_bootstrap"
            for step in steps:
                if step["id"] == failed_step:
                    step["state"] = "error"
                    step["message"] = str(setup.get("last_error") or step["message"])
        elif str(setup.get("onboarding_status") or "") == "provisioning":
            status = "provisioning"
            current_step = str(setup.get("current_step") or "knowledge")
            next_action = "wait"
        else:
            status = "connection_ready"
            # The bootstrap button lives in the automatic-setup stage and is
            # also the recovery action when only the canonical Flow/checksum
            # or preview smoke became stale after an artifact update.
            current_step = "knowledge"
            next_action = "bootstrap"
        return {
            "required": not readiness["ready"],
            "status": status,
            "current_step": current_step,
            "steps": steps,
            "next_action": next_action,
            "last_error": str(setup.get("last_error") or ""),
            "readiness": readiness,
        }

    def _endpoint(
        self,
        record: dict[str, Any],
        endpoint_id: str = "",
        *,
        require_active: bool = True,
    ) -> dict[str, Any]:
        endpoints = self._endpoint_records(record)
        wanted = str(endpoint_id or record.get("default_endpoint_id") or "")
        selected = next(
            (item for item in endpoints if str(item.get("endpoint_id") or "") == wanted),
            None,
        )
        if selected is None:
            raise HTTPException(status_code=404, detail="Langflow endpoint connection not found")
        if require_active and not bool(selected.get("active", True)):
            raise HTTPException(status_code=409, detail="Langflow endpoint connection is inactive")
        return selected

    def _api_key(self, record: dict[str, Any], endpoint_id: str = "") -> str:
        endpoint = self._endpoint(record, endpoint_id)
        encrypted = str(endpoint.get("api_key_encrypted") or "")
        if not encrypted:
            raise HTTPException(status_code=409, detail="Langflow is not connected")
        return self.cipher.decrypt(encrypted, owner=str(record["employee_id"]))

    @staticmethod
    def _headers(api_key: str) -> dict[str, str]:
        return {"x-api-key": api_key}

    def _request(
        self,
        method: str,
        endpoint: str,
        path: str,
        api_key: str,
        *,
        expected: set[int] | None = None,
        timeout: float = 20,
        **kwargs: Any,
    ) -> httpx.Response:
        try:
            response = httpx.request(
                method,
                f"{endpoint.rstrip('/')}{path}",
                headers={**self._headers(api_key), **kwargs.pop("headers", {})},
                timeout=timeout,
                follow_redirects=False,
                **kwargs,
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Langflow connection failed: {type(exc).__name__}") from exc
        allowed = expected or {200}
        if response.status_code not in allowed:
            detail: Any
            try:
                detail = response.json()
            except ValueError:
                detail = response.text[:500]
            raise HTTPException(
                status_code=502,
                detail={"code": "langflow_api_error", "path": path, "status": response.status_code, "response": detail},
            )
        return response

    def _agent_hub_request(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        expected: set[int] | None = None,
    ) -> Any:
        base_url = agent_hub_api_origin()
        try:
            response = httpx.get(
                f"{base_url}{path}",
                params=params or {},
                timeout=20,
                follow_redirects=False,
            )
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Agent Hub catalog connection failed: {type(exc).__name__}",
            ) from exc
        if response.status_code not in (expected or {200}):
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "agent_hub_catalog_error",
                    "path": path,
                    "status": response.status_code,
                },
            )
        try:
            return response.json()
        except ValueError as exc:
            raise HTTPException(
                status_code=502,
                detail="Agent Hub catalog returned an invalid response",
            ) from exc

    @staticmethod
    def _public_agent_hub_asset(item: dict[str, Any]) -> dict[str, Any]:
        author = item.get("author") if isinstance(item.get("author"), dict) else {}
        safe = {
            "asset_id": str(item.get("id") or item.get("asset_id") or ""),
            "title": str(item.get("title") or ""),
            "type": str(item.get("type") or ""),
            "description": str(item.get("description") or ""),
            "category": str(item.get("category") or ""),
            "version": str(item.get("version") or ""),
            "min_langflow_version": str(item.get("min_langflow_ver") or ""),
            "max_langflow_version": str(item.get("max_langflow_ver") or ""),
            "tested_versions": [
                str(value)
                for value in (item.get("tested_versions") or [])
                if str(value)
            ],
            "tags": [str(value) for value in (item.get("tags") or []) if str(value)],
            "is_standard": bool(item.get("is_standard")),
            "status": str(item.get("status") or ""),
            "author": {
                "employee_id": str(
                    author.get("employee_id")
                    or author.get("id")
                    or item.get("author_id")
                    or ""
                ),
                "name": str(author.get("name") or ""),
                "team": str(author.get("team") or ""),
                "org": str(author.get("org") or ""),
            },
            "updated_at": str(item.get("updated_at") or ""),
        }
        safe["metadata_checksum"] = hashlib.sha256(
            json.dumps(
                safe,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        external = str(os.getenv("AGENT_HUB_EXTERNAL_URL") or "").rstrip("/")
        route = "flow" if safe["type"] == "json" else "component"
        safe["asset_url"] = f"{external}#/{route}/{safe['asset_id']}" if external else ""
        return safe

    def agent_hub_assets(
        self,
        principal: AuthIdentity,
        *,
        search: str = "",
        asset_type: str = "",
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        require_role(principal, "boi.viewer")
        if asset_type and asset_type not in {"json", "py"}:
            raise HTTPException(status_code=422, detail="Agent Hub asset type must be json or py")
        payload = self._agent_hub_request(
            "/api/v1/components",
            params={
                "search": search.strip() or None,
                "type": asset_type or None,
                "sort": "popular",
                "limit": max(1, min(int(limit), 100)),
                "offset": max(0, int(offset)),
            },
        )
        rows = payload.get("items") if isinstance(payload, dict) else []
        items = [
            self._public_agent_hub_asset(item)
            for item in (rows or [])
            if isinstance(item, dict)
            and str(item.get("status") or "") == "approved"
        ]
        return {
            "ok": True,
            "items": items,
            "total": int(payload.get("total") or len(items)) if isinstance(payload, dict) else len(items),
            "limit": max(1, min(int(limit), 100)),
            "offset": max(0, int(offset)),
        }

    def agent_hub_asset(self, principal: AuthIdentity, asset_id: str) -> dict[str, Any]:
        require_role(principal, "boi.viewer")
        asset_id = str(asset_id or "").strip()
        if not re.fullmatch(r"[0-9A-Fa-f-]{32,36}", asset_id):
            raise HTTPException(status_code=422, detail="invalid Agent Hub asset ID")
        payload = self._agent_hub_request(f"/api/v1/components/{asset_id}")
        if not isinstance(payload, dict) or str(payload.get("id") or "") != asset_id:
            raise HTTPException(status_code=502, detail="Agent Hub asset identity mismatch")
        if str(payload.get("status") or "") != "approved":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "agent_hub_asset_not_approved",
                    "message": "Only approved Agent Hub assets can be linked to a BoI Action.",
                    "asset_id": asset_id,
                },
            )
        # The immutable Agent Hub detail route does not filter soft-deleted
        # records. Confirm the exact ID still appears in its approved catalog
        # before treating the metadata as Action provenance.
        catalog = self._agent_hub_request(
            "/api/v1/components",
            params={
                "search": str(payload.get("title") or ""),
                "type": str(payload.get("type") or "") or None,
                "limit": 1000,
                "offset": 0,
            },
        )
        visible_ids = {
            str(item.get("id") or "")
            for item in (catalog.get("items") or [])
            if isinstance(item, dict)
        } if isinstance(catalog, dict) else set()
        if asset_id not in visible_ids:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "agent_hub_asset_not_catalog_visible",
                    "message": "The Agent Hub asset is not available in the approved catalog.",
                    "asset_id": asset_id,
                },
            )
        return {"ok": True, "asset": self._public_agent_hub_asset(payload)}

    def inspect_connection(self, endpoint: str, api_key: str) -> dict[str, Any]:
        return self.langflow.inspect_connection(endpoint, api_key)

    def _validate_endpoint_owner(
        self,
        principal: AuthIdentity,
        endpoint: str,
        api_key: str,
        *,
        current_endpoint_id: str = "",
        allow_existing_same_owner: bool = False,
    ) -> dict[str, Any]:
        inspected = self.inspect_connection(endpoint, api_key)
        expected_usernames = {principal.employee_id, f"boi-{principal.employee_id}"}
        if inspected["langflow_username"] not in expected_usernames:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "langflow_user_mismatch",
                    "message": "Langflow API Key owner must match the current employee",
                    "expected": sorted(expected_usernames),
                    "actual": inspected["langflow_username"],
                },
            )
        if not inspected["langflow_user_id"] or not inspected["is_active"]:
            raise HTTPException(status_code=403, detail="Langflow API Key owner is inactive or missing")
        users_root = self.root / "users"
        for path in users_root.glob("*.json") if users_root.exists() else []:
            try:
                other = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            other_endpoints = [item for item in other.get("endpoints") or [] if isinstance(item, dict)]
            legacy = other.get("connection") if isinstance(other.get("connection"), dict) else {}
            if legacy and not other_endpoints:
                other_endpoints = [legacy]
            for other_endpoint in other_endpoints:
                if (
                    str(other.get("employee_id") or "") != principal.employee_id
                    and str(other_endpoint.get("langflow_user_id") or "") == inspected["langflow_user_id"]
                ):
                    raise HTTPException(status_code=409, detail="this Langflow user is already assigned to another employee")
                if (
                    str(other.get("employee_id") or "") == principal.employee_id
                    and not allow_existing_same_owner
                    and str(other_endpoint.get("endpoint_id") or "") != current_endpoint_id
                    and str(other_endpoint.get("langflow_user_id") or "") == inspected["langflow_user_id"]
                    and str(other_endpoint.get("base_url") or other_endpoint.get("endpoint") or "") == endpoint
                ):
                    raise HTTPException(status_code=409, detail="this Langflow endpoint is already registered")
        return inspected

    def endpoints(self, principal: AuthIdentity, *, live: bool = False) -> dict[str, Any]:
        require_role(principal, "boi.viewer")
        record = self._read(principal.employee_id)
        items: list[dict[str, Any]] = []
        for endpoint in self._endpoint_records(record):
            public = self._public_connection(endpoint)
            if live and bool(endpoint.get("active", True)):
                try:
                    inspected = self.inspect_connection(
                        str(endpoint.get("base_url") or endpoint.get("endpoint") or ""),
                        self._api_key(record, str(endpoint.get("endpoint_id") or "")),
                    )
                    public.update(inspected)
                    public["status"] = "connected"
                    public["last_error"] = ""
                except HTTPException as exc:
                    public["status"] = "error"
                    public["last_error"] = str(exc.detail)
            items.append(public)
        return {
            "ok": True,
            "endpoints": items,
            "default_endpoint_id": str(record.get("default_endpoint_id") or ""),
            "limit": MAX_ENDPOINTS,
        }

    def test_unsaved_endpoint(
        self,
        principal: AuthIdentity,
        request: PlaygroundEndpointTestRequest,
    ) -> dict[str, Any]:
        require_role(principal, "boi.viewer")
        endpoint = normalize_langflow_endpoint(request.base_url)
        inspected = self._validate_endpoint_owner(
            principal,
            endpoint,
            request.api_key,
            allow_existing_same_owner=True,
        )
        return {"ok": True, "connection": self._public_connection(inspected)}

    def create_endpoint(
        self,
        principal: AuthIdentity,
        request: PlaygroundEndpointCreateRequest,
    ) -> dict[str, Any]:
        require_role(principal, "boi.viewer")
        base_url = normalize_langflow_endpoint(request.base_url)
        inspected = self._validate_endpoint_owner(principal, base_url, request.api_key)
        with self._lock:
            record = self._read(principal.employee_id)
            endpoints = self._endpoint_records(record)
            if len(endpoints) >= MAX_ENDPOINTS:
                raise HTTPException(status_code=409, detail=f"up to {MAX_ENDPOINTS} Langflow endpoints are allowed")
            endpoint_id = f"ep-{uuid.uuid4().hex[:16]}"
            connection = {
                **inspected,
                "endpoint_id": endpoint_id,
                "name": request.name.strip(),
                "base_url": base_url,
                "endpoint": base_url,
                "api_key_encrypted": self.cipher.encrypt(request.api_key, owner=principal.employee_id),
                "api_key_fingerprint": hashlib.sha256(request.api_key.encode("utf-8")).hexdigest()[:12],
                "connected_at": now_iso(),
                "last_checked_at": now_iso(),
                "status": "connected",
                "last_error": "",
                "active": True,
                "auth_source": principal.auth_source,
            }
            endpoints.append(connection)
            record["endpoints"] = endpoints
            if request.make_default or not record.get("default_endpoint_id"):
                record["default_endpoint_id"] = endpoint_id
            self._write(principal.employee_id, record)
        return {"ok": True, "endpoint": self._public_connection(connection)}

    def update_endpoint(
        self,
        principal: AuthIdentity,
        endpoint_id: str,
        request: PlaygroundEndpointUpdateRequest,
    ) -> dict[str, Any]:
        require_role(principal, "boi.viewer")
        with self._lock:
            record = self._read(principal.employee_id)
            connection = self._endpoint(record, endpoint_id, require_active=False)
            candidate_url = normalize_langflow_endpoint(
                request.base_url
                if request.base_url is not None
                else str(connection.get("base_url") or connection.get("endpoint") or "")
            )
            candidate_key = (
                request.api_key
                if request.api_key is not None and request.api_key.strip()
                else self.cipher.decrypt(str(connection.get("api_key_encrypted") or ""), owner=principal.employee_id)
            )
            inspected = self._validate_endpoint_owner(
                principal,
                candidate_url,
                candidate_key,
                current_endpoint_id=endpoint_id,
            )
            connection.update(inspected)
            connection["base_url"] = candidate_url
            connection["endpoint"] = candidate_url
            if request.name is not None:
                connection["name"] = request.name.strip()
            if request.api_key is not None and request.api_key.strip():
                connection["api_key_encrypted"] = self.cipher.encrypt(candidate_key, owner=principal.employee_id)
                connection["api_key_fingerprint"] = hashlib.sha256(candidate_key.encode("utf-8")).hexdigest()[:12]
            if request.active is not None:
                connection["active"] = request.active
            connection["status"] = "connected"
            connection["last_error"] = ""
            connection["last_checked_at"] = now_iso()
            if request.make_default:
                record["default_endpoint_id"] = endpoint_id
            record.pop("connection", None)
            self._write(principal.employee_id, record)
        return {"ok": True, "endpoint": self._public_connection(connection)}

    def test_endpoint(self, principal: AuthIdentity, endpoint_id: str) -> dict[str, Any]:
        require_role(principal, "boi.viewer")
        with self._lock:
            record = self._read(principal.employee_id)
            connection = self._endpoint(record, endpoint_id, require_active=False)
            try:
                inspected = self._validate_endpoint_owner(
                    principal,
                    str(connection.get("base_url") or connection.get("endpoint") or ""),
                    self._api_key(record, endpoint_id),
                    current_endpoint_id=endpoint_id,
                )
            except HTTPException as exc:
                connection["status"] = "error"
                connection["last_error"] = str(exc.detail)
                connection["last_checked_at"] = now_iso()
                self._write(principal.employee_id, record)
                raise
            connection.update(inspected)
            connection["status"] = "connected"
            connection["last_error"] = ""
            connection["last_checked_at"] = now_iso()
            self._write(principal.employee_id, record)
        return {"ok": True, "endpoint": self._public_connection(connection)}

    def delete_endpoint(self, principal: AuthIdentity, endpoint_id: str) -> dict[str, Any]:
        require_role(principal, "boi.viewer")
        with self._lock:
            record = self._read(principal.employee_id)
            connection = self._endpoint(record, endpoint_id, require_active=False)
            references = [
                item
                for item in record.get("deployments") or []
                if isinstance(item, dict) and str(item.get("endpoint_id") or "") == endpoint_id
            ]
            if references:
                connection["active"] = False
                connection["status"] = "inactive"
                connection["last_error"] = "deployment references this endpoint"
                self._write(principal.employee_id, record)
                return {"ok": True, "deleted": False, "deactivated": True}
            record["endpoints"] = [
                item
                for item in self._endpoint_records(record)
                if str(item.get("endpoint_id") or "") != endpoint_id
            ]
            self._endpoint_setups(record).pop(endpoint_id, None)
            if str(record.get("default_endpoint_id") or "") == endpoint_id:
                record["default_endpoint_id"] = str(
                    (record["endpoints"][0] if record["endpoints"] else {}).get("endpoint_id") or ""
                )
            record.pop("connection", None)
            self._write(principal.employee_id, record)
        return {"ok": True, "deleted": True, "deactivated": False}

    def connect(self, principal: AuthIdentity, request: PlaygroundConnectRequest) -> dict[str, Any]:
        """Compatibility wrapper that creates or updates the default endpoint."""

        record = self._read(principal.employee_id)
        endpoints = self._endpoint_records(record)
        default_id = str(record.get("default_endpoint_id") or "")
        if default_id and endpoints:
            result = self.update_endpoint(
                principal,
                default_id,
                PlaygroundEndpointUpdateRequest(
                    base_url=request.endpoint,
                    api_key=request.api_key,
                    make_default=True,
                ),
            )
            return {"ok": True, "connection": result["endpoint"]}
        result = self.create_endpoint(
            principal,
            PlaygroundEndpointCreateRequest(
                name="Personal Langflow",
                base_url=request.endpoint,
                api_key=request.api_key,
                make_default=True,
            ),
        )
        return {"ok": True, "connection": result["endpoint"]}

    def _project(self, endpoint: str, api_key: str, employee_id: str) -> dict[str, Any]:
        name = f"{PROJECT_PREFIX}{employee_id}"
        return self.langflow.ensure_project(
            endpoint,
            api_key,
            name=name,
            description="BoI Agent Playground personal project",
        )

    def _variables(self, endpoint: str, api_key: str) -> list[dict[str, Any]]:
        return self.langflow.variables(endpoint, api_key)

    def _put_credential(self, endpoint: str, api_key: str, raw_pat: str) -> dict[str, Any]:
        return self.langflow.put_credential(
            endpoint,
            api_key,
            name=BOI_PAT_VARIABLE_NAME,
            value=raw_pat,
        )

    def _flows(self, endpoint: str, api_key: str) -> list[dict[str, Any]]:
        return self.langflow.flows(endpoint, api_key)

    def projects(self, principal: AuthIdentity, endpoint_id: str) -> dict[str, Any]:
        require_role(principal, "boi.viewer")
        record = self._read(principal.employee_id)
        connection = self._endpoint(record, endpoint_id)
        api_key = self._api_key(record, endpoint_id)
        payload = self.langflow.projects(
            str(connection.get("base_url") or connection.get("endpoint") or ""),
            api_key,
        )
        projects = [
            {
                "id": str(item.get("id") or ""),
                "name": str(item.get("name") or ""),
                "description": str(item.get("description") or ""),
            }
            for item in payload if isinstance(item, dict) and item.get("id")
        ] if isinstance(payload, list) else []
        return {"ok": True, "endpoint_id": endpoint_id, "projects": projects}

    def flows(self, principal: AuthIdentity, endpoint_id: str, project_id: str) -> dict[str, Any]:
        require_role(principal, "boi.viewer")
        record = self._read(principal.employee_id)
        connection = self._endpoint(record, endpoint_id)
        api_key = self._api_key(record, endpoint_id)
        endpoint = str(connection.get("base_url") or connection.get("endpoint") or "")
        projects = self.projects(principal, endpoint_id)["projects"]
        if project_id not in {str(item.get("id") or "") for item in projects}:
            raise HTTPException(status_code=404, detail="project does not belong to this endpoint connection")
        live = self._flows(endpoint, api_key)
        registered: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        for registry_item in record.get("flow_registry") or []:
            if not isinstance(registry_item, dict):
                continue
            identity = (
                str(registry_item.get("endpoint_id") or ""),
                str(registry_item.get("project_id") or ""),
                str(registry_item.get("flow_id") or ""),
            )
            registered.setdefault(identity, []).append(registry_item)
        deployments: dict[tuple[str, str, str], dict[str, Any]] = {}
        for deployment in record.get("deployments") or []:
            if not isinstance(deployment, dict):
                continue
            identity = (
                str(deployment.get("endpoint_id") or ""),
                str(deployment.get("project_id") or ""),
                str(deployment.get("flow_id") or ""),
            )
            deployments[identity] = deployment
        validation_rank = {
            "blocked": -1,
            "discovered": 0,
            "structural_validated": 1,
            "build_validated": 2,
            "runtime_validated": 3,
            "task_validated": 4,
            "action_ready": 5,
            "action_linked": 6,
        }
        items = []
        for item in live:
            folder_id = str(item.get("folder_id") or item.get("project_id") or "")
            if folder_id != project_id:
                continue
            flow_id = str(item.get("id") or "")
            identity = (endpoint_id, project_id, flow_id)
            deployment = deployments.get(identity, {})
            registry_candidates = registered.get(identity, [])
            deployment_version = str(
                deployment.get("asset_version")
                or deployment.get("artifact_version")
                or ""
            )
            deployment_checksum = str(deployment.get("artifact_checksum") or "")
            registry = next(
                (
                    candidate
                    for candidate in reversed(registry_candidates)
                    if (
                        not deployment_version
                        or str(candidate.get("artifact_version") or "")
                        == deployment_version
                    )
                    and (
                        not deployment_checksum
                        or str(candidate.get("artifact_checksum") or "")
                        == deployment_checksum
                    )
                ),
                {},
            )
            if not registry and registry_candidates:
                registry = max(
                    registry_candidates,
                    key=lambda candidate: (
                        validation_rank.get(
                            str(candidate.get("validation_status") or "discovered"),
                            0,
                        ),
                        str(candidate.get("validated_at") or candidate.get("last_seen_at") or ""),
                    ),
                )
            validation_status = str(
                registry.get("validation_status")
                or deployment.get("status")
                or "discovered"
            )
            items.append(
                {
                    "flow_id": flow_id,
                    "id": flow_id,
                    "name": str(item.get("name") or ""),
                    "endpoint_name": str(item.get("endpoint_name") or ""),
                    "project_id": project_id,
                    "endpoint_id": endpoint_id,
                    "updated_at": item.get("updated_at"),
                    "validation_status": validation_status,
                    "artifact_version": str(
                        registry.get("artifact_version")
                        or deployment_version
                    ),
                    "artifact_checksum": str(
                        registry.get("artifact_checksum")
                        or deployment_checksum
                    ),
                    "deployment_id": str(
                        registry.get("deployment_id")
                        or deployment.get("deployment_id")
                        or ""
                    ),
                    "flow_url": f"{endpoint}/flow/{flow_id}",
                }
            )
        items.sort(key=lambda item: (str(item.get("name") or "").lower(), str(item.get("flow_id") or "")))
        return {
            "ok": True,
            "endpoint_id": endpoint_id,
            "project_id": project_id,
            "flows": items,
        }

    @staticmethod
    def _runtime_flow_checksum(flow: dict[str, Any]) -> str:
        stable = {
            "id": str(flow.get("id") or ""),
            "name": str(flow.get("name") or ""),
            "endpoint_name": str(flow.get("endpoint_name") or ""),
            "description": str(flow.get("description") or ""),
            "folder_id": str(flow.get("folder_id") or flow.get("project_id") or ""),
            "data": flow.get("data") if isinstance(flow.get("data"), dict) else {},
        }
        return hashlib.sha256(
            json.dumps(
                stable,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        ).hexdigest()

    def _project_flow_snapshots(
        self,
        principal: AuthIdentity,
        endpoint_id: str,
        project_id: str,
    ) -> list[dict[str, Any]]:
        record = self._read(principal.employee_id)
        connection = self._endpoint(record, endpoint_id)
        api_key = self._api_key(record, endpoint_id)
        endpoint = str(connection.get("base_url") or connection.get("endpoint") or "")
        projects = self.langflow.projects(endpoint, api_key)
        if project_id not in {
            str(item.get("id") or "")
            for item in projects
            if isinstance(item, dict)
        }:
            raise HTTPException(status_code=404, detail="project does not belong to this endpoint connection")
        snapshots: list[dict[str, Any]] = []
        for listed in self._flows(endpoint, api_key):
            if not isinstance(listed, dict):
                continue
            listed_project = str(listed.get("folder_id") or listed.get("project_id") or "")
            if listed_project != project_id:
                continue
            flow_id = str(listed.get("id") or "")
            if not flow_id:
                continue
            try:
                detail = self.langflow.flow(endpoint, api_key, flow_id)
            except HTTPException:
                detail = listed
            snapshots.append(
                {
                    "flow_id": flow_id,
                    "name": str(detail.get("name") or listed.get("name") or ""),
                    "endpoint_name": str(
                        detail.get("endpoint_name")
                        or listed.get("endpoint_name")
                        or ""
                    ),
                    "runtime_checksum": self._runtime_flow_checksum(detail),
                    "updated_at": str(listed.get("updated_at") or ""),
                }
            )
        snapshots.sort(key=lambda item: (item["name"].lower(), item["flow_id"]))
        return snapshots

    @staticmethod
    def _agent_hub_version(value: str) -> tuple[int, int, int] | None:
        match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", str(value or ""))
        if not match:
            return None
        return (
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3) or 0),
        )

    def _validate_agent_hub_asset_compatibility(
        self,
        asset: dict[str, Any],
        langflow_version: str,
    ) -> None:
        current = parse_version(langflow_version)
        minimum = self._agent_hub_version(str(asset.get("min_langflow_version") or ""))
        maximum = self._agent_hub_version(str(asset.get("max_langflow_version") or ""))
        if minimum and current < minimum:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "agent_hub_asset_langflow_incompatible",
                    "message": "Agent Hub asset requires a newer Langflow version.",
                    "asset_id": asset.get("asset_id"),
                    "required_minimum": asset.get("min_langflow_version"),
                    "actual_version": langflow_version,
                },
            )
        if maximum and current > maximum:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "agent_hub_asset_langflow_incompatible",
                    "message": "Agent Hub asset is not approved for this Langflow version.",
                    "asset_id": asset.get("asset_id"),
                    "supported_maximum": asset.get("max_langflow_version"),
                    "actual_version": langflow_version,
                },
            )

    def _hub_adoption(
        self,
        record: dict[str, Any],
        adoption_id: str,
    ) -> dict[str, Any]:
        adoption = next(
            (
                item
                for item in record.get("hub_adoptions") or []
                if isinstance(item, dict)
                and str(item.get("adoption_id") or "") == adoption_id
            ),
            None,
        )
        if adoption is None:
            raise HTTPException(status_code=404, detail="Agent Hub adoption not found")
        return adoption

    def begin_hub_adoption(
        self,
        principal: AuthIdentity,
        request: PlaygroundHubAdoptionBeginRequest,
    ) -> dict[str, Any]:
        require_role(principal, "boi.editor")
        record = self._read(principal.employee_id)
        connection = self._endpoint(record, request.endpoint_id)
        unique_asset_ids = list(dict.fromkeys(str(value).strip() for value in request.asset_ids))
        source_assets: list[dict[str, Any]] = []
        for asset_id in unique_asset_ids:
            asset = self.agent_hub_asset(principal, asset_id)["asset"]
            self._validate_agent_hub_asset_compatibility(
                asset,
                str(connection.get("version") or ""),
            )
            source_assets.append(asset)
        snapshots = self._project_flow_snapshots(
            principal,
            request.endpoint_id,
            request.project_id,
        )
        adoption_id = f"adoption-{uuid.uuid4().hex[:16]}"
        adoption = {
            "adoption_id": adoption_id,
            "employee_id": principal.employee_id,
            "endpoint_id": request.endpoint_id,
            "project_id": request.project_id,
            "validation_profile": request.validation_profile,
            "source_assets": source_assets,
            "snapshot": {
                item["flow_id"]: item["runtime_checksum"]
                for item in snapshots
            },
            "status": "awaiting_agent_hub_deployment",
            "created_at": now_iso(),
            "last_checked_at": now_iso(),
        }
        with self._lock:
            current = self._read(principal.employee_id)
            self._endpoint(current, request.endpoint_id)
            current.setdefault("hub_adoptions", []).append(adoption)
            self._write(principal.employee_id, current)
        return {
            "ok": True,
            "adoption": {
                **adoption,
                "snapshot": {
                    "flow_count": len(snapshots),
                    "flow_ids": [item["flow_id"] for item in snapshots],
                },
            },
        }

    def discover_hub_adoption(
        self,
        principal: AuthIdentity,
        adoption_id: str,
    ) -> dict[str, Any]:
        require_role(principal, "boi.editor")
        record = self._read(principal.employee_id)
        adoption = self._hub_adoption(record, adoption_id)
        snapshots = self._project_flow_snapshots(
            principal,
            str(adoption.get("endpoint_id") or ""),
            str(adoption.get("project_id") or ""),
        )
        before = adoption.get("snapshot") if isinstance(adoption.get("snapshot"), dict) else {}
        candidates = []
        for item in snapshots:
            previous = str(before.get(item["flow_id"]) or "")
            if not previous or previous != item["runtime_checksum"]:
                candidates.append(
                    {
                        **item,
                        "change_kind": "created" if not previous else "updated",
                    }
                )
        with self._lock:
            current = self._read(principal.employee_id)
            current_adoption = self._hub_adoption(current, adoption_id)
            current_adoption["status"] = (
                "candidate_found" if candidates else "awaiting_agent_hub_deployment"
            )
            current_adoption["candidates"] = candidates
            current_adoption["last_checked_at"] = now_iso()
            self._write(principal.employee_id, current)
        return {
            "ok": True,
            "adoption_id": adoption_id,
            "status": "candidate_found" if candidates else "awaiting_agent_hub_deployment",
            "candidates": candidates,
        }

    def confirm_hub_adoption(
        self,
        principal: AuthIdentity,
        adoption_id: str,
        request: PlaygroundHubAdoptionConfirmRequest,
    ) -> dict[str, Any]:
        require_role(principal, "boi.editor")
        discovered = self.discover_hub_adoption(principal, adoption_id)
        candidate = next(
            (
                item
                for item in discovered["candidates"]
                if str(item.get("flow_id") or "") == request.flow_id
            ),
            None,
        )
        if candidate is None:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "agent_hub_flow_not_changed",
                    "message": "Select a Flow created or changed after the Agent Hub deployment started.",
                },
            )
        record = self._read(principal.employee_id)
        adoption = self._hub_adoption(record, adoption_id)
        source_assets = [
            item
            for item in adoption.get("source_assets") or []
            if isinstance(item, dict)
        ]
        for pinned in source_assets:
            current = self.agent_hub_asset(
                principal,
                str(pinned.get("asset_id") or ""),
            )["asset"]
            if current["metadata_checksum"] != pinned.get("metadata_checksum"):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "agent_hub_asset_changed",
                        "message": "Agent Hub asset metadata changed. Start the import again to pin the new version.",
                        "asset_id": current["asset_id"],
                    },
                )
        primary = next(
            (item for item in source_assets if item.get("type") == "json"),
            source_assets[0] if source_assets else {},
        )
        deployment = self.record_deployment(
            principal,
            PlaygroundDeploymentRequest(
                endpoint_id=str(adoption.get("endpoint_id") or ""),
                project_id=str(adoption.get("project_id") or ""),
                flow_id=request.flow_id,
                endpoint_name=str(candidate.get("endpoint_name") or ""),
                asset_version=str(primary.get("version") or ""),
                artifact_checksum=str(candidate.get("runtime_checksum") or ""),
                agent_hub_asset_id=str(primary.get("asset_id") or ""),
            ),
        )["deployment"]
        with self._lock:
            current_record = self._read(principal.employee_id)
            current_adoption = self._hub_adoption(current_record, adoption_id)
            current_adoption.update(
                {
                    "status": "confirmed",
                    "flow_id": request.flow_id,
                    "runtime_checksum": candidate["runtime_checksum"],
                    "deployment_id": deployment["deployment_id"],
                    "confirmed_at": now_iso(),
                }
            )
            stored_deployment = next(
                item
                for item in current_record.get("deployments") or []
                if isinstance(item, dict)
                and str(item.get("deployment_id") or "")
                == deployment["deployment_id"]
            )
            if stored_deployment is None:
                raise HTTPException(status_code=500, detail="Agent Hub deployment record was not stored")
            stored_deployment.update(
                {
                    "origin": "agent_hub_approved_asset",
                    "adoption_id": adoption_id,
                    "source_assets": source_assets,
                    "validation_profile": str(adoption.get("validation_profile") or ""),
                    "runtime_checksum": candidate["runtime_checksum"],
                }
            )
            registry_item = next(
                (
                    item
                    for item in current_record.get("flow_registry") or []
                    if isinstance(item, dict)
                    and str(item.get("endpoint_id") or "")
                    == str(adoption.get("endpoint_id") or "")
                    and str(item.get("project_id") or "")
                    == str(adoption.get("project_id") or "")
                    and str(item.get("flow_id") or "") == request.flow_id
                ),
                None,
            )
            if registry_item is not None:
                registry_item.update(
                    {
                        "origin": "agent_hub_approved_asset",
                        "adoption_id": adoption_id,
                        "source_assets": source_assets,
                        "validation_profile": str(adoption.get("validation_profile") or ""),
                        "runtime_checksum": candidate["runtime_checksum"],
                    }
                )
            self._write(principal.employee_id, current_record)
            deployment = dict(stored_deployment)
        return {
            "ok": True,
            "adoption_id": adoption_id,
            "deployment": deployment,
            "source_assets": source_assets,
        }

    def _live_flow(
        self,
        principal: AuthIdentity,
        endpoint_id: str,
        project_id: str,
        flow_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any], str]:
        record = self._read(principal.employee_id)
        connection = self._endpoint(record, endpoint_id)
        api_key = self._api_key(record, endpoint_id)
        endpoint = str(connection.get("base_url") or connection.get("endpoint") or "")
        projects = self.projects(principal, endpoint_id)["projects"]
        if project_id not in {str(item.get("id") or "") for item in projects}:
            raise HTTPException(status_code=404, detail="project does not belong to this endpoint connection")
        flow = next(
            (
                item
                for item in self._flows(endpoint, api_key)
                if str(item.get("id") or "") == flow_id
                and str(item.get("folder_id") or item.get("project_id") or "") == project_id
            ),
            None,
        )
        if flow is None:
            raise HTTPException(status_code=404, detail="Flow does not belong to the selected endpoint and project")
        return connection, flow, api_key

    @staticmethod
    def _upsert_flow_registry(record: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        registry = [item for item in record.get("flow_registry") or [] if isinstance(item, dict)]
        identity = (
            str(payload.get("endpoint_id") or ""),
            str(payload.get("project_id") or ""),
            str(payload.get("flow_id") or ""),
            str(payload.get("artifact_version") or ""),
            str(payload.get("artifact_checksum") or ""),
        )
        existing = next(
            (
                item
                for item in registry
                if (
                    str(item.get("endpoint_id") or ""),
                    str(item.get("project_id") or ""),
                    str(item.get("flow_id") or ""),
                    str(item.get("artifact_version") or ""),
                    str(item.get("artifact_checksum") or ""),
                ) == identity
            ),
            None,
        )
        if existing is None:
            existing = {}
            registry.append(existing)
        existing.update(payload)
        record["flow_registry"] = registry
        return existing

    def _canonical_flow(self, endpoint: str, api_key: str, project_id: str) -> dict[str, Any] | None:
        candidates = [
            item
            for item in self._flows(endpoint, api_key)
            if (
                str(item.get("endpoint_name") or "") == CANONICAL_FLOW_ENDPOINT
                or str(item.get("name") or "") == CANONICAL_FLOW_NAME
            )
            and str(item.get("folder_id") or "") == project_id
        ]
        candidates.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        return candidates[0] if candidates else None

    def _install_flow(
        self,
        endpoint: str,
        api_key: str,
        project_id: str,
        *,
        force_upload: bool = False,
    ) -> dict[str, Any]:
        existing = None if force_upload else self._canonical_flow(endpoint, api_key, project_id)
        if existing:
            return existing
        flow_path = self.repo_root / "langflow" / "flows" / "boi_wiki_agent_loop.json"
        if not flow_path.exists():
            raise HTTPException(status_code=503, detail="canonical Agent Playground Flow artifact is missing")
        exported = json.loads(flow_path.read_text(encoding="utf-8"))
        flow_data = exported.get("data") if isinstance(exported.get("data"), dict) else exported
        # Use the same create contract as immutable Agent Hub PR #25. Langflow's
        # upload endpoint preserves stale frontend component metadata and can
        # mark otherwise valid 1.11 ChatInput/ChatOutput nodes as outdated.
        return self.langflow.create_flow(
            endpoint,
            api_key,
            name=str(exported.get("name") or CANONICAL_FLOW_NAME),
            description=str(exported.get("description") or ""),
            data=flow_data,
            project_id=project_id,
        )

    @staticmethod
    def _flow_reinstall_required(exc: Exception) -> bool:
        detail = getattr(exc, "detail", exc)
        serialized = json.dumps(detail, ensure_ascii=False, default=str).lower()
        return any(
            marker in serialized
            for marker in (
                "outdated component",
                "error building component",
                "component build",
            )
        )

    def _canonical_checksum(self) -> str:
        flow_path = self.repo_root / "langflow" / "flows" / "boi_wiki_agent_loop.json"
        if not flow_path.exists():
            return ""
        return hashlib.sha256(flow_path.read_bytes()).hexdigest()

    def _model_agent_checksum(self) -> str:
        flow_path = (
            self.repo_root
            / "langflow"
            / "flows"
            / "boi_wiki_agent_loop_model_agent.json"
        )
        if not flow_path.exists():
            return ""
        return hashlib.sha256(flow_path.read_bytes()).hexdigest()

    def _run(
        self,
        endpoint: str,
        api_key: str,
        flow_ref: str,
        payload: PlaygroundFlowTestRequest,
        *,
        run_token: str = "",
    ) -> dict[str, Any]:
        input_value = json.dumps(
            {
                "question": payload.question,
                "business_context": payload.business_context,
                "task_ref": payload.task_ref,
                "page_ref": payload.page_ref,
                "context_id": payload.context_id,
                "sop_ref": payload.sop_ref,
                "sop_stage": payload.sop_stage,
                "event_ref": payload.event_ref,
                "action_ref": payload.action_ref,
                "prior_results": payload.prior_results,
                "required_evidence": payload.required_evidence,
                "missing_evidence": payload.missing_evidence,
                "save_mode": payload.save_mode,
                "title": payload.title,
                "trace_id": f"playground-{uuid.uuid4().hex}",
            },
            ensure_ascii=False,
        )
        result = self.langflow.run(
            endpoint,
            api_key,
            flow_ref,
            input_value=input_value,
            run_token=run_token,
        )
        serialized = json.dumps(result, ensure_ascii=False, default=str)
        if any(pattern.search(serialized) for pattern in SECRET_PATTERNS):
            raise HTTPException(status_code=502, detail="secret-like value detected in Langflow output")
        return result

    def bootstrap(self, principal: AuthIdentity, request: PlaygroundBootstrapRequest) -> dict[str, Any]:
        require_role(principal, "boi.viewer")
        endpoint_id = ""
        current_step = "connection"
        with self._lock:
            record = self._read(principal.employee_id)
            connection = self._endpoint(record, request.endpoint_id)
            endpoint_id = str(connection.get("endpoint_id") or "")
            setup = self._endpoint_setup(record, endpoint_id)
            setup.update(
                {
                    "onboarding_status": "provisioning",
                    "current_step": "connection",
                    "last_error": "",
                    "started_at": str(setup.get("started_at") or now_iso()),
                }
            )
            self._write(principal.employee_id, record)
        try:
            with self._lock:
                record = self._read(principal.employee_id)
                connection = self._endpoint(record, endpoint_id)
                setup = self._endpoint_setup(record, endpoint_id)
                endpoint = str(connection.get("base_url") or connection.get("endpoint") or "")
                api_key = self._api_key(record, endpoint_id)
                inspected = self.inspect_connection(endpoint, api_key)
                if inspected["langflow_user_id"] != connection.get("langflow_user_id"):
                    raise HTTPException(status_code=409, detail="Langflow API Key owner changed after connection")

                current_step = "knowledge"
                setup["current_step"] = current_step
                self._write(principal.employee_id, record)
                project = self._project(endpoint, api_key, principal.employee_id)
                project_record = {
                    "id": str(project.get("id") or ""),
                    "name": str(project.get("name") or f"{PROJECT_PREFIX}{principal.employee_id}"),
                    "endpoint_id": endpoint_id,
                }
                setup["project"] = project_record
                bundle_check = self.langflow.verify_component_bundle(endpoint, api_key)
                setup["bundle"] = {
                    "version": COMPONENT_BUNDLE_VERSION,
                    "mode": COMPONENT_BUNDLE_MODE,
                    **bundle_check,
                    "checked_at": now_iso(),
                }
                self._write(principal.employee_id, record)

                wiki_credentials = (
                    record.get("wiki_credentials")
                    if isinstance(record.get("wiki_credentials"), dict)
                    else {}
                )
                current_credential = (
                    setup.get("wiki_credential")
                    if isinstance(setup.get("wiki_credential"), dict)
                    else wiki_credentials.get(endpoint_id) or {}
                )
                current_token_id = str((current_credential or {}).get("token_id") or "")
                current_token = (
                    self.pat_service.store.get("tokens", current_token_id)
                    if current_token_id
                    else None
                )
                variable_exists = any(
                    item.get("name") == BOI_PAT_VARIABLE_NAME
                    for item in self._variables(endpoint, api_key)
                )
                if not current_token or current_token.get("revoked_at") or not variable_exists:
                    if current_token and not current_token.get("revoked_at"):
                        self.pat_service.revoke(principal, current_token_id)
                    issued = self.pat_service.create(
                        principal,
                        TokenCreateRequest(
                            name="Agent Playground BoI knowledge",
                            scopes=(
                                ["boi.read", "boi.draft"]
                                if principal.is_admin or "boi.editor" in principal.roles
                                else ["boi.read"]
                            ),
                            expires_in_days=None,
                        ),
                    )
                    try:
                        self._put_credential(endpoint, api_key, str(issued["token"]))
                    except Exception:
                        self.pat_service.revoke(principal, str(issued["token_id"]))
                        raise
                    current_credential = {
                        "token_id": issued["token_id"],
                        "variable_name": BOI_PAT_VARIABLE_NAME,
                        "expires_at": None,
                        "linked_at": now_iso(),
                    }
                    wiki_credentials[endpoint_id] = current_credential
                    record["wiki_credentials"] = wiki_credentials
                    setup["wiki_credential"] = current_credential
                    if endpoint_id == str(record.get("default_endpoint_id") or ""):
                        record["wiki_credential"] = current_credential
                    # Persist before Flow smoke so a retry cannot orphan another PAT.
                    self._write(principal.employee_id, record)
                else:
                    setup["wiki_credential"] = current_credential

                current_step = "flow"
                setup["current_step"] = current_step
                self._write(principal.employee_id, record)
                flow = self._install_flow(endpoint, api_key, project_record["id"])
                flow_ref = str(flow.get("id") or flow.get("endpoint_name") or CANONICAL_FLOW_ENDPOINT)
                smoke_request = PlaygroundFlowTestRequest(
                    endpoint_id=endpoint_id,
                    project_id=project_record["id"],
                    question=request.smoke_question,
                    save_mode="preview",
                    title="Agent Playground 온보딩 확인",
                )
                try:
                    smoke_result = self._run(endpoint, api_key, flow_ref, smoke_request)
                except HTTPException as exc:
                    if not self._flow_reinstall_required(exc):
                        raise
                    flow = self._install_flow(
                        endpoint,
                        api_key,
                        project_record["id"],
                        force_upload=True,
                    )
                    flow_ref = str(
                        flow.get("id") or flow.get("endpoint_name") or CANONICAL_FLOW_ENDPOINT
                    )
                    smoke_result = self._run(endpoint, api_key, flow_ref, smoke_request)
                canonical_checksum = self._canonical_checksum()
                canonical_flow = {
                    "id": str(flow.get("id") or ""),
                    "name": str(flow.get("name") or CANONICAL_FLOW_NAME),
                    "endpoint_name": str(flow.get("endpoint_name") or CANONICAL_FLOW_ENDPOINT),
                    "version": CANONICAL_FLOW_VERSION,
                    "checksum": canonical_checksum,
                    "flow_url": f"{endpoint}/flow/{flow_ref}",
                    "endpoint_id": endpoint_id,
                    "project_id": project_record["id"],
                }
                smoke_record = {
                    "status": "passed",
                    "checked_at": now_iso(),
                    "flow_id": canonical_flow["id"],
                    "session_id": str(smoke_result.get("session_id") or ""),
                    "mode": "preview",
                }
                setup.update(
                    {
                        "project": project_record,
                        "canonical_flow": canonical_flow,
                        "smoke": smoke_record,
                        "onboarding_status": "ready",
                        "current_step": "complete",
                        "last_error": "",
                        "completed_at": now_iso(),
                    }
                )
                canonical_flows = [
                    item
                    for item in record.get("canonical_flows") or []
                    if isinstance(item, dict)
                    and str(item.get("endpoint_id") or "") != endpoint_id
                ]
                canonical_flows.append(canonical_flow)
                record["canonical_flows"] = canonical_flows
                if endpoint_id == str(record.get("default_endpoint_id") or ""):
                    record["project"] = project_record
                    record["canonical_flow"] = canonical_flow
                    record["wiki_credential"] = current_credential
                self._upsert_flow_registry(
                    record,
                    {
                        "endpoint_id": endpoint_id,
                        "project_id": project_record["id"],
                        "flow_id": canonical_flow["id"],
                        "name": canonical_flow["name"],
                        "endpoint_name": canonical_flow["endpoint_name"],
                        "artifact_version": CANONICAL_FLOW_VERSION,
                        "artifact_checksum": canonical_checksum,
                        "validation_status": "runtime_validated",
                        "validation_history": [
                            {
                                "stage": "runtime_validated",
                                "status": "passed",
                                "checked_at": now_iso(),
                                "mode": "preview",
                            }
                        ],
                        "last_seen_at": now_iso(),
                    },
                )
                record["last_test"] = {
                    "status": "passed",
                    "mode": "preview",
                    "tested_at": smoke_record["checked_at"],
                    "endpoint_id": endpoint_id,
                    "project_id": project_record["id"],
                    "flow_id": canonical_flow["id"],
                    "session_id": smoke_record["session_id"],
                }
                self._write(principal.employee_id, record)
        except Exception as exc:
            with self._lock:
                failed_record = self._read(principal.employee_id)
                failed_setup = self._endpoint_setup(failed_record, endpoint_id)
                failed_setup.update(
                    {
                        "onboarding_status": "error",
                        "current_step": current_step,
                        "last_error": str(getattr(exc, "detail", exc))[:1000],
                        "failed_at": now_iso(),
                    }
                )
                self._write(principal.employee_id, failed_record)
            raise
        return {"ok": True, "state": self.state(principal, live=False)}

    def test_flow(
        self,
        principal: AuthIdentity,
        flow_id: str,
        request: PlaygroundFlowTestRequest,
    ) -> dict[str, Any]:
        require_role(principal, "boi.viewer")
        if request.save_mode == "private_draft":
            require_role(principal, "boi.editor")
        record = self._read(principal.employee_id)
        canonical = record.get("canonical_flow") if isinstance(record.get("canonical_flow"), dict) else {}
        endpoint_id = str(request.endpoint_id or canonical.get("endpoint_id") or record.get("default_endpoint_id") or "")
        project_id = str(request.project_id or canonical.get("project_id") or (record.get("project") or {}).get("id") or "")
        connection, _, api_key = self._live_flow(principal, endpoint_id, project_id, flow_id)
        endpoint = str(connection.get("base_url") or connection.get("endpoint") or "")
        try:
            result = self._run(endpoint, api_key, flow_id, request)
        except Exception as exc:
            record["last_test"] = {
                "status": "failed",
                "mode": request.save_mode,
                "tested_at": now_iso(),
                "endpoint_id": endpoint_id,
                "project_id": project_id,
                "flow_id": flow_id,
                "error": str(getattr(exc, "detail", exc))[:1000],
            }
            self._write(principal.employee_id, record)
            raise
        record["last_test"] = {
            "status": "passed",
            "mode": request.save_mode,
            "tested_at": now_iso(),
            "endpoint_id": endpoint_id,
            "project_id": project_id,
            "flow_id": flow_id,
            "session_id": str(result.get("session_id") or ""),
        }
        existing_registry = next(
            (
                item
                for item in record.get("flow_registry") or []
                if isinstance(item, dict)
                and str(item.get("endpoint_id") or "") == endpoint_id
                and str(item.get("project_id") or "") == project_id
                and str(item.get("flow_id") or "") == flow_id
            ),
            {},
        )
        registry_item = self._upsert_flow_registry(
            record,
            {
                "endpoint_id": endpoint_id,
                "project_id": project_id,
                "flow_id": flow_id,
                "artifact_version": next(
                    (
                        str(item.get("artifact_version") or "")
                        for item in record.get("flow_registry") or []
                        if isinstance(item, dict)
                        and str(item.get("endpoint_id") or "") == endpoint_id
                        and str(item.get("project_id") or "") == project_id
                        and str(item.get("flow_id") or "") == flow_id
                    ),
                    "",
                ),
                "artifact_checksum": next(
                    (
                        str(item.get("artifact_checksum") or "")
                        for item in record.get("flow_registry") or []
                        if isinstance(item, dict)
                        and str(item.get("endpoint_id") or "") == endpoint_id
                        and str(item.get("project_id") or "") == project_id
                        and str(item.get("flow_id") or "") == flow_id
                    ),
                    "",
                ),
                "validation_status": advance_flow_validation_status(
                    str(existing_registry.get("validation_status") or ""),
                    "runtime_validated",
                ),
                "last_test": record["last_test"],
            },
        )
        registry_item.setdefault("validation_history", []).append(
            {
                "stage": "runtime_validated",
                "status": "passed",
                "checked_at": now_iso(),
                "save_mode": request.save_mode,
            }
        )
        self._write(principal.employee_id, record)
        return {
            "ok": True,
            "endpoint_id": endpoint_id,
            "project_id": project_id,
            "flow_id": flow_id,
            "mode": request.save_mode,
            "result": result,
        }

    def record_deployment(self, principal: AuthIdentity, request: PlaygroundDeploymentRequest) -> dict[str, Any]:
        require_role(principal, "boi.editor")
        record = self._read(principal.employee_id)
        connection, flow, _ = self._live_flow(
            principal,
            request.endpoint_id,
            request.project_id,
            request.flow_id,
        )
        connection_endpoint = str(connection.get("base_url") or connection.get("endpoint") or "")
        if request.flow_url:
            deployed_endpoint = normalize_langflow_endpoint(request.flow_url)
            if urlsplit(connection_endpoint).netloc != urlsplit(deployed_endpoint).netloc:
                raise HTTPException(
                    status_code=409,
                    detail="Agent Hub deployment must target the selected Langflow endpoint",
                )
        if request.agent_hub_flow_url:
            # Informational evidence can use the Agent Hub container-facing host
            # while runtime invocation remains bound to the selected connection.
            normalize_langflow_endpoint(request.agent_hub_flow_url)
        checksum = request.artifact_checksum or (
            self._canonical_checksum()
            if str(flow.get("name") or "") == CANONICAL_FLOW_NAME
            or str(flow.get("endpoint_name") or "") == CANONICAL_FLOW_ENDPOINT
            else hashlib.sha256(
                json.dumps(flow, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()
        )
        deployment_id = f"hub-{uuid.uuid4().hex[:16]}"
        deployment = {
            "deployment_id": deployment_id,
            "employee_id": principal.employee_id,
            "endpoint_id": request.endpoint_id,
            "project_id": request.project_id,
            "flow_url": request.flow_url or f"{connection_endpoint}/flow/{request.flow_id}",
            "agent_hub_flow_url": request.agent_hub_flow_url,
            "flow_id": request.flow_id,
            "flow_name": str(flow.get("name") or ""),
            "endpoint_name": request.endpoint_name or str(flow.get("endpoint_name") or ""),
            "asset_version": request.asset_version,
            "artifact_checksum": checksum,
            "agent_hub_asset_id": request.agent_hub_asset_id,
            "agent_hub_endpoint_id": request.agent_hub_endpoint_id,
            "agent_hub_deployment_id": request.agent_hub_deployment_id,
            "status": "discovered",
            "created_at": now_iso(),
        }
        record.setdefault("deployments", []).append(deployment)
        self._upsert_flow_registry(
            record,
            {
                "endpoint_id": request.endpoint_id,
                "project_id": request.project_id,
                "flow_id": request.flow_id,
                "name": str(flow.get("name") or ""),
                "endpoint_name": str(flow.get("endpoint_name") or ""),
                "artifact_version": request.asset_version,
                "artifact_checksum": checksum,
                "deployment_id": deployment_id,
                "validation_status": "discovered",
                "last_seen_at": now_iso(),
            },
        )
        self._write(principal.employee_id, record)
        return {"ok": True, "deployment": deployment}

    @staticmethod
    def _flow_contract(
        flow: dict[str, Any],
        validation_profile: str = "boi_knowledge_draft",
    ) -> dict[str, Any]:
        serialized = json.dumps(flow, ensure_ascii=False, default=str)
        flow_data = flow.get("data") if isinstance(flow.get("data"), dict) else flow
        component_identities: set[str] = set()
        for node in flow_data.get("nodes") or []:
            if isinstance(node, str):
                component_identities.add(node)
                continue
            if not isinstance(node, dict):
                continue
            data = node.get("data") if isinstance(node.get("data"), dict) else {}
            component = (
                data.get("node")
                if isinstance(data.get("node"), dict)
                else {}
            )
            for value in (
                node.get("id"),
                node.get("type"),
                data.get("type"),
                data.get("display_name"),
                component.get("name"),
                component.get("display_name"),
            ):
                normalized = str(value or "").strip()
                if normalized:
                    component_identities.add(normalized)

        def has_component(name: str) -> bool:
            return any(
                identity == name
                or identity.startswith(f"{name}-")
                or f":{name}@" in identity
                for identity in component_identities
            )

        profiles = {
            "generic_action": {
                "required_components": [],
                "forbidden_components": [],
                "inputs": ["question"],
                "outputs": ["answer"],
                "strict_manifest": False,
            },
            "boi_knowledge": {
                "required_components": ["BoIWikiKnowledge"],
                "forbidden_components": ["BoIWikiSave"],
                "inputs": [
                    "question",
                    "business_context",
                    "task_ref",
                    "page_ref",
                    "context_id",
                    "sop_ref",
                    "sop_stage",
                    "event_ref",
                    "action_ref",
                    "prior_results",
                    "required_evidence",
                    "missing_evidence",
                ],
                "outputs": [
                    "answer",
                    "task_context",
                    "source_references",
                    "ontology_relationships",
                    "grounding_status",
                    "provenance",
                ],
                "strict_manifest": True,
            },
            "boi_knowledge_draft": {
                "required_components": ["BoIWikiKnowledge", "BoIWikiSave"],
                "forbidden_components": [],
                "inputs": [
                    "question",
                    "business_context",
                    "task_ref",
                    "page_ref",
                    "context_id",
                    "sop_ref",
                    "sop_stage",
                    "event_ref",
                    "action_ref",
                    "prior_results",
                    "required_evidence",
                    "missing_evidence",
                    "save_mode",
                    "title",
                ],
                "outputs": [
                    "answer",
                    "task_context",
                    "source_references",
                    "ontology_relationships",
                    "grounding_status",
                    "draft_reference",
                    "wiki_url",
                    "provenance",
                ],
                "strict_manifest": True,
            },
        }
        profile = profiles.get(validation_profile) or profiles["boi_knowledge_draft"]
        required_components = list(profile["required_components"])
        forbidden_components = list(profile["forbidden_components"])
        missing_components = [name for name in required_components if not has_component(name)]
        present_forbidden = [name for name in forbidden_components if has_component(name)]
        expected_inputs = list(profile["inputs"])
        expected_outputs = list(profile["outputs"])
        declared_contract = (
            flow_data.get("boi_contract")
            if isinstance(flow_data.get("boi_contract"), dict)
            else {}
        )
        declared_agent_kind = str(declared_contract.get("agent_kind") or "")
        model_backed = (
            declared_agent_kind == "openai_compatible_model"
            or has_component("BoIModelAgent")
        )
        declared_hash = str(flow_data.get("boi_contract_sha256") or "")
        computed_hash = (
            hashlib.sha256(
                json.dumps(
                    declared_contract,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            if declared_contract
            else ""
        )
        if validation_profile == "generic_action":
            if declared_contract:
                declared_inputs = declared_contract.get("inputs")
                declared_outputs = declared_contract.get("outputs")
                contract_fields = {
                    "version": bool(str(declared_contract.get("version") or "")),
                    "inputs": (
                        isinstance(declared_inputs, list)
                        and "question" in declared_inputs
                    ),
                    "outputs": (
                        isinstance(declared_outputs, list)
                        and "answer" in declared_outputs
                    ),
                    "checksum": bool(declared_hash) and declared_hash == computed_hash,
                }
                expected_inputs = [
                    str(value) for value in declared_inputs if str(value)
                ] if isinstance(declared_inputs, list) else expected_inputs
                expected_outputs = [
                    str(value) for value in declared_outputs if str(value)
                ] if isinstance(declared_outputs, list) else expected_outputs
                inferred_manifest = False
            else:
                has_chat_input = has_component("ChatInput") or "Chat Input" in component_identities
                has_chat_output = has_component("ChatOutput") or "Chat Output" in component_identities
                contract_fields = {
                    "version": True,
                    "inputs": has_chat_input,
                    "outputs": has_chat_output,
                    "checksum": True,
                }
                inferred_manifest = True
        else:
            contract_fields = {
                "version": str(declared_contract.get("version") or "") == CANONICAL_FLOW_VERSION,
                "inputs": declared_contract.get("inputs") == expected_inputs,
                "outputs": declared_contract.get("outputs") == expected_outputs,
                "checksum": bool(declared_hash) and declared_hash == computed_hash,
            }
            inferred_manifest = False
        secret_matches = [
            pattern.pattern
            for pattern in SECRET_PATTERNS
            if pattern.search(serialized)
        ]
        return {
            "ok": (
                not missing_components
                and not present_forbidden
                and not secret_matches
                and all(contract_fields.values())
            ),
            "validation_profile": validation_profile,
            "components": {
                "required": required_components,
                "missing": missing_components,
                "forbidden": forbidden_components,
                "present_forbidden": present_forbidden,
            },
            "manifest_contract": {
                "ok": all(contract_fields.values()),
                "fields": contract_fields,
                "declared_checksum": declared_hash,
                "computed_checksum": computed_hash,
                "inferred": inferred_manifest,
            },
            "secret_scan": {
                "ok": not secret_matches,
                "matched_patterns": secret_matches,
            },
            "input_contract": expected_inputs,
            "output_contract": expected_outputs,
            "agent_kind": (
                "openai_compatible_model"
                if model_backed
                else declared_agent_kind or "contract_agent"
            ),
        }

    @staticmethod
    def _generic_runtime_contract(result: dict[str, Any]) -> dict[str, Any]:
        def answer_text(value: Any, parent_key: str = "") -> str:
            if isinstance(value, str):
                return value.strip() if parent_key in {"answer", "text", "content"} else ""
            if isinstance(value, dict):
                for preferred in ("answer", "text", "content"):
                    if preferred in value:
                        found = answer_text(value[preferred], preferred)
                        if found:
                            return found
                for preferred in ("message", "result", "results", "output", "outputs", "data"):
                    if preferred in value:
                        found = answer_text(value[preferred], preferred)
                        if found:
                            return found
                for key, child in value.items():
                    found = answer_text(child, str(key))
                    if found:
                        return found
            if isinstance(value, list):
                for child in value:
                    found = answer_text(child, parent_key)
                    if found:
                        return found
            return ""

        answer = answer_text(result)
        return {
            "ok": bool(answer),
            "fields": {"answer": bool(answer)},
            "answer_length": len(answer),
        }

    @staticmethod
    def _contract_payload(result: Any) -> dict[str, Any]:
        if isinstance(result, dict):
            if {
                "source_references",
                "grounding_status",
                "provenance",
            }.issubset(result):
                return result
            for value in result.values():
                found = AgentPlaygroundService._contract_payload(value)
                if found:
                    return found
        if isinstance(result, list):
            for value in result:
                found = AgentPlaygroundService._contract_payload(value)
                if found:
                    return found
        return {}

    @classmethod
    def _runtime_contract(cls, result: dict[str, Any]) -> dict[str, Any]:
        payload = cls._contract_payload(result)
        sources = payload.get("source_references")
        grounding = str(payload.get("grounding_status") or "")
        provenance = payload.get("provenance")
        fields = {
            "source_references": isinstance(sources, list) and bool(sources),
            "grounding_status": grounding in {
                "grounded_with_ontology",
                "grounded_document_fallback",
                "grounded_ontology_only",
            },
            "provenance": isinstance(provenance, dict) and bool(provenance),
        }
        return {
            "ok": all(fields.values()),
            "fields": fields,
            "grounding_status": grounding,
            "source_count": len(sources) if isinstance(sources, list) else 0,
            "ontology_count": len(payload.get("ontology_relationships") or []),
        }

    @classmethod
    def _model_runtime_contract(cls, result: dict[str, Any]) -> dict[str, Any]:
        payload = cls._contract_payload(result)
        provenance = payload.get("provenance") if isinstance(payload.get("provenance"), dict) else {}
        knowledge_provenance = (
            provenance.get("knowledge_provenance")
            if isinstance(provenance.get("knowledge_provenance"), dict)
            else {}
        )
        model_trace = (
            provenance.get("model_agent")
            if isinstance(provenance.get("model_agent"), dict)
            else knowledge_provenance.get("model_agent")
            if isinstance(knowledge_provenance.get("model_agent"), dict)
            else payload.get("model_trace")
            if isinstance(payload.get("model_trace"), dict)
            else {}
        )
        answer = str(payload.get("answer") or "").strip()
        fields = {
            "real_inference": model_trace.get("real_inference") is True,
            "model": bool(str(model_trace.get("model") or "")),
            "provider": str(model_trace.get("provider") or "") == "openai-compatible",
            "answer": bool(answer),
        }
        return {
            "ok": all(fields.values()),
            "fields": fields,
            "model": str(model_trace.get("model") or ""),
            "response_id": str(model_trace.get("response_id") or ""),
            "latency_ms": model_trace.get("latency_ms"),
        }

    def validate_flow(
        self,
        principal: AuthIdentity,
        flow_id: str,
        request: PlaygroundFlowValidationRequest,
    ) -> dict[str, Any]:
        require_role(principal, "boi.editor")
        require_role(principal, "boi.action_invoker")
        connection, listed_flow, api_key = self._live_flow(
            principal,
            request.endpoint_id,
            request.project_id,
            flow_id,
        )
        record_before = self._read(principal.employee_id)
        exact_deployment = next(
            (
                item
                for item in reversed(record_before.get("deployments") or [])
                if isinstance(item, dict)
                and str(item.get("endpoint_id") or "") == request.endpoint_id
                and str(item.get("project_id") or "") == request.project_id
                and str(item.get("flow_id") or "") == flow_id
            ),
            {},
        )
        validation_profile = str(
            exact_deployment.get("validation_profile")
            or "boi_knowledge_draft"
        )
        artifact_version = str(
            exact_deployment.get("asset_version")
            or exact_deployment.get("artifact_version")
            or request.artifact_version
        )
        if validation_profile not in {
            "generic_action",
            "boi_knowledge",
            "boi_knowledge_draft",
        }:
            validation_profile = "boi_knowledge_draft"
        endpoint = str(connection.get("base_url") or connection.get("endpoint") or "")
        try:
            flow = self.langflow.flow(endpoint, api_key, flow_id)
            if not isinstance(flow, dict):
                flow = listed_flow
        except HTTPException:
            flow = listed_flow
        structural = self._flow_contract(flow, validation_profile)
        checksum = request.artifact_checksum or (
            self._canonical_checksum()
            if str(flow.get("name") or listed_flow.get("name") or "") == CANONICAL_FLOW_NAME
            else hashlib.sha256(
                json.dumps(flow, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()
        )
        history = [
            {
                "stage": "discovered",
                "status": "passed",
                "checked_at": now_iso(),
                "flow_id": flow_id,
            },
            {
                "stage": "structural_validated",
                "status": "passed" if structural["ok"] else "failed",
                "checked_at": now_iso(),
                "details": structural,
            },
        ]
        validation_status = "blocked"
        failure_reason = ""
        runtime_result: dict[str, Any] = {}
        task_result: dict[str, Any] = {}
        if structural["ok"]:
            history.append(
                {
                    "stage": "build_validated",
                    "status": "passed",
                    "checked_at": now_iso(),
                    "details": {"flow_loaded": True, "components_resolved": True},
                }
            )
            preview = PlaygroundFlowTestRequest(
                endpoint_id=request.endpoint_id,
                project_id=request.project_id,
                question=request.question,
                save_mode="preview",
                title="Flow 검증 미리보기",
            )
            runtime_result = self._run(endpoint, api_key, flow_id, preview)
            runtime_contract = (
                self._generic_runtime_contract(runtime_result)
                if validation_profile == "generic_action"
                else self._runtime_contract(runtime_result)
            )
            model_runtime_contract = (
                self._model_runtime_contract(runtime_result)
                if structural.get("agent_kind") == "openai_compatible_model"
                else {"ok": True, "fields": {}}
            )
            history.append(
                {
                    "stage": "runtime_validated",
                    "status": (
                        "passed"
                        if runtime_contract["ok"] and model_runtime_contract["ok"]
                        else "failed"
                    ),
                    "checked_at": now_iso(),
                    "details": {
                        **runtime_contract,
                        "model_inference": model_runtime_contract,
                    },
                }
            )
            if (
                runtime_contract["ok"]
                and model_runtime_contract["ok"]
                and validation_profile == "generic_action"
            ):
                history.append(
                    {
                        "stage": "task_validated",
                        "status": "passed",
                        "checked_at": now_iso(),
                        "details": {
                            "profile": validation_profile,
                            "wiki_task_contract": "not_required",
                            "side_effect_policy": "explicit_action_review_required",
                        },
                    }
                )
                validation_status = "action_ready"
                history.append(
                    {
                        "stage": "action_ready",
                        "status": "passed",
                        "checked_at": now_iso(),
                    }
                )
            elif runtime_contract["ok"] and model_runtime_contract["ok"]:
                task_ref = request.task_ref or "task://agent-playground/validation"
                task_payload = PlaygroundFlowTestRequest(
                    endpoint_id=request.endpoint_id,
                    project_id=request.project_id,
                    question="이 Task의 SOP 단계, 선행 결과, 필요한 근거와 부족한 근거를 정리해줘.",
                    business_context="Agent Playground Flow별 SOP Task Context 검증",
                    task_ref=task_ref,
                    context_id=f"validation-{uuid.uuid4().hex[:12]}",
                    sop_ref="boi:public:sop:equipment-abnormal-response",
                    sop_stage="analyze",
                    event_ref="event:root_cause.analysis.requested.v1",
                    action_ref="action:langflow.equipment.stage_analysis",
                    prior_results=[
                        {
                            "ref": "action:sop.equipment.request_trend_history",
                            "status": "completed",
                            "summary": "Trend History 근거 확보",
                        }
                    ],
                    required_evidence=["trend_history", "raw_data", "alarm_context"],
                    missing_evidence=["raw_data"],
                    save_mode="preview",
                    title="SOP Task Context 검증",
                )
                validation_trace = f"flow-validation-{uuid.uuid4().hex}"
                run_token = self.pat_service.create_run_token(
                    principal,
                    action_key=f"agent-playground.validation.{flow_id}",
                    flow_id=flow_id,
                    trace_id=validation_trace,
                    scopes=["boi.read"],
                    ttl_seconds=180,
                )
                try:
                    task_result = self._run(
                        endpoint,
                        api_key,
                        flow_id,
                        task_payload,
                        run_token=str(run_token["token"]),
                    )
                finally:
                    self.pat_service.consume_run_token(str(run_token["token_id"]))
                task_contract = self._runtime_contract(task_result)
                task_payload_result = self._contract_payload(task_result)
                task_context = (
                    task_payload_result.get("task_context")
                    if isinstance(task_payload_result.get("task_context"), dict)
                    else {}
                )
                ontology_relationships = task_payload_result.get("ontology_relationships")
                task_fields = {
                    "task_context": task_context.get("profile") == "sop_task_execution",
                    "task_ref": task_context.get("task_ref") == task_payload.task_ref,
                    "sop_ref": task_context.get("sop_ref") == task_payload.sop_ref,
                    "sop_stage": task_context.get("sop_stage") == task_payload.sop_stage,
                    "event_ref": task_context.get("event_ref") == task_payload.event_ref,
                    "action_ref": task_context.get("action_ref") == task_payload.action_ref,
                    "prior_results": task_context.get("prior_results") == task_payload.prior_results,
                    "required_evidence": task_context.get("required_evidence") == task_payload.required_evidence,
                    "missing_evidence": task_context.get("missing_evidence") == task_payload.missing_evidence,
                    "ontology": isinstance(ontology_relationships, list) and bool(ontology_relationships),
                    "source_references": bool(task_contract["fields"]["source_references"]),
                }
                task_ok = task_contract["ok"] and all(task_fields.values())
                history.append(
                    {
                        "stage": "task_validated",
                        "status": "passed" if task_ok else "failed",
                        "checked_at": now_iso(),
                        "details": {**task_contract, "fields": task_fields},
                    }
                )
                if task_ok:
                    validation_status = "action_ready"
                    history.append(
                        {
                            "stage": "action_ready",
                            "status": "passed",
                            "checked_at": now_iso(),
                        }
                    )
                else:
                    failure_reason = "SOP Task Context, Ontology, or grounding contract is incomplete"
            else:
                failure_reason = (
                    "runtime output does not prove real model inference"
                    if structural.get("agent_kind") == "openai_compatible_model"
                    and not model_runtime_contract["ok"]
                    else "runtime output does not satisfy the grounding contract"
                )
        else:
            missing = ", ".join(structural["components"]["missing"])
            forbidden = ", ".join(structural["components"]["present_forbidden"])
            if missing:
                failure_reason = f"required BoI components are missing: {missing}"
            elif forbidden:
                failure_reason = (
                    "read-only validation profile forbids components: "
                    f"{forbidden}"
                )
            elif not structural["manifest_contract"]["ok"]:
                failed_fields = ", ".join(
                    key
                    for key, passed in structural["manifest_contract"]["fields"].items()
                    if not passed
                )
                failure_reason = f"Flow manifest contract mismatch: {failed_fields}"
            else:
                failure_reason = "secret scan failed"
        if validation_status == "blocked":
            history.append(
                {
                    "stage": "blocked",
                    "status": "failed",
                    "checked_at": now_iso(),
                    "reason": failure_reason,
                }
            )
        with self._lock:
            record = self._read(principal.employee_id)
            registry_item = self._upsert_flow_registry(
                record,
                {
                    "endpoint_id": request.endpoint_id,
                    "project_id": request.project_id,
                    "flow_id": flow_id,
                    "name": str(flow.get("name") or listed_flow.get("name") or ""),
                    "endpoint_name": str(flow.get("endpoint_name") or listed_flow.get("endpoint_name") or ""),
                    "artifact_version": artifact_version,
                    "artifact_checksum": checksum,
                    "validation_profile": validation_profile,
                    "input_contract": structural["input_contract"],
                    "output_contract": structural["output_contract"],
                    "validation_status": validation_status,
                    "validation_history": history,
                    "failure_reason": failure_reason,
                    "validated_at": now_iso(),
                },
            )
            for deployment in record.get("deployments") or []:
                if (
                    isinstance(deployment, dict)
                    and str(deployment.get("endpoint_id") or "") == request.endpoint_id
                    and str(deployment.get("project_id") or "") == request.project_id
                    and str(deployment.get("flow_id") or "") == flow_id
                ):
                    deployment["status"] = validation_status
                    deployment["validation_profile"] = validation_profile
                    deployment["input_contract"] = structural["input_contract"]
                    deployment["output_contract"] = structural["output_contract"]
                    deployment["artifact_checksum"] = checksum
                    deployment["validated_at"] = now_iso()
                    if failure_reason:
                        deployment["failure_reason"] = failure_reason
            self._write(principal.employee_id, record)
        return {
            "ok": validation_status == "action_ready",
            "endpoint_id": request.endpoint_id,
            "project_id": request.project_id,
            "flow_id": flow_id,
            "artifact_version": artifact_version,
            "artifact_checksum": checksum,
            "validation_status": validation_status,
            "validation_profile": validation_profile,
            "failure_reason": failure_reason,
            "history": history,
            "structural": structural,
            "runtime": runtime_result,
            "task": task_result,
            "registry": registry_item,
        }

    def deployment(self, principal: AuthIdentity, deployment_id: str) -> dict[str, Any]:
        record = self._read(principal.employee_id)
        for item in record.get("deployments") or []:
            if isinstance(item, dict) and str(item.get("deployment_id") or "") == deployment_id:
                return item
        raise HTTPException(status_code=404, detail="deployment not found")

    def action_draft_payload(self, principal: AuthIdentity, deployment_id: str) -> dict[str, Any]:
        require_role(principal, "boi.editor", "boi.action_invoker")
        deployment = self.deployment(principal, deployment_id)
        if str(deployment.get("status") or "") != "action_ready":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "flow_not_action_ready",
                    "message": "Flow별 구조·runtime·SOP Task·Ontology 검증을 먼저 통과해야 합니다.",
                    "validation_status": str(deployment.get("status") or "discovered"),
                    "failure_reason": str(deployment.get("failure_reason") or ""),
                },
            )
        source_assets = [
            item
            for item in deployment.get("source_assets") or []
            if isinstance(item, dict)
        ]
        current_sources = []
        for pinned in source_assets:
            current = self.agent_hub_asset(
                principal,
                str(pinned.get("asset_id") or ""),
            )["asset"]
            current_sources.append(
                {
                    "asset_id": str(pinned.get("asset_id") or ""),
                    "title": str(pinned.get("title") or ""),
                    "type": str(pinned.get("type") or ""),
                    "pinned_version": str(pinned.get("version") or ""),
                    "current_version": str(current.get("version") or ""),
                    "author": pinned.get("author") or {},
                    "update_available": (
                        str(current.get("metadata_checksum") or "")
                        != str(pinned.get("metadata_checksum") or "")
                    ),
                }
            )
        action_slug = re.sub(r"[^a-z0-9-]+", "-", str(deployment.get("endpoint_name") or "").lower()).strip("-")
        if not action_slug:
            action_slug = str(deployment["flow_id"]).lower()
        validation_profile = str(
            deployment.get("validation_profile") or "boi_knowledge_draft"
        )
        flow_name = str(deployment.get("flow_name") or "").strip() or (
            str(source_assets[0].get("title") or "").strip()
            if source_assets
            else CANONICAL_FLOW_NAME
        )
        profile_contracts: dict[str, dict[str, Any]] = {
            "generic_action": {
                "title": f"{flow_name} Action",
                "business_goal": "승인된 Agent Hub Flow의 기능을 BoI에서 재사용합니다.",
                "description": (
                    "Agent Hub 승인 자산을 개인 Langflow에 배포하고 exact Flow로 "
                    "고정한 일반 Action 등록 초안입니다."
                ),
                "inputs": deployment.get("input_contract") or ["question"],
                "outputs": deployment.get("output_contract") or ["answer"],
                "default_mode": "execute",
                "risk_level": "medium",
                "approval_required": True,
            },
            "boi_knowledge": {
                "title": f"{flow_name} Action",
                "business_goal": "BoI Wiki·Ontology 지식을 근거와 함께 조회합니다.",
                "description": (
                    "승인된 Agent Hub Flow를 BoI 지식 조회 전용 Action으로 연결하는 "
                    "등록 초안입니다."
                ),
                "inputs": deployment.get("input_contract") or [
                    "question",
                    "business_context",
                    "task_ref",
                    "page_ref",
                    "sop_ref",
                    "sop_stage",
                    "event_ref",
                    "action_ref",
                    "prior_results",
                    "required_evidence",
                    "missing_evidence",
                ],
                "outputs": deployment.get("output_contract") or [
                    "answer",
                    "task_context",
                    "source_references",
                    "ontology_relationships",
                    "grounding_status",
                    "provenance",
                ],
                "default_mode": "preview",
                "risk_level": "low",
                "approval_required": False,
            },
            "boi_knowledge_draft": {
                "title": f"{flow_name} Action",
                "business_goal": "BoI Wiki 지식을 근거와 함께 조회하고 결과를 개인 초안으로 저장합니다.",
                "description": (
                    "승인된 Agent Hub Flow를 Wiki·Ontology 조회와 개인 초안 저장 "
                    "Action으로 연결하는 등록 초안입니다."
                ),
                "inputs": deployment.get("input_contract") or [
                    "question",
                    "business_context",
                    "task_ref",
                    "page_ref",
                    "sop_ref",
                    "sop_stage",
                    "event_ref",
                    "action_ref",
                    "prior_results",
                    "required_evidence",
                    "missing_evidence",
                    "save_mode",
                    "title",
                ],
                "outputs": deployment.get("output_contract") or [
                    "answer",
                    "task_context",
                    "source_references",
                    "ontology_relationships",
                    "grounding_status",
                    "draft_reference",
                    "wiki_url",
                    "provenance",
                ],
                "default_mode": "preview",
                "risk_level": "low",
                "approval_required": False,
            },
        }
        profile_contract = profile_contracts.get(
            validation_profile,
            profile_contracts["boi_knowledge_draft"],
        )
        generic_field_schema = {
            field_name: {
                "type": (
                    "array"
                    if field_name
                    in {"prior_results", "required_evidence", "missing_evidence"}
                    else "string"
                ),
                **({"required": True} if field_name == "question" else {}),
            }
            for field_name in profile_contract["inputs"]
        }
        if validation_profile == "boi_knowledge_draft":
            generic_field_schema["save_mode"] = {
                "type": "string",
                "enum": ["preview", "private_draft"],
                "default": "preview",
            }
        output_schema = {
            field_name: {
                "type": (
                    "array"
                    if field_name in {"source_references", "ontology_relationships"}
                    else "object"
                    if field_name in {"task_context", "provenance"}
                    else "string"
                )
            }
            for field_name in profile_contract["outputs"]
        }
        connector_config = {
            "endpoint_connection_id": deployment["endpoint_id"],
            "deployment_id": deployment["deployment_id"],
            "project_id": deployment["project_id"],
            "flow_id": deployment["flow_id"],
            "endpoint_name": deployment["endpoint_name"],
            "endpoint": f"/api/v1/run/{deployment['flow_id']}",
            "artifact_version": deployment["asset_version"],
            "artifact_checksum": deployment["artifact_checksum"],
            "default_mode": profile_contract["default_mode"],
            "connection_source": "agent_playground",
            "source_assets": current_sources,
            "source_origin": str(deployment.get("origin") or "agent_playground"),
            "validation_profile": validation_profile,
        }
        action_contract = {
            "schema_version": "boi.action-contract.v1",
            "profile": validation_profile,
            "business_goal": profile_contract["business_goal"],
            "inputs": {
                "fields": list(profile_contract["inputs"]),
                "schema": generic_field_schema,
            },
            "outputs": {
                "fields": list(profile_contract["outputs"]),
                "schema": output_schema,
            },
        }
        connector_binding = {
            "schema_version": "boi.connector-binding.v1",
            "kind": "langflow",
            "adapter": "agent_playground.langflow",
            "operation": "run_flow",
            "execution_mode": "gateway",
            "deployment_reference": {
                "endpoint_connection_id": deployment["endpoint_id"],
                "deployment_id": deployment["deployment_id"],
                "project_id": deployment["project_id"],
                "flow_id": deployment["flow_id"],
                "artifact_version": deployment["asset_version"],
                "artifact_checksum": deployment["artifact_checksum"],
            },
            "config": connector_config,
        }
        return {
            "entry_kind": "action",
            "scope": "private",
            "title": profile_contract["title"],
            "business_goal": profile_contract["business_goal"],
            "description": profile_contract["description"],
            "input_fields": profile_contract["inputs"],
            "output_fields": profile_contract["outputs"],
            "execution_mode": "gateway",
            "connector_kind": "langflow",
            "connector_config": connector_config,
            "action_contract": action_contract,
            "connector_binding": connector_binding,
            "input_schema": generic_field_schema,
            "output_schema": output_schema,
            "sample_payload": (
                {"question": "이 Flow의 기능을 실행해줘."}
                if validation_profile == "generic_action"
                else {
                    "question": "관련 Wiki 근거를 찾아 요약해줘.",
                    **(
                        {"save_mode": "preview"}
                        if validation_profile == "boi_knowledge_draft"
                        else {}
                    ),
                }
            ),
            "result_mapping": (
                {"answer": "answer"}
                if validation_profile == "generic_action"
                else {
                    "source_refs": "source_references",
                    "status": "grounding_status",
                    **(
                        {"doc_ref": "draft_reference"}
                        if validation_profile == "boi_knowledge_draft"
                        else {}
                    ),
                }
            ),
            "risk_policy": {
                "default_mode": profile_contract["default_mode"],
                "private_draft_requires_explicit_mode": (
                    validation_profile == "boi_knowledge_draft"
                ),
                "run_token_required_for_boi_action": True,
                "generic_action_requires_registration_review": (
                    validation_profile == "generic_action"
                ),
            },
            "action_key": f"agent-playground.{principal.employee_id}.{action_slug}.{deployment['flow_id']}",
            "risk_level": profile_contract["risk_level"],
            "approval_required": profile_contract["approval_required"],
            "user_confirmed": False,
        }

    def rotate_credential(
        self,
        principal: AuthIdentity,
        request: PlaygroundRotateCredentialRequest,
    ) -> dict[str, Any]:
        require_role(principal, "boi.viewer")
        with self._lock:
            record = self._read(principal.employee_id)
            connection = self._endpoint(record, request.endpoint_id)
            endpoint_id = str(connection.get("endpoint_id") or "")
            endpoint = str(connection.get("base_url") or connection.get("endpoint") or "")
            api_key = self._api_key(record, endpoint_id)
            wiki_credentials = (
                record.get("wiki_credentials")
                if isinstance(record.get("wiki_credentials"), dict)
                else {}
            )
            current_credential = wiki_credentials.get(endpoint_id) or (
                record.get("wiki_credential")
                if isinstance(record.get("wiki_credential"), dict)
                else {}
            )
            previous_token_id = str((current_credential or {}).get("token_id") or "")
            issued = self.pat_service.create(
                principal,
                TokenCreateRequest(
                    name="Agent Playground BoI knowledge (rotated)",
                    scopes=(
                        ["boi.read", "boi.draft"]
                        if principal.is_admin or "boi.editor" in principal.roles
                        else ["boi.read"]
                    ),
                    expires_in_days=None,
                ),
            )
            try:
                self._put_credential(endpoint, api_key, str(issued["token"]))
            except Exception:
                self.pat_service.revoke(principal, str(issued["token_id"]))
                raise
            if previous_token_id:
                self.pat_service.revoke(principal, previous_token_id)
            credential = {
                "token_id": issued["token_id"],
                "variable_name": BOI_PAT_VARIABLE_NAME,
                "expires_at": None,
                "linked_at": now_iso(),
                "rotated_at": now_iso(),
                "rotation_reason": request.reason,
            }
            wiki_credentials[endpoint_id] = credential
            record["wiki_credentials"] = wiki_credentials
            setup = self._endpoint_setup(record, endpoint_id)
            setup["wiki_credential"] = credential
            setup["last_error"] = ""
            if endpoint_id == str(record.get("default_endpoint_id") or ""):
                record["wiki_credential"] = credential
            self._write(principal.employee_id, record)
        return {
            "ok": True,
            "credential": {
                "token_id": issued["token_id"],
                "variable_name": BOI_PAT_VARIABLE_NAME,
                "expires_at": None,
                "endpoint_id": endpoint_id,
            },
        }

    def state(self, principal: AuthIdentity, *, live: bool = True) -> dict[str, Any]:
        require_role(principal, "boi.viewer")
        record = self._read(principal.employee_id)
        setup_before = json.dumps(record.get("endpoint_setups"), ensure_ascii=False, sort_keys=True, default=str)
        setups = self._endpoint_setups(record)
        setup_after = json.dumps(setups, ensure_ascii=False, sort_keys=True, default=str)
        if setup_before != setup_after:
            self._write(principal.employee_id, record)
        endpoint_payload = self.endpoints(principal, live=live)
        endpoints = endpoint_payload["endpoints"]
        default_endpoint_id = str(endpoint_payload.get("default_endpoint_id") or "")
        connection = next(
            (item for item in endpoints if str(item.get("endpoint_id") or "") == default_endpoint_id),
            {},
        )
        selected_setup = setups.get(default_endpoint_id) or {}
        public_setups: dict[str, dict[str, Any]] = {}
        for endpoint_id, setup in setups.items():
            setup_endpoint = next(
                (
                    item
                    for item in endpoints
                    if str(item.get("endpoint_id") or "") == endpoint_id
                ),
                {},
            )
            public_setup = self._public_setup(
                setup,
                self._setup_readiness(setup_endpoint, setup),
            )
            public_setup["onboarding"] = self._onboarding(
                principal,
                setup_endpoint,
                setup,
            )
            public_setups[endpoint_id] = public_setup
        onboarding = self._onboarding(principal, connection, selected_setup)
        live_error = str(connection.get("last_error") or "")
        deployments = [item for item in record.get("deployments") or [] if isinstance(item, dict)]
        hub_adoptions = []
        for item in record.get("hub_adoptions") or []:
            if not isinstance(item, dict):
                continue
            snapshot = item.get("snapshot") if isinstance(item.get("snapshot"), dict) else {}
            hub_adoptions.append(
                {
                    key: value
                    for key, value in item.items()
                    if key != "snapshot"
                }
                | {
                    "snapshot": {
                        "flow_count": len(snapshot),
                        "flow_ids": sorted(str(value) for value in snapshot),
                    }
                }
            )
        latest_deployment = deployments[-1] if deployments else None
        action = record.get("action") if isinstance(record.get("action"), dict) else None
        project = (
            selected_setup.get("project")
            if isinstance(selected_setup.get("project"), dict)
            else record.get("project") if isinstance(record.get("project"), dict) else None
        )
        flow = (
            selected_setup.get("canonical_flow")
            if isinstance(selected_setup.get("canonical_flow"), dict)
            else record.get("canonical_flow")
            if isinstance(record.get("canonical_flow"), dict)
            else None
        )
        selected_credential = (
            selected_setup.get("wiki_credential")
            if isinstance(selected_setup.get("wiki_credential"), dict)
            else {}
        )
        external_url = str(
            os.getenv("LANGFLOW_EXTERNAL_URL")
            or connection.get("base_url")
            or connection.get("endpoint")
            or ""
        ).rstrip("/")
        settings_url = f"{external_url}/settings/api-keys" if external_url else ""
        deploy_url = str(
            os.getenv("LANGFLOW_DEPLOY_URL")
            or connection.get("base_url")
            or connection.get("endpoint")
            or ""
        ).rstrip("/")
        return {
            "ok": True,
            "identity": {
                "employee_id": principal.employee_id,
                "display_name": principal.display_name,
                "roles": principal.roles,
                "teams": principal.teams,
                "auth_source": principal.auth_source,
            },
            "connection": {
                "status": str(
                    connection.get("status")
                    or ("error" if live_error else "connected" if connection else "not_connected")
                ),
                **connection,
                "error": live_error,
            },
            "endpoints": endpoints,
            "default_endpoint_id": default_endpoint_id,
            "endpoint_limit": MAX_ENDPOINTS,
            "endpoint_setups": public_setups,
            "onboarding": {
                **onboarding,
                "langflow_settings_url": settings_url,
                "langflow_external_url": external_url,
                "langflow_deploy_url": deploy_url,
                "agent_hub_url": os.getenv("AGENT_HUB_EXTERNAL_URL", "http://localhost:3000"),
                "user_guide_url": (
                    "/docs/boi:public:boi-wiki-manual:langflow:"
                    "agent-playground-onboarding"
                ),
            },
            "project": project,
            "flow": flow,
            "flows": [item for item in record.get("flow_registry") or [] if isinstance(item, dict)],
            "deployments": deployments,
            "hub_adoptions": hub_adoptions,
            "wiki": {
                "status": "connected" if selected_credential else "not_connected",
                "credential_variable": BOI_PAT_VARIABLE_NAME if selected_credential else "",
                "pat_expires_at": selected_credential.get("expires_at"),
            },
            "last_test": record.get("last_test"),
            "agent_hub": {
                "status": "deployed" if latest_deployment else "not_deployed",
                "latest_deployment": latest_deployment,
                "catalog_available": bool(
                    os.getenv("AGENT_HUB_API_URL")
                    or os.getenv("AGENT_HUB_EXTERNAL_URL")
                ),
                "manual_registration": {
                    "endpoint": connection.get("base_url") or connection.get("endpoint") or "",
                    "project": (project or {}).get("name") or f"{PROJECT_PREFIX}{principal.employee_id}",
                    "credential_label": "Playground 연결 키",
                },
            },
            "action": action or {"status": "not_connected"},
            "capabilities": {
                "can_manage_connection": principal.is_admin or "boi.viewer" in principal.roles,
                "can_edit": principal.is_admin or "boi.editor" in principal.roles,
                "can_execute_action": principal.is_admin or "boi.action_invoker" in principal.roles,
                "can_save_private_draft": principal.is_admin or "boi.editor" in principal.roles,
            },
            "canonical_asset": {
                "name": CANONICAL_FLOW_NAME,
                "endpoint_name": CANONICAL_FLOW_ENDPOINT,
                "version": CANONICAL_FLOW_VERSION,
                "checksum": self._canonical_checksum(),
                "bundle_version": COMPONENT_BUNDLE_VERSION,
                "bundle_mode": COMPONENT_BUNDLE_MODE,
            },
            "model_agent_asset": {
                "name": MODEL_AGENT_FLOW_NAME,
                "endpoint_name": MODEL_AGENT_FLOW_ENDPOINT,
                "model_variable": "BOI_AGENT_EXAMPLE_MODEL",
                "base_url_variable": "BOI_LLM_BASE_URL",
                "credential_variable": BOI_LLM_API_KEY_VARIABLE_NAME,
            },
            "security": {
                "api_key_encrypted": True,
                "encryption_key_configured": self.encryption_configured,
                "pat_stored_by_boi": "hash_only",
                "secrets_in_export": False,
                "langflow_runtime_modified": False,
                "component_bundle_mode": COMPONENT_BUNDLE_MODE,
            },
        }

    def record_action_draft(self, principal: AuthIdentity, deployment_id: str, draft: dict[str, Any]) -> None:
        record = self._read(principal.employee_id)
        deployment = self.deployment(principal, deployment_id)
        draft_id = str(draft.get("draft_id") or "")
        record["action"] = {
            "status": str(draft.get("status") or "draft"),
            "draft_id": draft_id,
            "draft_url": f"/actions/drafts/{draft_id}" if draft_id else "",
            "deployment_id": deployment_id,
            "linked_at": now_iso(),
        }
        for item in record.get("deployments") or []:
            if isinstance(item, dict) and str(item.get("deployment_id") or "") == deployment_id:
                item["status"] = "action_linked"
                item["action_draft_id"] = draft_id
                item["action_draft_status"] = str(draft.get("status") or "draft")
                item["action_linked_at"] = now_iso()
        for item in record.get("flow_registry") or []:
            if (
                isinstance(item, dict)
                and str(item.get("endpoint_id") or "") == str(deployment.get("endpoint_id") or "")
                and str(item.get("project_id") or "") == str(deployment.get("project_id") or "")
                and str(item.get("flow_id") or "") == str(deployment.get("flow_id") or "")
            ):
                item["validation_status"] = "action_linked"
                item["action_draft_id"] = draft_id
                item["action_draft_status"] = str(draft.get("status") or "draft")
        self._write(principal.employee_id, record)

    def sync_action_draft_status(self, employee_id: str, draft: dict[str, Any]) -> None:
        """Mirror registration state only when its immutable deployment reference matches."""

        draft_id = str(draft.get("draft_id") or "")
        if not draft_id:
            return
        request = draft.get("request") if isinstance(draft.get("request"), dict) else {}
        connector = request.get("connector_config") if isinstance(request.get("connector_config"), dict) else {}
        deployment_id = str(connector.get("deployment_id") or "")
        flow_id = str(connector.get("flow_id") or "")
        if str(connector.get("connection_source") or "") != "agent_playground" or not deployment_id or not flow_id:
            return
        record = self._read(employee_id)
        deployment = next(
            (
                item
                for item in record.get("deployments") or []
                if isinstance(item, dict)
                and str(item.get("deployment_id") or "") == deployment_id
            ),
            None,
        )
        if deployment is None:
            return
        exact_fields = {
            "endpoint_connection_id": "endpoint_id",
            "project_id": "project_id",
            "flow_id": "flow_id",
            "artifact_version": "asset_version",
            "artifact_checksum": "artifact_checksum",
        }
        if any(
            str(connector.get(connector_key) or "") != str(deployment.get(deployment_key) or "")
            for connector_key, deployment_key in exact_fields.items()
        ):
            raise HTTPException(status_code=409, detail="Action draft deployment reference does not match")
        status = str(draft.get("status") or "draft")
        validation = draft.get("validation") if isinstance(draft.get("validation"), dict) else {}
        action = record.get("action") if isinstance(record.get("action"), dict) else {}
        if str(action.get("draft_id") or "") == draft_id:
            action["status"] = status
            action["validation"] = {
                "valid": bool(validation.get("valid")),
                "checks": list(validation.get("checks") or []),
            }
            action["catalog_applied"] = bool(draft.get("catalog_applied"))
            action["updated_at"] = now_iso()
            record["action"] = action
        for collection_name in ("deployments", "flow_registry"):
            for item in record.get(collection_name) or []:
                if not isinstance(item, dict) or str(item.get("action_draft_id") or "") != draft_id:
                    continue
                item["action_draft_status"] = status
                item["action_draft_valid"] = bool(validation.get("valid"))
                item["action_catalog_applied"] = bool(draft.get("catalog_applied"))
                if collection_name == "deployments":
                    item["status"] = "action_linked"
                else:
                    item["validation_status"] = "action_linked"
        self._write(employee_id, record)

    def execution_connection(self, deployment_id: str, flow_id: str) -> dict[str, str]:
        """Resolve the Action owner's endpoint without trusting caller-supplied ownership."""

        users_root = self.root / "users"
        for path in sorted(users_root.glob("*.json")) if users_root.exists() else []:
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            deployment = next(
                (
                    item
                    for item in record.get("deployments") or []
                    if isinstance(item, dict)
                    and str(item.get("deployment_id") or "") == deployment_id
                ),
                None,
            )
            if deployment is None:
                continue
            if str(deployment.get("flow_id") or "") != flow_id:
                raise HTTPException(status_code=409, detail="deployment and Flow ID do not match")
            if str(deployment.get("status") or "") not in {"action_ready", "action_linked"}:
                raise HTTPException(status_code=409, detail="deployment is not ready for Action execution")
            endpoint_id = str(deployment.get("endpoint_id") or "")
            connection = self._endpoint(record, endpoint_id)
            return {
                "endpoint": str(connection.get("base_url") or connection.get("endpoint") or ""),
                "api_key": self._api_key(record, endpoint_id),
                "langflow_user_id": str(connection.get("langflow_user_id") or ""),
                "owner_employee_id": str(record.get("employee_id") or ""),
                "endpoint_id": endpoint_id,
                "project_id": str(deployment.get("project_id") or ""),
            }
        raise HTTPException(status_code=404, detail="Agent Playground deployment not found")

    def artifact_bundle(
        self,
        principal: AuthIdentity,
        flow_id: str,
        *,
        endpoint_id: str = "",
        project_id: str = "",
    ) -> bytes:
        require_role(principal, "boi.viewer")
        record = self._read(principal.employee_id)
        canonical = record.get("canonical_flow") if isinstance(record.get("canonical_flow"), dict) else {}
        selected_endpoint_id = str(endpoint_id or canonical.get("endpoint_id") or record.get("default_endpoint_id") or "")
        selected_project_id = str(project_id or canonical.get("project_id") or (record.get("project") or {}).get("id") or "")
        _, live_flow, _ = self._live_flow(
            principal,
            selected_endpoint_id,
            selected_project_id,
            flow_id,
        )
        serialized_flow = json.dumps(live_flow, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        if any(pattern.search(serialized_flow.decode("utf-8", errors="ignore")) for pattern in SECRET_PATTERNS):
            raise HTTPException(status_code=500, detail="secret-like value found in Flow export")
        safe_flow_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(live_flow.get("name") or flow_id)).strip("-")
        artifact_name = str(live_flow.get("name") or flow_id)
        artifact_endpoint_name = str(live_flow.get("endpoint_name") or "")
        canonical_path = self.repo_root / "langflow" / "flows" / "boi_wiki_agent_loop.json"
        canonical_checksum = self._canonical_checksum() if canonical_path.exists() else ""
        model_agent_path = (
            self.repo_root
            / "langflow"
            / "flows"
            / "boi_wiki_agent_loop_model_agent.json"
        )
        model_agent_checksum = self._model_agent_checksum() if model_agent_path.exists() else ""
        registry_item = next(
            (
                item
                for item in record.get("flow_registry") or []
                if isinstance(item, dict)
                and str(item.get("endpoint_id") or "") == selected_endpoint_id
                and str(item.get("project_id") or "") == selected_project_id
                and str(item.get("flow_id") or "") == flow_id
            ),
            {},
        )
        # Agent Hub uses the uploaded asset title as the deployed Flow name.
        # Identify the canonical artifact by its recorded identity and checksum,
        # not by that mutable display name, so exports stay generator-derived.
        if (
            canonical_path.exists()
            and str(registry_item.get("artifact_checksum") or "") == canonical_checksum
        ):
            canonical_export = json.loads(canonical_path.read_text(encoding="utf-8"))
            serialized_flow = canonical_path.read_bytes()
            safe_flow_name = "boi_wiki_agent_loop"
            artifact_name = str(canonical_export.get("name") or CANONICAL_FLOW_NAME)
            artifact_endpoint_name = str(
                canonical_export.get("endpoint_name") or CANONICAL_FLOW_ENDPOINT
            )
        elif (
            model_agent_path.exists()
            and str(registry_item.get("artifact_checksum") or "") == model_agent_checksum
        ):
            model_export = json.loads(model_agent_path.read_text(encoding="utf-8"))
            serialized_flow = model_agent_path.read_bytes()
            safe_flow_name = "boi_wiki_agent_loop_model_agent"
            artifact_name = str(model_export.get("name") or MODEL_AGENT_FLOW_NAME)
            artifact_endpoint_name = str(
                model_export.get("endpoint_name") or MODEL_AGENT_FLOW_ENDPOINT
            )
        component_root = self.repo_root / "langflow" / "custom_components" / "boi"
        static_paths = [
            *sorted(component_root.glob("*.py")),
            self.repo_root / "langflow" / "flows" / "boi_wiki_agent_loop_model_agent.json",
            self.repo_root / "langflow" / "compatibility-manifest.json",
            self.repo_root / "langflow" / "agent_hub" / "README.md",
        ]
        missing = [str(path.relative_to(self.repo_root)) for path in static_paths if not path.exists()]
        if missing:
            raise HTTPException(status_code=503, detail={"message": "Agent Hub artifact is incomplete", "missing": missing})
        checksum = hashlib.sha256(serialized_flow).hexdigest()
        serialized_flow_text = serialized_flow.decode("utf-8", errors="ignore")
        model_agent_artifact = "BoIModelAgent" in serialized_flow_text
        manifest = {
            "schema_version": "boi-agent-hub-validation-v2",
            "name": artifact_name,
            "endpoint_name": artifact_endpoint_name,
            "version": CANONICAL_FLOW_VERSION,
            "artifact_checksum": checksum,
            "source_identity": {
                "endpoint_id": selected_endpoint_id,
                "project_id": selected_project_id,
                "flow_id": flow_id,
            },
            "langflow": {
                "minimum": "1.11.0",
                "maximum_exclusive": "1.12.0",
                "run_api": "/api/v1/run/{flow_id}",
            },
            "components": [
                "BoIWikiKnowledge",
                "BoIModelAgent" if model_agent_artifact else "BoIAgentSlot",
                "BoIWikiSave",
            ],
            "credential_variables": (
                [
                    BOI_PAT_VARIABLE_NAME,
                    BOI_LLM_API_KEY_VARIABLE_NAME,
                ]
                if model_agent_artifact
                else [BOI_PAT_VARIABLE_NAME]
            ),
            "configuration_variables": (
                ["BOI_LLM_BASE_URL", "BOI_AGENT_EXAMPLE_MODEL"]
                if model_agent_artifact
                else []
            ),
            "agent_kind": (
                "openai_compatible_model" if model_agent_artifact else "contract_shell"
            ),
            "request_variables": ["BOI_RUN_TOKEN"],
            "inputs": [
                "question",
                "business_context",
                "task_ref",
                "page_ref",
                "context_id",
                "sop_ref",
                "sop_stage",
                "event_ref",
                "action_ref",
                "prior_results",
                "required_evidence",
                "missing_evidence",
                "save_mode",
                "title",
            ],
            "outputs": [
                "answer",
                "task_context",
                "source_references",
                "ontology_relationships",
                "grounding_status",
                "draft_reference",
                "wiki_url",
                "provenance",
            ],
            "defaults": {"save_mode": "preview"},
            "secret_policy": {
                "raw_credentials_in_export": False,
                "agent_hub_receives_boi_pat": False,
            },
        }
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f"langflow/flows/{safe_flow_name}.json", serialized_flow)
            archive.writestr(
                "langflow/agent_hub/flow.manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
            )
            for path in static_paths:
                content = path.read_bytes()
                text = content.decode("utf-8", errors="ignore")
                if any(pattern.search(text) for pattern in SECRET_PATTERNS):
                    raise HTTPException(status_code=500, detail=f"secret-like value found in artifact: {path.name}")
                archive.writestr(path.relative_to(self.repo_root).as_posix(), content)
        return stream.getvalue()
