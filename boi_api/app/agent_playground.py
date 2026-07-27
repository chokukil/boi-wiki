from __future__ import annotations

import ast
import asyncio
import base64
import copy
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
from urllib.parse import urlencode, urlsplit, urlunsplit

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
UNIVERSAL_MCP_FLOW_NAME = "BoI Universal Simulation MCP"
UNIVERSAL_MCP_FLOW_ENDPOINT = "boi-universal-simulation-mcp"
UNIVERSAL_MCP_FLOW_VERSION = "1.0.0"
UNIVERSAL_MCP_TOOL_NAME = "boi_universal_simulate"
UNIVERSAL_MCP_TOOL_DESCRIPTION = (
    "Wiki·Ontology와 선택한 Task 맥락을 사용해 실제 시스템을 호출하지 않는 "
    "업무 처리 시뮬레이션과 근거가 포함된 초안 후보를 만듭니다."
)
COMPONENT_BUNDLE_VERSION = "1.2.0"
COMPONENT_BUNDLE_MODE = "read_only_extension"
REQUIRED_BUNDLE_COMPONENTS = (
    "BoIWikiKnowledge",
    "BoIWikiSave",
    "BoIModelAgent",
    "BoIUniversalSimulationMCPAgent",
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


def public_langflow_endpoint(value: str) -> str:
    """Keep container-only hostnames out of browser-facing responses."""

    candidate = str(value or "").rstrip("/")
    parsed = urlsplit(candidate)
    if str(parsed.hostname or "").lower() != "host.docker.internal":
        return candidate
    configured = str(
        os.getenv("LANGFLOW_EXTERNAL_URL")
        or os.getenv("LANGFLOW_DEPLOY_URL")
        or ""
    ).rstrip("/")
    if configured.startswith(("http://", "https://")):
        return configured
    return candidate


def runtime_langflow_endpoint(value: str) -> str:
    """Resolve a browser-visible Langflow URL to the server-side API origin."""

    normalized = normalize_langflow_endpoint(value)
    external = str(os.getenv("LANGFLOW_EXTERNAL_URL") or "").strip()
    deploy = str(os.getenv("LANGFLOW_DEPLOY_URL") or "").strip()
    if not external or not deploy:
        return normalized
    if normalized == normalize_langflow_endpoint(external):
        return normalize_langflow_endpoint(deploy)
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


class PlaygroundMCPUpdateRequest(BaseModel):
    enabled: bool = True
    action_name: str = Field(default=UNIVERSAL_MCP_TOOL_NAME, min_length=1, max_length=100)
    action_description: str = Field(
        default=UNIVERSAL_MCP_TOOL_DESCRIPTION,
        min_length=1,
        max_length=1000,
    )
    auth_type: Literal["apikey"] = "apikey"


class PlaygroundMCPTestRequest(BaseModel):
    question: str = Field(
        default="현재 업무의 근거와 예상 처리 결과를 시뮬레이션해줘.",
        min_length=1,
        max_length=8000,
    )
    task_ref: str = Field(default="", max_length=1000)
    save_mode: Literal["preview", "private_draft"] = "preview"


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


class PlaygroundHubAdoptionComposeRequest(BaseModel):
    flow_id: str = Field(min_length=1, max_length=500)
    component_asset_id: str = Field(min_length=1, max_length=500)
    replace_agent_slot: Literal[True] = True


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
    PROJECT_MCP_PATH = "/api/v1/mcp/project/{project_id}"

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

    def update_flow(
        self,
        endpoint: str,
        api_key: str,
        flow_id: str,
        flow: dict[str, Any],
    ) -> dict[str, Any]:
        payload = self._transport(
            "PATCH",
            endpoint,
            f"/api/v1/flows/{flow_id}",
            api_key,
            expected={200},
            json={
                key: flow[key]
                for key in (
                    "name",
                    "description",
                    "endpoint_name",
                    "data",
                    "folder_id",
                    "project_id",
                )
                if key in flow
            },
            timeout=120,
        ).json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="Langflow Flow update returned an invalid response")
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
        endpoint_name: str = "",
        mcp_enabled: bool | None = None,
        action_name: str = "",
        action_description: str = "",
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "name": name,
            "description": description,
            "data": data,
            "folder_id": project_id,
            "project_id": project_id,
        }
        if endpoint_name:
            body["endpoint_name"] = endpoint_name
        if mcp_enabled is not None:
            body["mcp_enabled"] = mcp_enabled
        if action_name:
            body["action_name"] = action_name
        if action_description:
            body["action_description"] = action_description
        payload = self._transport(
            "POST",
            endpoint,
            self.FLOWS_PATH,
            api_key,
            expected={200, 201},
            json=body,
            timeout=120,
        ).json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="Langflow create did not return a Flow")
        return payload

    def project_mcp(self, endpoint: str, api_key: str, project_id: str) -> dict[str, Any]:
        payload = self._transport(
            "GET",
            endpoint,
            self.PROJECT_MCP_PATH.format(project_id=project_id),
            api_key,
        ).json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="Langflow MCP settings returned an invalid response")
        return payload

    def update_project_mcp(
        self,
        endpoint: str,
        api_key: str,
        project_id: str,
        *,
        settings: list[dict[str, Any]],
        auth_type: str = "apikey",
    ) -> dict[str, Any]:
        payload = self._transport(
            "PATCH",
            endpoint,
            self.PROJECT_MCP_PATH.format(project_id=project_id),
            api_key,
            json={
                "settings": settings,
                "auth_settings": {"auth_type": auth_type},
            },
        ).json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="Langflow MCP update returned an invalid response")
        return payload

    def run(
        self,
        endpoint: str,
        api_key: str,
        flow_id: str,
        *,
        input_value: str,
        run_token: str = "",
        audience: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        request_headers: dict[str, str] = {}
        if run_token:
            request_headers["X-LANGFLOW-GLOBAL-VAR-BOI_RUN_TOKEN"] = run_token
        for key, value in (audience or {}).items():
            normalized = str(value or "").strip()
            if normalized:
                request_headers[f"X-LANGFLOW-GLOBAL-VAR-{key}"] = normalized
        payload = self._transport(
            "POST",
            endpoint,
            self.RUN_PATH.format(flow_id=flow_id),
            api_key,
            headers=request_headers,
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
        base_url = public_langflow_endpoint(
            str(public.get("base_url") or public.get("endpoint") or "")
        )
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
            recommended_flow = (
                setup.get("recommended_flow")
                if isinstance(setup.get("recommended_flow"), dict)
                else {}
            )
            recommended_smoke = (
                setup.get("recommended_smoke")
                if isinstance(setup.get("recommended_smoke"), dict)
                else {}
            )
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
            if recommended_flow:
                setup["recommended_flow"] = recommended_flow
            if recommended_smoke:
                setup["recommended_smoke"] = recommended_smoke
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
        recommended_flow = (
            setup.get("recommended_flow")
            if isinstance(setup.get("recommended_flow"), dict)
            else {}
        )
        recommended_smoke = (
            setup.get("recommended_smoke")
            if isinstance(setup.get("recommended_smoke"), dict)
            else {}
        )
        bundle = setup.get("bundle") if isinstance(setup.get("bundle"), dict) else {}
        canonical_checksum = self._canonical_checksum()
        recommended_checksum = self._recommended_flow_checksum()
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
            "recommended_flow": (
                bool(recommended_flow.get("id"))
                and str(recommended_flow.get("version") or "")
                == UNIVERSAL_MCP_FLOW_VERSION
                and str(recommended_flow.get("checksum") or "") == recommended_checksum
            ),
            "recommended_smoke": (
                str(recommended_smoke.get("status") or "") == "passed"
                and str(recommended_smoke.get("flow_id") or "")
                == str(recommended_flow.get("id") or "")
            ),
        }
        return {"ready": all(checks.values()), "checks": checks}

    @staticmethod
    def _public_setup(setup: dict[str, Any], readiness: dict[str, Any]) -> dict[str, Any]:
        project = setup.get("project") if isinstance(setup.get("project"), dict) else {}
        flow = setup.get("canonical_flow") if isinstance(setup.get("canonical_flow"), dict) else {}
        smoke = setup.get("smoke") if isinstance(setup.get("smoke"), dict) else {}
        recommended_flow = (
            setup.get("recommended_flow")
            if isinstance(setup.get("recommended_flow"), dict)
            else {}
        )
        recommended_smoke = (
            setup.get("recommended_smoke")
            if isinstance(setup.get("recommended_smoke"), dict)
            else {}
        )
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
            "recommended_flow": {
                "id": str(recommended_flow.get("id") or ""),
                "name": str(recommended_flow.get("name") or ""),
                "endpoint_name": str(recommended_flow.get("endpoint_name") or ""),
                "version": str(recommended_flow.get("version") or ""),
                "checksum": str(recommended_flow.get("checksum") or ""),
                "flow_url": str(recommended_flow.get("flow_url") or ""),
                "project_id": str(recommended_flow.get("project_id") or ""),
                "mcp_enabled": bool(recommended_flow.get("mcp_enabled")),
                "mcp_tool": str(recommended_flow.get("mcp_tool") or ""),
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
            "recommended_smoke": {
                "status": str(recommended_smoke.get("status") or "not_run"),
                "checked_at": str(recommended_smoke.get("checked_at") or ""),
                "flow_id": str(recommended_smoke.get("flow_id") or ""),
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
        flow_ready = (
            checks["canonical_flow"]
            and checks["preview_smoke"]
            and checks["recommended_flow"]
            and checks["recommended_smoke"]
        )
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
                    "추천 Flow와 기준 Flow의 preview smoke를 통과했습니다."
                    if flow_ready
                    else "추천 Flow를 설치하고 Wiki·Ontology 기반 preview를 확인합니다."
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
        component_contract = (
            item.get("component_contract")
            if isinstance(item.get("component_contract"), dict)
            else {}
        )
        if component_contract:
            safe["component_contract"] = {
                "schema_version": str(
                    component_contract.get("schema_version")
                    or component_contract.get("contract_id")
                    or ""
                ),
                "inputs": [
                    str(value) for value in component_contract.get("inputs") or []
                ],
                "outputs": [
                    str(value) for value in component_contract.get("outputs") or []
                ],
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
        endpoint = runtime_langflow_endpoint(request.base_url)
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
        base_url = runtime_langflow_endpoint(request.base_url)
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
            candidate_url = runtime_langflow_endpoint(
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
        drift_updates: list[dict[str, str]] = []
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
            try:
                flow_detail = self.langflow.flow(endpoint, api_key, flow_id)
                live_checksum = self._runtime_flow_checksum(flow_detail)
                graph_health = self._graph_health(flow_detail)
                flow_summary = self.flow_display_snapshot(flow_detail)
                source_assets = list(
                    deployment.get("source_assets")
                    or registry.get("source_assets")
                    or []
                )
                component_graph = self._adopted_component_graph_state(
                    flow_detail,
                    source_assets,
                )
                registered_checksum = str(
                    registry.get("validated_checksum")
                    or deployment.get("validated_checksum")
                    or registry.get("artifact_checksum")
                    or deployment_checksum
                )
                checksum_state = (
                    "matched"
                    if registered_checksum and live_checksum == registered_checksum
                    else "drifted"
                    if registered_checksum
                    else "unknown"
                )
            except HTTPException:
                live_checksum = ""
                flow_summary = {
                    "name": str(item.get("name") or ""),
                    "description": "",
                    "endpoint_name": str(item.get("endpoint_name") or ""),
                    "node_count": 0,
                    "edge_count": 0,
                    "nodes": [],
                    "edges": [],
                    "end_to_end_reachable": False,
                    "connected_component_ids": [],
                }
                graph_health = {
                    "end_to_end_reachable": False,
                    "connected_component_ids": [],
                    "disconnected_nodes": [],
                }
                source_assets = list(
                    deployment.get("source_assets")
                    or registry.get("source_assets")
                    or []
                )
                component_graph = {
                    "items": [],
                    "all_deployed": False,
                    "all_connected": False,
                    "disconnected_component_ids": [],
                    "missing_component_ids": [
                        str(asset.get("asset_id") or "")
                        for asset in source_assets
                        if isinstance(asset, dict)
                        and str(asset.get("type") or "") == "py"
                    ],
                }
                checksum_state = "unknown"
            if checksum_state == "drifted":
                validation_status = "blocked"
                for stored in (registry, deployment):
                    if stored:
                        stored["validation_status" if stored is registry else "status"] = "blocked"
                        stored["checksum_state"] = "drifted"
                        stored["live_checksum"] = live_checksum
                        stored["failure_reason"] = "flow_checksum_drift"
                drift_updates.append(
                    {
                        "endpoint_id": endpoint_id,
                        "project_id": project_id,
                        "flow_id": flow_id,
                        "live_checksum": live_checksum,
                    }
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
                    "live_checksum": live_checksum,
                    "checksum_state": checksum_state,
                    "graph_health": graph_health,
                    "connected_component_ids": graph_health.get(
                        "connected_component_ids"
                    ) or [],
                    "disconnected_nodes": graph_health.get("disconnected_nodes") or [],
                    "component_graph": component_graph,
                    "executed_component_ids": list(
                        registry.get("executed_component_ids")
                        or deployment.get("executed_component_ids")
                        or []
                    ),
                    "mcp_enabled": bool(
                        registry.get("mcp_enabled")
                        or item.get("mcp_enabled")
                    ),
                    "mcp_tool": str(
                        registry.get("mcp_tool")
                        or item.get("action_name")
                        or ""
                    ),
                    "mcp_status": str(
                        registry.get("mcp_status")
                        or (
                            "ready"
                            if registry.get("mcp_enabled")
                            or item.get("mcp_enabled")
                            else "not_configured"
                        )
                    ),
                    "source_assets": source_assets,
                    "adoption_id": str(
                        deployment.get("adoption_id")
                        or registry.get("adoption_id")
                        or ""
                    ),
                    "deployment_id": str(
                        registry.get("deployment_id")
                        or deployment.get("deployment_id")
                        or ""
                    ),
                    "action_draft_id": str(
                        registry.get("action_draft_id")
                        or deployment.get("action_draft_id")
                        or ""
                    ),
                    "action_key": str(
                        registry.get("action_key")
                        or deployment.get("action_key")
                        or ""
                    ),
                    "action_draft_status": str(
                        registry.get("action_draft_status")
                        or deployment.get("action_draft_status")
                        or ""
                    ),
                    "action_catalog_applied": bool(
                        registry.get("action_catalog_applied")
                        or deployment.get("action_catalog_applied")
                    ),
                    "flow_url": f"{public_langflow_endpoint(endpoint)}/flow/{flow_id}",
                    "flow_summary": flow_summary,
                }
            )
        if drift_updates:
            with self._lock:
                current = self._read(principal.employee_id)
                for update in drift_updates:
                    for collection_name in ("flow_registry", "deployments"):
                        for stored in current.get(collection_name) or []:
                            if (
                                not isinstance(stored, dict)
                                or str(stored.get("endpoint_id") or "")
                                != update["endpoint_id"]
                                or str(stored.get("project_id") or "")
                                != update["project_id"]
                                or str(stored.get("flow_id") or "")
                                != update["flow_id"]
                            ):
                                continue
                            stored[
                                "validation_status"
                                if collection_name == "flow_registry"
                                else "status"
                            ] = "blocked"
                            stored["checksum_state"] = "drifted"
                            stored["live_checksum"] = update["live_checksum"]
                            stored["failure_reason"] = "flow_checksum_drift"
                self._write(principal.employee_id, current)
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

    @staticmethod
    def _node_id(node: Any) -> str:
        return str(node.get("id") or "") if isinstance(node, dict) else str(node or "")

    @staticmethod
    def _node_component_identity(node: dict[str, Any]) -> set[str]:
        data = node.get("data") if isinstance(node.get("data"), dict) else {}
        component = data.get("node") if isinstance(data.get("node"), dict) else {}
        values = {
            node.get("id"),
            node.get("type"),
            data.get("type"),
            data.get("display_name"),
            component.get("name"),
            component.get("display_name"),
        }
        return {str(value).strip() for value in values if str(value or "").strip()}

    @staticmethod
    def _component_contract(asset: dict[str, Any]) -> dict[str, Any]:
        metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
        contract = (
            asset.get("component_contract")
            if isinstance(asset.get("component_contract"), dict)
            else metadata.get("component_contract")
            if isinstance(metadata.get("component_contract"), dict)
            else {}
        )
        contract_id = str(
            contract.get("schema_version")
            or contract.get("contract_id")
            or asset.get("component_contract_id")
            or ""
        )
        return {
            "contract_id": contract_id,
            "inputs": [str(value) for value in contract.get("inputs") or []],
            "outputs": [str(value) for value in contract.get("outputs") or []],
        }

    @staticmethod
    def _node_component_contract(node: dict[str, Any]) -> dict[str, Any]:
        data = node.get("data") if isinstance(node.get("data"), dict) else {}
        component = data.get("node") if isinstance(data.get("node"), dict) else {}
        metadata = (
            component.get("metadata")
            if isinstance(component.get("metadata"), dict)
            else {}
        )
        for candidate in (
            data.get("component_contract"),
            metadata.get("component_contract"),
        ):
            if isinstance(candidate, dict):
                return {
                    "contract_id": str(
                        candidate.get("schema_version")
                        or candidate.get("contract_id")
                        or ""
                    ),
                    "inputs": [
                        str(value) for value in candidate.get("inputs") or []
                    ],
                    "outputs": [
                        str(value) for value in candidate.get("outputs") or []
                    ],
                }
        template = (
            component.get("template")
            if isinstance(component.get("template"), dict)
            else {}
        )
        source = ""
        for key in ("code", "_code", "component_code"):
            field = template.get(key)
            if isinstance(field, dict) and isinstance(field.get("value"), str):
                source = str(field["value"])
                break
        if not source:
            return {"contract_id": "", "inputs": [], "outputs": []}
        try:
            module = ast.parse(source)
        except SyntaxError:
            return {"contract_id": "", "inputs": [], "outputs": []}
        for class_node in (
            item for item in module.body if isinstance(item, ast.ClassDef)
        ):
            for statement in class_node.body:
                if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
                    continue
                targets = (
                    statement.targets
                    if isinstance(statement, ast.Assign)
                    else [statement.target]
                )
                if not any(
                    isinstance(target, ast.Name)
                    and target.id in {"component_contract", "COMPONENT_CONTRACT"}
                    for target in targets
                ):
                    continue
                try:
                    value = ast.literal_eval(statement.value)
                except (ValueError, TypeError):
                    continue
                if isinstance(value, dict):
                    return {
                        "contract_id": str(
                            value.get("schema_version")
                            or value.get("contract_id")
                            or ""
                        ),
                        "inputs": [
                            str(item) for item in value.get("inputs") or []
                        ],
                        "outputs": [
                            str(item) for item in value.get("outputs") or []
                        ],
                    }
        return {"contract_id": "", "inputs": [], "outputs": []}

    @classmethod
    def _component_nodes_for_asset(
        cls,
        nodes: list[dict[str, Any]],
        *,
        asset_title: str,
        required_contract: dict[str, Any],
    ) -> list[dict[str, Any]]:
        title_key = re.sub(r"[^a-z0-9]+", "", asset_title.lower())
        matches: list[tuple[int, dict[str, Any]]] = []
        for node in nodes:
            normalized = {
                re.sub(r"[^a-z0-9]+", "", value.lower())
                for value in cls._node_component_identity(node)
            }
            match_lengths = [
                len(value)
                for value in normalized
                if (
                    len(value) >= 8
                    and title_key
                    and (title_key in value or value in title_key)
                )
            ]
            if match_lengths:
                matches.append((max(match_lengths), node))
        if matches:
            # Agent Hub titles commonly append a version or validation run ID.
            # Prefer the most specific identity so "Incompatible Agent Slot
            # 20260727" does not also select the shorter built-in Agent Slot.
            best_match_length = max(score for score, _ in matches)
            return [node for score, node in matches if score == best_match_length]
        return [
            node
            for node in nodes
            if cls._node_component_contract(node) == required_contract
        ]

    @classmethod
    def _graph_health(cls, flow: dict[str, Any]) -> dict[str, Any]:
        data = flow.get("data") if isinstance(flow.get("data"), dict) else {}
        nodes = [item for item in data.get("nodes") or [] if isinstance(item, dict)]
        edges = [item for item in data.get("edges") or [] if isinstance(item, dict)]
        node_ids = {cls._node_id(node) for node in nodes if cls._node_id(node)}
        adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
        reverse: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
        for edge in edges:
            source = str(edge.get("source") or "")
            target = str(edge.get("target") or "")
            if source in node_ids and target in node_ids:
                adjacency[source].add(target)
                reverse[target].add(source)
        starts = {
            cls._node_id(node)
            for node in nodes
            if any("ChatInput" in value or value == "Chat Input" for value in cls._node_component_identity(node))
        }
        ends = {
            cls._node_id(node)
            for node in nodes
            if any("ChatOutput" in value or value == "Chat Output" for value in cls._node_component_identity(node))
        }

        def walk(seeds: set[str], graph: dict[str, set[str]]) -> set[str]:
            visited: set[str] = set()
            pending = list(seeds)
            while pending:
                current = pending.pop()
                if current in visited:
                    continue
                visited.add(current)
                pending.extend(graph.get(current) or [])
            return visited

        forward = walk(starts, adjacency)
        backward = walk(ends, reverse)
        execution_path = forward & backward
        disconnected = sorted(node_ids - execution_path)
        connected_component_ids: list[str] = []
        for node in nodes:
            if cls._node_id(node) not in execution_path:
                continue
            data_value = node.get("data") if isinstance(node.get("data"), dict) else {}
            component = (
                data_value.get("node")
                if isinstance(data_value.get("node"), dict)
                else {}
            )
            metadata = (
                component.get("metadata")
                if isinstance(component.get("metadata"), dict)
                else {}
            )
            component_id = str(
                metadata.get("component_asset_id")
                or data_value.get("component_asset_id")
                or ""
            )
            if component_id:
                connected_component_ids.append(component_id)
        return {
            "end_to_end_reachable": bool(starts and ends and ends.intersection(forward)),
            "start_nodes": sorted(starts),
            "output_nodes": sorted(ends),
            "execution_path_nodes": sorted(execution_path),
            "connected_component_ids": sorted(set(connected_component_ids)),
            "disconnected_nodes": disconnected,
        }

    @classmethod
    def flow_display_snapshot(cls, flow: dict[str, Any]) -> dict[str, Any]:
        """Return a secret-free, read-only Flow graph for BoI user interfaces."""

        data = flow.get("data") if isinstance(flow.get("data"), dict) else {}
        raw_nodes = [
            item for item in data.get("nodes") or [] if isinstance(item, dict)
        ][:80]
        raw_edges = [
            item for item in data.get("edges") or [] if isinstance(item, dict)
        ][:160]
        health = cls._graph_health(flow)
        execution_path = {
            str(item) for item in health.get("execution_path_nodes") or []
        }

        def safe_text(value: Any, *, limit: int = 160) -> str:
            text = re.sub(r"\s+", " ", str(value or "")).strip()[:limit]
            return (
                "[비밀값 제거됨]"
                if any(pattern.search(text) for pattern in SECRET_PATTERNS)
                else text
            )

        nodes: list[dict[str, Any]] = []
        node_ids: set[str] = set()
        for node in raw_nodes:
            node_id = cls._node_id(node)
            if not node_id:
                continue
            node_ids.add(node_id)
            node_key = hashlib.sha256(node_id.encode("utf-8")).hexdigest()[:12]
            node_data = (
                node.get("data") if isinstance(node.get("data"), dict) else {}
            )
            component = (
                node_data.get("node")
                if isinstance(node_data.get("node"), dict)
                else {}
            )
            metadata = (
                component.get("metadata")
                if isinstance(component.get("metadata"), dict)
                else {}
            )
            label = safe_text(
                node_data.get("display_name")
                or component.get("display_name")
                or component.get("name")
                or node_data.get("type")
                or node_id
            )
            component_kind = safe_text(
                component.get("name")
                or node_data.get("type")
                or node.get("type")
                or "component"
            )
            identities = " ".join(cls._node_component_identity(node)).lower()
            role = (
                "input"
                if "chatinput" in identities or "chat input" in identities
                else "output"
                if "chatoutput" in identities or "chat output" in identities
                else "knowledge"
                if "boiwikiknowledge" in identities
                else "save"
                if "boiwikisave" in identities
                else "agent"
                if "agent" in identities
                else "component"
            )
            nodes.append(
                {
                    "node_key": node_key,
                    "label": label,
                    "component_kind": component_kind,
                    "component_id": safe_text(
                        metadata.get("component_asset_id")
                        or node_data.get("component_asset_id")
                        or "",
                        limit=120,
                    ),
                    "role": role,
                    "on_execution_path": node_id in execution_path,
                }
            )

        node_key_by_id = {
            cls._node_id(node): hashlib.sha256(
                cls._node_id(node).encode("utf-8")
            ).hexdigest()[:12]
            for node in raw_nodes
            if cls._node_id(node) in node_ids
        }
        edges = [
            {
                "source": node_key_by_id[source],
                "target": node_key_by_id[target],
            }
            for edge in raw_edges
            if (source := str(edge.get("source") or "")) in node_key_by_id
            and (target := str(edge.get("target") or "")) in node_key_by_id
        ]
        # Langflow does not promise that graph nodes are serialized in execution
        # order.  Use a stable topological order for the read-only UI and fall
        # back to the source order for disconnected or cyclic nodes.
        order_index = {
            str(node.get("node_key") or ""): index
            for index, node in enumerate(nodes)
        }
        outgoing: dict[str, list[str]] = {
            str(node.get("node_key") or ""): [] for node in nodes
        }
        indegree: dict[str, int] = {
            str(node.get("node_key") or ""): 0 for node in nodes
        }
        for edge in edges:
            source = str(edge.get("source") or "")
            target = str(edge.get("target") or "")
            if source in outgoing and target in indegree:
                outgoing[source].append(target)
                indegree[target] += 1
        ready = sorted(
            (key for key, degree in indegree.items() if degree == 0),
            key=lambda key: order_index.get(key, len(order_index)),
        )
        ordered_keys: list[str] = []
        while ready:
            current = ready.pop(0)
            ordered_keys.append(current)
            for target in sorted(
                outgoing.get(current) or [],
                key=lambda key: order_index.get(key, len(order_index)),
            ):
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.append(target)
                    ready.sort(key=lambda key: order_index.get(key, len(order_index)))
        ordered_key_set = set(ordered_keys)
        ordered_keys.extend(
            key
            for key in order_index
            if key not in ordered_key_set
        )
        node_by_key = {
            str(node.get("node_key") or ""): node for node in nodes
        }
        nodes = [node_by_key[key] for key in ordered_keys if key in node_by_key]
        return {
            "name": safe_text(flow.get("name") or "Langflow Flow"),
            "description": safe_text(flow.get("description") or "", limit=500),
            "endpoint_name": safe_text(flow.get("endpoint_name") or "", limit=120),
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges,
            "end_to_end_reachable": bool(health.get("end_to_end_reachable")),
            "connected_component_ids": [
                safe_text(item, limit=120)
                for item in health.get("connected_component_ids") or []
            ][:40],
        }

    @staticmethod
    def _edge_handles(
        *,
        source_id: str,
        source_type: str,
        source_name: str,
        source_types: list[str],
        target_id: str,
        target_name: str,
        target_types: list[str],
    ) -> dict[str, Any]:
        source_handle = {
            "dataType": source_type,
            "id": source_id,
            "name": source_name,
            "output_types": source_types,
        }
        target_handle = {
            "fieldName": target_name,
            "id": target_id,
            "inputTypes": target_types,
            "type": "other",
        }

        def encoded(value: dict[str, Any]) -> str:
            return json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
            ).replace('"', "œ")

        source_encoded = encoded(source_handle)
        target_encoded = encoded(target_handle)
        return {
            "animated": False,
            "className": "",
            "data": {
                "sourceHandle": source_handle,
                "targetHandle": target_handle,
            },
            "id": (
                f"reactflow__edge-{source_id}{source_encoded}-"
                f"{target_id}{target_encoded}"
            ),
            "selected": False,
            "source": source_id,
            "sourceHandle": source_encoded,
            "target": target_id,
            "targetHandle": target_encoded,
        }

    def compose_hub_adoption(
        self,
        principal: AuthIdentity,
        adoption_id: str,
        request: PlaygroundHubAdoptionComposeRequest,
    ) -> dict[str, Any]:
        require_role(principal, "boi.editor")
        record = self._read(principal.employee_id)
        adoption = self._hub_adoption(record, adoption_id)
        if str(adoption.get("flow_id") or "") != request.flow_id:
            raise HTTPException(status_code=409, detail="adoption and Flow ID do not match")
        asset = next(
            (
                item
                for item in adoption.get("source_assets") or []
                if isinstance(item, dict)
                and str(item.get("asset_id") or "") == request.component_asset_id
            ),
            None,
        )
        if asset is None or str(asset.get("type") or "") != "py":
            raise HTTPException(status_code=404, detail="component asset is not part of this adoption")
        connection, _, api_key = self._live_flow(
            principal,
            str(adoption.get("endpoint_id") or ""),
            str(adoption.get("project_id") or ""),
            request.flow_id,
        )
        endpoint = str(connection.get("base_url") or connection.get("endpoint") or "")
        canvas_url = (
            f"{public_langflow_endpoint(endpoint)}/flow/{request.flow_id}"
        )
        flow = self.langflow.flow(endpoint, api_key, request.flow_id)
        before_checksum = self._runtime_flow_checksum(flow)
        catalog_contract = self._component_contract(asset)
        required_contract = {
            "contract_id": "boi.agent-slot.v1",
            "inputs": ["agent_context"],
            "outputs": ["agent_result"],
        }
        if catalog_contract["contract_id"] and catalog_contract != required_contract:
            return {
                "ok": False,
                "status": "manual_required",
                "reason": "component_contract_incompatible",
                "required_contract": required_contract,
                "actual_contract": catalog_contract,
                "contract_source": "agent_hub_catalog",
                "langflow_canvas_url": canvas_url,
            }
        data = copy.deepcopy(flow.get("data") if isinstance(flow.get("data"), dict) else {})
        nodes = [item for item in data.get("nodes") or [] if isinstance(item, dict)]
        edges = [item for item in data.get("edges") or [] if isinstance(item, dict)]
        slot_nodes = [
            node
            for node in nodes
            if any(
                value.startswith("BoIAgentSlot")
                or value.startswith("BoIUniversalSimulationMCPAgent")
                or value == "agent_slot"
                for value in self._node_component_identity(node)
            )
        ]
        component_nodes = self._component_nodes_for_asset(
            nodes,
            asset_title=str(asset.get("title") or ""),
            required_contract=required_contract,
        )
        if len(slot_nodes) != 1 or len(component_nodes) != 1:
            return {
                "ok": False,
                "status": "manual_required",
                "reason": (
                    "agent_slot_not_unique"
                    if len(slot_nodes) != 1
                    else "component_node_not_unique"
                ),
                "slot_count": len(slot_nodes),
                "component_node_count": len(component_nodes),
                "langflow_canvas_url": canvas_url,
            }
        slot = slot_nodes[0]
        component = component_nodes[0]
        deployed_contract = self._node_component_contract(component)
        contract = (
            catalog_contract
            if catalog_contract["contract_id"]
            else deployed_contract
        )
        if (
            contract["contract_id"] != "boi.agent-slot.v1"
            or contract["inputs"] != ["agent_context"]
            or contract["outputs"] != ["agent_result"]
        ):
            return {
                "ok": False,
                "status": "manual_required",
                "reason": "component_contract_incompatible",
                "required_contract": required_contract,
                "actual_contract": contract,
                "contract_source": (
                    "agent_hub_catalog"
                    if catalog_contract["contract_id"]
                    else "deployed_component_source"
                    if deployed_contract["contract_id"]
                    else "missing"
                ),
                "langflow_canvas_url": canvas_url,
            }
        slot_id = self._node_id(slot)
        component_id = self._node_id(component)
        inbound = [edge for edge in edges if str(edge.get("target") or "") == slot_id]
        outbound = [edge for edge in edges if str(edge.get("source") or "") == slot_id]
        if len(inbound) != 1 or len(outbound) != 1:
            return {
                "ok": False,
                "status": "manual_required",
                "reason": "agent_slot_edge_ambiguous",
                "inbound_edge_count": len(inbound),
                "outbound_edge_count": len(outbound),
                "langflow_canvas_url": canvas_url,
            }
        component_data = component.get("data") if isinstance(component.get("data"), dict) else {}
        component_node = (
            component_data.get("node")
            if isinstance(component_data.get("node"), dict)
            else {}
        )
        template = (
            component_node.get("template")
            if isinstance(component_node.get("template"), dict)
            else {}
        )
        outputs = [
            item
            for item in component_node.get("outputs") or []
            if isinstance(item, dict)
        ]
        input_spec = template.get("agent_context") if isinstance(template.get("agent_context"), dict) else {}
        output_spec = next(
            (item for item in outputs if str(item.get("name") or "") == "agent_result"),
            None,
        )
        if not input_spec or output_spec is None:
            return {
                "ok": False,
                "status": "manual_required",
                "reason": "component_ports_do_not_match_contract",
                "langflow_canvas_url": canvas_url,
            }
        component_node.setdefault("metadata", {})["component_asset_id"] = request.component_asset_id
        component_node["metadata"]["component_contract"] = "boi.agent-slot.v1"
        component_data["component_asset_id"] = request.component_asset_id
        provenance_input = template.get("component_asset_id")
        if isinstance(provenance_input, dict):
            provenance_input["value"] = request.component_asset_id
        source_to_component = self._edge_handles(
            source_id=str(inbound[0].get("source") or ""),
            source_type=str(
                ((inbound[0].get("data") or {}).get("sourceHandle") or {}).get("dataType")
                or ""
            ),
            source_name=str(
                ((inbound[0].get("data") or {}).get("sourceHandle") or {}).get("name")
                or "knowledge"
            ),
            source_types=list(
                ((inbound[0].get("data") or {}).get("sourceHandle") or {}).get("output_types")
                or ["Data", "JSON"]
            ),
            target_id=component_id,
            target_name="agent_context",
            target_types=list(input_spec.get("input_types") or ["Data", "JSON"]),
        )
        component_to_target = self._edge_handles(
            source_id=component_id,
            source_type=str(component_data.get("type") or component_node.get("name") or "Component"),
            source_name="agent_result",
            source_types=list(output_spec.get("types") or ["Data", "JSON"]),
            target_id=str(outbound[0].get("target") or ""),
            target_name=str(
                ((outbound[0].get("data") or {}).get("targetHandle") or {}).get("fieldName")
                or "agent_result"
            ),
            target_types=list(
                ((outbound[0].get("data") or {}).get("targetHandle") or {}).get("inputTypes")
                or ["Data", "JSON"]
            ),
        )
        data["nodes"] = [node for node in nodes if self._node_id(node) != slot_id]
        data["edges"] = [
            edge
            for edge in edges
            if str(edge.get("source") or "") != slot_id
            and str(edge.get("target") or "") != slot_id
            and str(edge.get("source") or "") != component_id
            and str(edge.get("target") or "") != component_id
        ] + [source_to_component, component_to_target]
        snapshot_id = f"flow-snapshot-{uuid.uuid4().hex[:16]}"
        updated = self.langflow.update_flow(
            endpoint,
            api_key,
            request.flow_id,
            {**flow, "data": data},
        )
        after_checksum = self._runtime_flow_checksum(updated)
        graph_health = self._graph_health(updated)
        if not graph_health["end_to_end_reachable"] or request.component_asset_id not in graph_health["connected_component_ids"]:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "component_composition_graph_invalid",
                    "graph_health": graph_health,
                },
            )
        with self._lock:
            current = self._read(principal.employee_id)
            current.setdefault("composition_snapshots", []).append(
                {
                    "snapshot_id": snapshot_id,
                    "adoption_id": adoption_id,
                    "flow_id": request.flow_id,
                    "checksum": before_checksum,
                    "flow": flow,
                    "created_at": now_iso(),
                }
            )
            current_adoption = self._hub_adoption(current, adoption_id)
            current_adoption.update(
                {
                    "composition_status": "connected",
                    "connected_component_ids": [request.component_asset_id],
                    "runtime_checksum": after_checksum,
                    "rollback_snapshot_id": snapshot_id,
                    "composed_at": now_iso(),
                }
            )
            for deployment in current.get("deployments") or []:
                if (
                    isinstance(deployment, dict)
                    and str(deployment.get("deployment_id") or "")
                    == str(current_adoption.get("deployment_id") or "")
                ):
                    deployment["artifact_checksum"] = after_checksum
                    deployment["runtime_checksum"] = after_checksum
                    deployment["validated_checksum"] = after_checksum
                    deployment["live_checksum"] = after_checksum
                    deployment["checksum_state"] = "matched"
                    deployment["status"] = "discovered"
                    deployment["connected_component_ids"] = [request.component_asset_id]
                    deployment["graph_health"] = graph_health
            for registry_item in current.get("flow_registry") or []:
                if (
                    isinstance(registry_item, dict)
                    and str(registry_item.get("endpoint_id") or "")
                    == str(current_adoption.get("endpoint_id") or "")
                    and str(registry_item.get("project_id") or "")
                    == str(current_adoption.get("project_id") or "")
                    and str(registry_item.get("flow_id") or "") == request.flow_id
                ):
                    registry_item["artifact_checksum"] = after_checksum
                    registry_item["validated_checksum"] = after_checksum
                    registry_item["live_checksum"] = after_checksum
                    registry_item["checksum_state"] = "matched"
                    registry_item["validation_status"] = "discovered"
                    registry_item["connected_component_ids"] = [
                        request.component_asset_id
                    ]
                    registry_item["graph_health"] = graph_health
                    registry_item.pop("failure_reason", None)
            self._write(principal.employee_id, current)
        return {
            "ok": True,
            "status": "connected",
            "previous_checksum": before_checksum,
            "live_checksum": after_checksum,
            "connected_nodes": {
                "removed_agent_slot": slot_id,
                "component": component_id,
            },
            "connected_edges": [
                source_to_component["id"],
                component_to_target["id"],
            ],
            "graph_health": graph_health,
            "rollback_snapshot": {
                "snapshot_id": snapshot_id,
                "checksum": before_checksum,
            },
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
            endpoint_name=str(exported.get("endpoint_name") or CANONICAL_FLOW_ENDPOINT),
        )

    def _recommended_flow(
        self,
        endpoint: str,
        api_key: str,
        project_id: str,
    ) -> dict[str, Any] | None:
        candidates = [
            item
            for item in self._flows(endpoint, api_key)
            if (
                str(item.get("endpoint_name") or "") == UNIVERSAL_MCP_FLOW_ENDPOINT
                or str(item.get("name") or "") == UNIVERSAL_MCP_FLOW_NAME
            )
            and str(item.get("folder_id") or item.get("project_id") or "") == project_id
        ]
        candidates.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        return candidates[0] if candidates else None

    def _install_recommended_flow(
        self,
        endpoint: str,
        api_key: str,
        project_id: str,
        *,
        force_upload: bool = False,
    ) -> dict[str, Any]:
        existing = None if force_upload else self._recommended_flow(endpoint, api_key, project_id)
        if existing:
            return existing
        flow_path = (
            self.repo_root
            / "langflow"
            / "flows"
            / "boi_universal_simulation_mcp.json"
        )
        if not flow_path.exists():
            raise HTTPException(
                status_code=503,
                detail="Universal Simulation MCP Flow artifact is missing",
            )
        exported = json.loads(flow_path.read_text(encoding="utf-8"))
        flow_data = exported.get("data") if isinstance(exported.get("data"), dict) else exported
        return self.langflow.create_flow(
            endpoint,
            api_key,
            name=str(exported.get("name") or UNIVERSAL_MCP_FLOW_NAME),
            description=str(exported.get("description") or ""),
            data=flow_data,
            project_id=project_id,
            endpoint_name=str(
                exported.get("endpoint_name") or UNIVERSAL_MCP_FLOW_ENDPOINT
            ),
            mcp_enabled=True,
            action_name=str(exported.get("action_name") or UNIVERSAL_MCP_TOOL_NAME),
            action_description=str(
                exported.get("action_description")
                or UNIVERSAL_MCP_TOOL_DESCRIPTION
            ),
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

    def _recommended_flow_checksum(self) -> str:
        flow_path = (
            self.repo_root
            / "langflow"
            / "flows"
            / "boi_universal_simulation_mcp.json"
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
        audience: dict[str, str] | None = None,
        trace_id: str = "",
        execution_id: str = "",
    ) -> dict[str, Any]:
        resolved_trace_id = trace_id or f"playground-{uuid.uuid4().hex}"
        resolved_execution_id = execution_id or f"exec-{uuid.uuid4().hex}"
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
                "trace_id": resolved_trace_id,
                "execution_id": resolved_execution_id,
            },
            ensure_ascii=False,
        )
        result = self.langflow.run(
            endpoint,
            api_key,
            flow_ref,
            input_value=input_value,
            run_token=run_token,
            audience=audience,
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
                canonical_live_flow = self.langflow.flow(
                    endpoint,
                    api_key,
                    str(flow.get("id") or flow_ref),
                )
                canonical_live_checksum = self._runtime_flow_checksum(
                    canonical_live_flow
                )
                canonical_flow = {
                    "id": str(flow.get("id") or ""),
                    "name": str(flow.get("name") or CANONICAL_FLOW_NAME),
                    "endpoint_name": str(flow.get("endpoint_name") or CANONICAL_FLOW_ENDPOINT),
                    "version": CANONICAL_FLOW_VERSION,
                    "checksum": canonical_checksum,
                    "validated_checksum": canonical_live_checksum,
                    "live_checksum": canonical_live_checksum,
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

                recommended_flow_live = self._install_recommended_flow(
                    endpoint,
                    api_key,
                    project_record["id"],
                )
                recommended_ref = str(
                    recommended_flow_live.get("id")
                    or recommended_flow_live.get("endpoint_name")
                    or UNIVERSAL_MCP_FLOW_ENDPOINT
                )
                recommended_smoke_request = PlaygroundFlowTestRequest(
                    endpoint_id=endpoint_id,
                    project_id=project_record["id"],
                    question=(
                        "현재 요청을 처리하기 전에 확인할 Wiki·Ontology 근거와 "
                        "예상 처리 결과를 시뮬레이션해줘."
                    ),
                    save_mode="preview",
                    title="Universal Simulation MCP 온보딩 확인",
                )
                try:
                    recommended_smoke_result = self._run(
                        endpoint,
                        api_key,
                        recommended_ref,
                        recommended_smoke_request,
                    )
                except HTTPException as exc:
                    if not self._flow_reinstall_required(exc):
                        raise
                    recommended_flow_live = self._install_recommended_flow(
                        endpoint,
                        api_key,
                        project_record["id"],
                        force_upload=True,
                    )
                    recommended_ref = str(
                        recommended_flow_live.get("id")
                        or recommended_flow_live.get("endpoint_name")
                        or UNIVERSAL_MCP_FLOW_ENDPOINT
                    )
                    recommended_smoke_result = self._run(
                        endpoint,
                        api_key,
                        recommended_ref,
                        recommended_smoke_request,
                    )
                recommended_live_flow = self.langflow.flow(
                    endpoint,
                    api_key,
                    str(recommended_flow_live.get("id") or recommended_ref),
                )
                recommended_live_checksum = self._runtime_flow_checksum(
                    recommended_live_flow
                )
                recommended_flow = {
                    "id": str(recommended_flow_live.get("id") or ""),
                    "name": str(
                        recommended_flow_live.get("name")
                        or UNIVERSAL_MCP_FLOW_NAME
                    ),
                    "endpoint_name": str(
                        recommended_flow_live.get("endpoint_name")
                        or UNIVERSAL_MCP_FLOW_ENDPOINT
                    ),
                    "version": UNIVERSAL_MCP_FLOW_VERSION,
                    "checksum": self._recommended_flow_checksum(),
                    "validated_checksum": recommended_live_checksum,
                    "live_checksum": recommended_live_checksum,
                    "flow_url": f"{endpoint}/flow/{recommended_ref}",
                    "endpoint_id": endpoint_id,
                    "project_id": project_record["id"],
                    "mcp_enabled": True,
                    "mcp_tool": UNIVERSAL_MCP_TOOL_NAME,
                }
                recommended_smoke_record = {
                    "status": "passed",
                    "checked_at": now_iso(),
                    "flow_id": recommended_flow["id"],
                    "session_id": str(
                        recommended_smoke_result.get("session_id") or ""
                    ),
                    "mode": "preview",
                }
                setup.update(
                    {
                        "project": project_record,
                        "canonical_flow": canonical_flow,
                        "smoke": smoke_record,
                        "recommended_flow": recommended_flow,
                        "recommended_smoke": recommended_smoke_record,
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
                        "validated_checksum": canonical_live_checksum,
                        "live_checksum": canonical_live_checksum,
                        "checksum_state": "matched",
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
                self._upsert_flow_registry(
                    record,
                    {
                        "endpoint_id": endpoint_id,
                        "project_id": project_record["id"],
                        "flow_id": recommended_flow["id"],
                        "name": recommended_flow["name"],
                        "endpoint_name": recommended_flow["endpoint_name"],
                        "artifact_version": UNIVERSAL_MCP_FLOW_VERSION,
                        "artifact_checksum": recommended_flow["checksum"],
                        "validated_checksum": recommended_live_checksum,
                        "live_checksum": recommended_live_checksum,
                        "checksum_state": "matched",
                        "validation_status": "runtime_validated",
                        "mcp_enabled": True,
                        "mcp_tool": UNIVERSAL_MCP_TOOL_NAME,
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
                    "flow_id": recommended_flow["id"],
                    "session_id": recommended_smoke_record["session_id"],
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
        run_token: dict[str, object] | None = None
        trace_id = f"playground-{uuid.uuid4().hex}"
        execution_id = f"exec-{uuid.uuid4().hex}"
        audience = {
            "BOI_ACTION_KEY": "agent-playground-test",
            "BOI_DEPLOYMENT_ID": "agent-playground-preview",
            "BOI_ENDPOINT_ID": endpoint_id,
            "BOI_PROJECT_ID": project_id,
            "BOI_FLOW_ID": flow_id,
            "BOI_TRACE_ID": trace_id,
            "BOI_EXECUTION_ID": execution_id,
        }
        if request.save_mode == "private_draft":
            run_token = self.pat_service.create_run_token(
                principal,
                action_key="agent-playground-test",
                deployment_id="agent-playground-preview",
                endpoint_id=endpoint_id,
                project_id=project_id,
                flow_id=flow_id,
                trace_id=trace_id,
                execution_id=execution_id,
                allowed_capabilities=["boi.search", "boi.get", "knowledge.draft"],
                scopes=["boi.read", "boi.draft"],
                ttl_seconds=180,
            )
        try:
            result = self._run(
                endpoint,
                api_key,
                flow_id,
                request,
                run_token=str((run_token or {}).get("token") or ""),
                audience=audience,
                trace_id=trace_id,
                execution_id=execution_id,
            )
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
        finally:
            if run_token:
                self.pat_service.consume_run_token(str(run_token["token_id"]))
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

    @staticmethod
    def _mcp_streamable_url(endpoint: str, project_id: str) -> str:
        public_base = public_langflow_endpoint(
            str(os.getenv("LANGFLOW_EXTERNAL_URL") or endpoint)
        ).rstrip("/")
        return (
            f"{public_base}/api/v1/mcp/project/{project_id}/streamable"
        )

    def mcp_settings(
        self,
        principal: AuthIdentity,
        endpoint_id: str,
        project_id: str,
        *,
        flow_id: str = "",
    ) -> dict[str, Any]:
        require_role(principal, "boi.viewer")
        record = self._read(principal.employee_id)
        connection = self._endpoint(record, endpoint_id)
        api_key = self._api_key(record, endpoint_id)
        endpoint = str(connection.get("base_url") or connection.get("endpoint") or "")
        projects = self.projects(principal, endpoint_id)["projects"]
        if project_id not in {str(item.get("id") or "") for item in projects}:
            raise HTTPException(
                status_code=404,
                detail="project does not belong to this endpoint connection",
            )
        payload = self.langflow.project_mcp(endpoint, api_key, project_id)
        tools = [
            {
                "flow_id": str(item.get("id") or ""),
                "name": str(item.get("name") or ""),
                "description": str(item.get("description") or ""),
                "mcp_enabled": bool(item.get("mcp_enabled")),
                "tool_name": str(item.get("action_name") or ""),
                "tool_description": str(item.get("action_description") or ""),
            }
            for item in payload.get("tools") or []
            if isinstance(item, dict)
            and (not flow_id or str(item.get("id") or "") == flow_id)
        ]
        auth_type = str(
            (
                payload.get("auth_settings")
                if isinstance(payload.get("auth_settings"), dict)
                else {}
            ).get("auth_type")
            or "none"
        )
        streamable_url = self._mcp_streamable_url(endpoint, project_id)
        return {
            "ok": True,
            "endpoint_id": endpoint_id,
            "project_id": project_id,
            "flow_id": flow_id,
            "status": (
                "available"
                if any(item["mcp_enabled"] for item in tools)
                and auth_type == "apikey"
                else "not_ready"
            ),
            "auth": {
                "type": auth_type,
                "header": "x-api-key" if auth_type == "apikey" else "",
                "credential": "${LANGFLOW_API_KEY}" if auth_type == "apikey" else "",
            },
            "streamable_url": streamable_url,
            "tools": tools,
            "client_example": {
                "transport": "streamable_http",
                "url": streamable_url,
                "headers": (
                    {"x-api-key": "${LANGFLOW_API_KEY}"}
                    if auth_type == "apikey"
                    else {}
                ),
            },
        }

    def update_mcp_settings(
        self,
        principal: AuthIdentity,
        endpoint_id: str,
        project_id: str,
        flow_id: str,
        request: PlaygroundMCPUpdateRequest,
    ) -> dict[str, Any]:
        require_role(principal, "boi.editor")
        connection, live_flow, api_key = self._live_flow(
            principal,
            endpoint_id,
            project_id,
            flow_id,
        )
        endpoint = str(connection.get("base_url") or connection.get("endpoint") or "")
        current = self.langflow.project_mcp(endpoint, api_key, project_id)
        settings = [
            {
                key: item.get(key)
                for key in (
                    "id",
                    "mcp_enabled",
                    "action_name",
                    "action_description",
                    "name",
                    "description",
                )
                if key in item
            }
            for item in current.get("tools") or []
            if isinstance(item, dict)
        ]
        selected = next(
            (item for item in settings if str(item.get("id") or "") == flow_id),
            None,
        )
        if selected is None:
            selected = {
                "id": flow_id,
                "name": str(live_flow.get("name") or ""),
                "description": str(live_flow.get("description") or ""),
            }
            settings.append(selected)
        selected.update(
            {
                "mcp_enabled": request.enabled,
                "action_name": request.action_name,
                "action_description": request.action_description,
            }
        )
        self.langflow.update_project_mcp(
            endpoint,
            api_key,
            project_id,
            settings=settings,
            auth_type=request.auth_type,
        )
        with self._lock:
            record = self._read(principal.employee_id)
            registry_item = next(
                (
                    item
                    for item in record.get("flow_registry") or []
                    if isinstance(item, dict)
                    and str(item.get("endpoint_id") or "") == endpoint_id
                    and str(item.get("project_id") or "") == project_id
                    and str(item.get("flow_id") or "") == flow_id
                ),
                None,
            )
            if registry_item is not None:
                registry_item["mcp_enabled"] = request.enabled
                registry_item["mcp_tool"] = request.action_name
                registry_item["mcp_status"] = "ready" if request.enabled else "disabled"
                registry_item["mcp_updated_at"] = now_iso()
                self._write(principal.employee_id, record)
        return self.mcp_settings(
            principal,
            endpoint_id,
            project_id,
            flow_id=flow_id,
        )

    @staticmethod
    async def _call_mcp_tool(
        url: str,
        api_key: str,
        *,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        async with streamablehttp_client(
            url,
            headers={"x-api-key": api_key},
            timeout=30,
            sse_read_timeout=180,
        ) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                listed = await session.list_tools()
                tools = [
                    {
                        "name": item.name,
                        "description": item.description or "",
                        "input_schema": item.inputSchema,
                    }
                    for item in listed.tools
                ]
                selected = next(
                    (item for item in listed.tools if item.name == tool_name),
                    None,
                )
                if selected is None:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "code": "mcp_tool_missing",
                            "message": f"{tool_name} is not exposed by Langflow MCP",
                        },
                    )
                result = await session.call_tool(tool_name, arguments=arguments)
                return {
                    "tools": tools,
                    "call": result.model_dump(mode="json", exclude_none=True),
                }

    def test_mcp(
        self,
        principal: AuthIdentity,
        endpoint_id: str,
        project_id: str,
        flow_id: str,
        request: PlaygroundMCPTestRequest,
    ) -> dict[str, Any]:
        require_role(principal, "boi.viewer")
        connection, _, api_key = self._live_flow(
            principal,
            endpoint_id,
            project_id,
            flow_id,
        )
        endpoint = str(connection.get("base_url") or connection.get("endpoint") or "")
        settings = self.mcp_settings(
            principal,
            endpoint_id,
            project_id,
            flow_id=flow_id,
        )
        selected = next(
            (item for item in settings["tools"] if item["flow_id"] == flow_id),
            None,
        )
        if not selected or not selected["mcp_enabled"]:
            raise HTTPException(status_code=409, detail="selected Flow is not enabled as an MCP tool")
        if settings["auth"]["type"] != "apikey":
            raise HTTPException(status_code=409, detail="Langflow MCP API Key authentication is required")
        input_value = json.dumps(
            {
                "question": request.question,
                "task_ref": request.task_ref,
                # This value is intentionally passed through for the negative
                # policy check. The representative Flow itself must reject a
                # private draft when no caller-bound Action token is present.
                "save_mode": request.save_mode,
                "title": "Universal Simulation MCP 미리보기",
                "trace_id": f"mcp-preview-{uuid.uuid4().hex}",
            },
            ensure_ascii=False,
        )
        internal_url = (
            f"{endpoint}/api/v1/mcp/project/{project_id}/streamable"
        )
        result = asyncio.run(
            self._call_mcp_tool(
                internal_url,
                api_key,
                tool_name=str(selected["tool_name"]),
                arguments={"input_value": input_value},
            )
        )
        serialized = json.dumps(result, ensure_ascii=False, default=str)
        if any(pattern.search(serialized) for pattern in SECRET_PATTERNS):
            raise HTTPException(status_code=502, detail="secret-like value detected in MCP output")
        exact_tools = [
            item
            for item in result["tools"]
            if str(item.get("name") or "") == str(selected["tool_name"])
        ]
        if len(exact_tools) != 1:
            raise HTTPException(
                status_code=409,
                detail="representative MCP tool must be exposed exactly once",
            )
        with self._lock:
            record = self._read(principal.employee_id)
            for item in record.get("flow_registry") or []:
                if (
                    isinstance(item, dict)
                    and str(item.get("endpoint_id") or "") == endpoint_id
                    and str(item.get("project_id") or "") == project_id
                    and str(item.get("flow_id") or "") == flow_id
                ):
                    item["mcp_status"] = "validated"
                    item["mcp_last_tested_at"] = now_iso()
            self._write(principal.employee_id, record)
        return {
            "ok": True,
            "endpoint_id": endpoint_id,
            "project_id": project_id,
            "flow_id": flow_id,
            "tool_name": selected["tool_name"],
            "save_mode": request.save_mode,
            "write_allowed": False,
            "write_blocked": (
                request.save_mode == "private_draft"
                and (
                    "action_run_token_required" in serialized
                    or "MCP 미리보기만 수행했습니다" in serialized
                )
            ),
            "tested_at": now_iso(),
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
        try:
            live_flow = self.langflow.flow(
                connection_endpoint,
                self._api_key(record, request.endpoint_id),
                request.flow_id,
            )
        except HTTPException:
            live_flow = flow
        checksum = self._runtime_flow_checksum(live_flow)
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
            "validated_checksum": checksum,
            "live_checksum": checksum,
            "checksum_state": "matched",
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
                "validated_checksum": checksum,
                "live_checksum": checksum,
                "checksum_state": "matched",
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
        universal_mcp = (
            has_component("BoIUniversalSimulationMCPAgent")
            or str(declared_contract.get("endpoint_name") or "")
            == UNIVERSAL_MCP_FLOW_ENDPOINT
            or str((declared_contract.get("mcp") or {}).get("tool_name") or "")
            == UNIVERSAL_MCP_TOOL_NAME
        )
        model_backed = (
            declared_agent_kind == "openai_compatible_model"
            or has_component("BoIModelAgent")
            or universal_mcp
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
            declared_outputs = declared_contract.get("outputs")
            contract_fields = {
                "version": str(declared_contract.get("version") or "")
                == (
                    UNIVERSAL_MCP_FLOW_VERSION
                    if universal_mcp
                    else CANONICAL_FLOW_VERSION
                ),
                "inputs": declared_contract.get("inputs") == expected_inputs,
                "outputs": (
                    all(
                        item in declared_outputs
                        for item in expected_outputs
                    )
                    if universal_mcp and isinstance(declared_outputs, list)
                    else declared_outputs == expected_outputs
                ),
                "checksum": bool(declared_hash) and declared_hash == computed_hash,
            }
            inferred_manifest = False
        secret_matches = [
            pattern.pattern
            for pattern in SECRET_PATTERNS
            if pattern.search(serialized)
        ]
        structured_graph = any(
            isinstance(node, dict)
            for node in flow_data.get("nodes") or []
        )
        graph_health = (
            AgentPlaygroundService._graph_health(flow)
            if structured_graph
            else {
                "end_to_end_reachable": True,
                "execution_path_nodes": [],
                "connected_component_ids": [],
                "disconnected_nodes": [],
            }
        )
        return {
            "ok": (
                not missing_components
                and not present_forbidden
                and not secret_matches
                and all(contract_fields.values())
                and graph_health["end_to_end_reachable"]
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
            "graph_health": graph_health,
            "input_contract": expected_inputs,
            "output_contract": expected_outputs,
            "agent_kind": (
                "openai_compatible_model"
                if model_backed
                else declared_agent_kind or "contract_agent"
            ),
        }

    @classmethod
    def _adopted_component_graph_state(
        cls,
        flow: dict[str, Any],
        source_assets: list[dict[str, Any]],
    ) -> dict[str, Any]:
        data = flow.get("data") if isinstance(flow.get("data"), dict) else {}
        nodes = [item for item in data.get("nodes") or [] if isinstance(item, dict)]
        health = cls._graph_health(flow)
        execution_path = set(health.get("execution_path_nodes") or [])
        component_assets = [
            asset
            for asset in source_assets
            if isinstance(asset, dict) and str(asset.get("type") or "") == "py"
        ]
        items: list[dict[str, Any]] = []
        for asset in component_assets:
            asset_id = str(asset.get("asset_id") or "")
            title_key = re.sub(
                r"[^a-z0-9]+",
                "",
                str(asset.get("title") or "").lower(),
            )
            matches = []
            for node in nodes:
                identities = cls._node_component_identity(node)
                normalized = {
                    re.sub(r"[^a-z0-9]+", "", value.lower())
                    for value in identities
                }
                data_value = node.get("data") if isinstance(node.get("data"), dict) else {}
                component = (
                    data_value.get("node")
                    if isinstance(data_value.get("node"), dict)
                    else {}
                )
                metadata = (
                    component.get("metadata")
                    if isinstance(component.get("metadata"), dict)
                    else {}
                )
                if (
                    str(metadata.get("component_asset_id") or "") == asset_id
                    or (
                        title_key
                        and any(
                            title_key in value or value in title_key
                            for value in normalized
                            if len(value) >= 8
                        )
                    )
                ):
                    matches.append(node)
            if not matches and len(component_assets) == 1:
                contract_matches = [
                    node
                    for node in nodes
                    if cls._node_component_contract(node).get("contract_id")
                    == "boi.agent-slot.v1"
                ]
                if len(contract_matches) == 1:
                    matches = contract_matches
            node_ids = [cls._node_id(node) for node in matches]
            connected = [node_id for node_id in node_ids if node_id in execution_path]
            items.append(
                {
                    "asset_id": asset_id,
                    "title": str(asset.get("title") or ""),
                    "node_ids": node_ids,
                    "deployed": bool(node_ids),
                    "connected": len(connected) == 1 and len(node_ids) == 1,
                    "connected_node_ids": connected,
                }
            )
        return {
            "items": items,
            "all_deployed": all(item["deployed"] for item in items),
            "all_connected": all(item["connected"] for item in items),
            "disconnected_component_ids": [
                item["asset_id"]
                for item in items
                if item["deployed"] and not item["connected"]
            ],
            "missing_component_ids": [
                item["asset_id"] for item in items if not item["deployed"]
            ],
        }

    @staticmethod
    def _executed_component_ids(result: Any) -> list[str]:
        collected: set[str] = set()
        if isinstance(result, dict):
            for key, value in result.items():
                if key in {"component_asset_id", "executed_component_id"} and isinstance(value, str):
                    if value:
                        collected.add(value)
                elif key == "executed_component_ids" and isinstance(value, list):
                    collected.update(str(item) for item in value if str(item))
                else:
                    collected.update(AgentPlaygroundService._executed_component_ids(value))
        elif isinstance(result, list):
            for value in result:
                collected.update(AgentPlaygroundService._executed_component_ids(value))
        return sorted(collected)

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
        checksum = self._runtime_flow_checksum(flow)
        source_assets = [
            item
            for item in exact_deployment.get("source_assets") or []
            if isinstance(item, dict)
        ]
        component_graph = self._adopted_component_graph_state(flow, source_assets)
        structural["component_graph"] = component_graph
        if (
            component_graph["items"]
            and (
                not component_graph["all_deployed"]
                or not component_graph["all_connected"]
            )
        ):
            structural["ok"] = False
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
        executed_component_ids: list[str] = []
        if structural["ok"]:
            preview = PlaygroundFlowTestRequest(
                endpoint_id=request.endpoint_id,
                project_id=request.project_id,
                question=request.question,
                save_mode="preview",
                title="Flow 검증 미리보기",
            )
            runtime_result = self._run(endpoint, api_key, flow_id, preview)
            executed_component_ids = self._executed_component_ids(runtime_result)
            expected_component_ids = [
                str(item.get("asset_id") or "")
                for item in component_graph["items"]
                if item.get("connected")
            ]
            component_execution_ok = all(
                component_id in executed_component_ids
                for component_id in expected_component_ids
            )
            history.append(
                {
                    "stage": "build_validated",
                    "status": (
                        "passed"
                        if structural["graph_health"]["end_to_end_reachable"]
                        and component_execution_ok
                        else "failed"
                    ),
                    "checked_at": now_iso(),
                    "details": {
                        "actual_run_completed": True,
                        "graph_health": structural["graph_health"],
                        "expected_component_ids": expected_component_ids,
                        "executed_component_ids": executed_component_ids,
                        "component_execution_proven": component_execution_ok,
                    },
                }
            )
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
            if not component_execution_ok:
                runtime_contract["ok"] = False
                runtime_contract["component_execution_proven"] = False
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
                task_ref = request.task_ref
                if not task_ref:
                    failure_reason = "actual Task anchor is required for Task validation"
                    history.append(
                        {
                            "stage": "task_validated",
                            "status": "failed",
                            "checked_at": now_iso(),
                            "details": {
                                "actual_task_anchor": False,
                                "synthetic_task_anchor_allowed": False,
                            },
                        }
                    )
                    task_ref = ""
                if not task_ref:
                    task_payload = None
                else:
                    task_payload = PlaygroundFlowTestRequest(
                        endpoint_id=request.endpoint_id,
                        project_id=request.project_id,
                        question="이 Task의 실제 SOP 단계, 선행 결과, 필요한 근거와 부족한 근거를 정리해줘.",
                        business_context="Agent Playground 실제 Task Context 검증",
                        task_ref=task_ref,
                        save_mode="preview",
                        title="실제 Task Context 검증",
                    )
                if task_payload is None:
                    task_result = {}
                else:
                    validation_trace = f"flow-validation-{uuid.uuid4().hex}"
                    validation_execution_id = f"boi-validation-{uuid.uuid4().hex}"
                    validation_deployment_id = f"validation:{request.endpoint_id}:{flow_id}"
                    run_token = self.pat_service.create_run_token(
                        principal,
                        action_key=f"agent-playground.validation.{flow_id}",
                        deployment_id=validation_deployment_id,
                        endpoint_id=request.endpoint_id,
                        project_id=request.project_id,
                        flow_id=flow_id,
                        trace_id=validation_trace,
                        execution_id=validation_execution_id,
                        allowed_capabilities=["boi.search", "boi.get"],
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
                            audience={
                                "BOI_ACTION_KEY": f"agent-playground.validation.{flow_id}",
                                "BOI_DEPLOYMENT_ID": validation_deployment_id,
                                "BOI_ENDPOINT_ID": request.endpoint_id,
                                "BOI_PROJECT_ID": request.project_id,
                                "BOI_FLOW_ID": flow_id,
                                "BOI_TRACE_ID": validation_trace,
                                "BOI_EXECUTION_ID": validation_execution_id,
                            },
                        )
                    finally:
                        self.pat_service.consume_run_token(str(run_token["token_id"]))
                if task_payload is None:
                    task_contract = {"ok": False, "fields": {"source_references": False}}
                    task_payload_result = {}
                else:
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
                    "task_ref": (
                        task_payload is not None
                        and task_context.get("task_ref") == task_payload.task_ref
                    ),
                    "sop_ref": bool(task_context.get("sop_ref")),
                    "sop_stage": bool(task_context.get("sop_stage")),
                    "event_ref": bool(task_context.get("event_ref")),
                    "action_ref": bool(task_context.get("action_ref")),
                    "prior_results": isinstance(task_context.get("prior_results"), list),
                    "required_evidence": bool(task_context.get("required_evidence")),
                    "missing_evidence": isinstance(task_context.get("missing_evidence"), list),
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
                    "connected Agent Hub component has no runtime execution provenance"
                    if not component_execution_ok
                    else
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
            elif structural["component_graph"]["disconnected_component_ids"]:
                failure_reason = "disconnected_component"
            elif structural["component_graph"]["missing_component_ids"]:
                failure_reason = "agent_hub_component_not_deployed"
            elif not structural["graph_health"]["end_to_end_reachable"]:
                failure_reason = "flow_execution_path_is_disconnected"
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
            linked_deployment = next(
                (
                    deployment
                    for deployment in record.get("deployments") or []
                    if isinstance(deployment, dict)
                    and str(deployment.get("endpoint_id") or "") == request.endpoint_id
                    and str(deployment.get("project_id") or "") == request.project_id
                    and str(deployment.get("flow_id") or "") == flow_id
                ),
                None,
            )
            effective_validation_status = validation_status
            if (
                validation_status == "action_ready"
                and isinstance(linked_deployment, dict)
                and str(linked_deployment.get("action_draft_id") or "")
            ):
                effective_validation_status = "action_linked"
                history.append(
                    {
                        "stage": "action_linked",
                        "status": "passed",
                        "checked_at": now_iso(),
                        "details": {
                            "draft_id": str(linked_deployment.get("action_draft_id") or ""),
                            "preserved_after_revalidation": True,
                        },
                    }
                )
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
                    "validated_checksum": checksum,
                    "live_checksum": checksum,
                    "checksum_state": "matched",
                    "graph_health": structural["graph_health"],
                    "connected_component_ids": structural["graph_health"].get(
                        "connected_component_ids"
                    ) or [],
                    "disconnected_nodes": structural["graph_health"].get(
                        "disconnected_nodes"
                    ) or [],
                    "executed_component_ids": executed_component_ids,
                    "validation_profile": validation_profile,
                    "input_contract": structural["input_contract"],
                    "output_contract": structural["output_contract"],
                    "validation_status": effective_validation_status,
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
                    deployment["status"] = effective_validation_status
                    deployment["validation_profile"] = validation_profile
                    deployment["input_contract"] = structural["input_contract"]
                    deployment["output_contract"] = structural["output_contract"]
                    deployment["artifact_checksum"] = checksum
                    deployment["validated_checksum"] = checksum
                    deployment["live_checksum"] = checksum
                    deployment["checksum_state"] = "matched"
                    deployment["graph_health"] = structural["graph_health"]
                    deployment["executed_component_ids"] = executed_component_ids
                    deployment["validated_at"] = now_iso()
                    if failure_reason:
                        deployment["failure_reason"] = failure_reason
                    else:
                        deployment.pop("failure_reason", None)
            self._write(principal.employee_id, record)
        return {
            "ok": effective_validation_status in {"action_ready", "action_linked"},
            "endpoint_id": request.endpoint_id,
            "project_id": request.project_id,
            "flow_id": flow_id,
            "artifact_version": artifact_version,
            "artifact_checksum": checksum,
            "validation_status": effective_validation_status,
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

    def action_draft_payload(
        self,
        principal: AuthIdentity,
        deployment_id: str,
        *,
        scope: Literal["private", "team"] = "private",
        team_id: str = "",
    ) -> dict[str, Any]:
        require_role(principal, "boi.editor", "boi.action_invoker")
        if scope == "team":
            if not team_id:
                raise HTTPException(status_code=422, detail="team_id is required for team Action")
            if team_id not in principal.teams:
                raise HTTPException(
                    status_code=403,
                    detail="Action owner is not a member of the selected HCP team",
                )
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
        execution = self.execution_connection(
            deployment_id,
            str(deployment.get("flow_id") or ""),
        )
        live_flow = self.langflow.flow(
            execution["endpoint"],
            execution["api_key"],
            str(deployment.get("flow_id") or ""),
        )
        flow_display_snapshot = {
            **self.flow_display_snapshot(live_flow),
            "project_name": str(
                (
                    self._read(principal.employee_id)
                    .get("endpoint_setups", {})
                    .get(str(deployment.get("endpoint_id") or ""), {})
                    .get("project", {})
                    .get("name")
                )
                or f"{PROJECT_PREFIX}{principal.employee_id}"
            ),
            "source_origin": str(
                deployment.get("origin") or "agent_playground"
            ),
            "validation_status": str(deployment.get("status") or ""),
            "checksum_state": str(deployment.get("checksum_state") or "matched"),
            "validated_at": str(deployment.get("validated_at") or ""),
        }
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
            "flow_display_snapshot": flow_display_snapshot,
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
            "scope": scope,
            "folder": (
                f"team/{team_id}/action-drafts"
                if scope == "team"
                else f"private/{principal.employee_id}/action-drafts"
            ),
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
            "team_id": team_id if scope == "team" else "",
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
        selected_project_id = str((project or {}).get("id") or "")
        selected_endpoint_deployments = [
            item
            for item in deployments
            if str(item.get("endpoint_id") or "") == default_endpoint_id
            and (
                not selected_project_id
                or str(item.get("project_id") or "") == selected_project_id
            )
        ]
        selected_hub_adoptions = [
            item
            for item in hub_adoptions
            if str(item.get("endpoint_id") or "") == default_endpoint_id
            and (
                not selected_project_id
                or str(item.get("project_id") or "") == selected_project_id
            )
        ]
        pending_hub_adoption = next(
            (
                item
                for item in reversed(selected_hub_adoptions)
                if str(item.get("status") or "") != "confirmed"
            ),
            None,
        )
        if selected_endpoint_deployments:
            hub_onboarding = {
                "required": False,
                "status": "complete",
                "next_action": "review_deployment",
                "message": "Agent Hub 배포 Flow를 이 프로젝트에서 확인했습니다.",
                "deployment_id": str(
                    selected_endpoint_deployments[-1].get("deployment_id") or ""
                ),
            }
        elif pending_hub_adoption:
            hub_onboarding = {
                "required": True,
                "status": "in_progress",
                "next_action": "discover_deployment",
                "message": "Agent Hub 배포를 마친 뒤 결과를 확인하세요.",
                "adoption_id": str(pending_hub_adoption.get("adoption_id") or ""),
            }
        else:
            hub_onboarding = {
                "required": True,
                "status": "not_started",
                "next_action": "open_agent_hub",
                "message": "첫 배포 전에 endpoint 연결과 프로젝트 선택을 안내합니다.",
            }

        flow_registry = [
            item for item in record.get("flow_registry") or [] if isinstance(item, dict)
        ]
        selected_registry = [
            item
            for item in flow_registry
            if (
                not default_endpoint_id
                or str(item.get("endpoint_id") or "") == default_endpoint_id
            )
            and (
                not selected_project_id
                or str(item.get("project_id") or "") == selected_project_id
            )
        ]
        verified_flow = next(
            (
                item
                for item in reversed(selected_registry)
                if str(item.get("validation_status") or "")
                in {"action_ready", "action_linked"}
            ),
            None,
        )
        action_status = str((action or {}).get("status") or "not_connected")
        completed_stages: list[str] = []
        if not onboarding.get("required"):
            completed_stages.append("onboarding")
        if project and flow:
            completed_stages.append("create")
        if verified_flow:
            completed_stages.append("test")
        if selected_endpoint_deployments:
            completed_stages.append("hub")
        if action_status not in {"", "not_connected"}:
            completed_stages.append("action")

        blockers: list[str] = []
        if onboarding.get("required"):
            blockers.append(str(onboarding.get("last_error") or onboarding.get("message") or "온보딩 필요"))
        if connection and str(connection.get("status") or "") != "connected":
            blockers.append(str(connection.get("last_error") or "Langflow 연결 확인 필요"))
        if action_status not in {"", "not_connected"}:
            current_stage = "action"
            next_action = {
                "id": "open_action_draft",
                "stage": "action",
                "label": "Action 등록 상태 확인",
                "description": "등록 초안과 publish-request 상태를 확인하세요.",
            }
        elif verified_flow and selected_endpoint_deployments:
            current_stage = "action"
            next_action = {
                "id": "create_action",
                "stage": "action",
                "label": "Action으로 연결",
                "description": "검증된 Flow를 connector-neutral Action에 연결하세요.",
            }
        elif selected_endpoint_deployments:
            current_stage = "test"
            next_action = {
                "id": "validate_flow",
                "stage": "test",
                "label": "배포 Flow 검증",
                "description": "업무 맥락·Ontology·Wiki 근거와 저장 동작을 확인하세요.",
            }
        elif verified_flow:
            current_stage = "hub"
            next_action = {
                "id": "open_agent_hub",
                "stage": "hub",
                "label": "Agent Hub에서 배포",
                "description": "검증한 Flow를 기존 Agent Hub UI에서 개인 프로젝트로 배포하세요.",
            }
        elif not onboarding.get("required") and project and flow:
            current_stage = "create"
            next_action = {
                "id": "open_langflow",
                "stage": "create",
                "label": "Langflow에서 Flow 만들기",
                "description": "개인 프로젝트에서 Agent를 편집하고 충분히 시험하세요.",
            }
        else:
            current_stage = "onboarding"
            next_action = {
                "id": str(onboarding.get("next_action") or "open_langflow_settings"),
                "stage": "onboarding",
                "label": "Agent 개발 공간 준비",
                "description": "개인 Langflow 연결과 기준 Flow 준비를 완료하세요.",
            }
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
            "flows": flow_registry,
            "deployments": deployments,
            "hub_adoptions": hub_adoptions,
            "journey": {
                "current_stage": current_stage,
                "next_action": next_action,
                "blockers": blockers,
                "completed_stages": completed_stages,
            },
            "hub_onboarding": hub_onboarding,
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
            "recommended_asset": {
                "name": UNIVERSAL_MCP_FLOW_NAME,
                "endpoint_name": UNIVERSAL_MCP_FLOW_ENDPOINT,
                "version": UNIVERSAL_MCP_FLOW_VERSION,
                "checksum": self._recommended_flow_checksum(),
                "mcp_tool": UNIVERSAL_MCP_TOOL_NAME,
                "mcp_transport": "streamable_http",
                "save_policy": "action_token_required",
                "default_save_mode": "preview",
                "model": "LM Studio Gemma",
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
        deployment = self.deployment(principal, deployment_id)
        draft_id = str(draft.get("draft_id") or "")
        with self._lock:
            record = self._read(principal.employee_id)
            record["action"] = {
                "status": str(draft.get("status") or "draft"),
                "draft_id": draft_id,
                "draft_url": f"/actions/drafts/{draft_id}" if draft_id else "",
                "deployment_id": deployment_id,
                "action_key": str(
                    (
                        draft.get("request")
                        if isinstance(draft.get("request"), dict)
                        else {}
                    ).get("action_key")
                    or ""
                ),
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
        self.execution_connection(
            deployment_id,
            flow_id,
            action_key=str(request.get("action_key") or ""),
        )
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

    def execution_connection(
        self,
        deployment_id: str,
        flow_id: str,
        *,
        action_key: str = "",
    ) -> dict[str, str]:
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
            recorded_action = (
                record.get("action")
                if isinstance(record.get("action"), dict)
                and str(record["action"].get("deployment_id") or "") == deployment_id
                else {}
            )
            recorded_action_key = str(recorded_action.get("action_key") or "")
            if (
                recorded_action_key
                and action_key
                and recorded_action_key != str(action_key or "")
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Action key does not match the deployment registration",
                )
            endpoint = str(connection.get("base_url") or connection.get("endpoint") or "")
            api_key = self._api_key(record, endpoint_id)
            live_flow = self.langflow.flow(endpoint, api_key, flow_id)
            live_checksum = self._runtime_flow_checksum(live_flow)
            registered_checksum = str(
                deployment.get("validated_checksum")
                or deployment.get("artifact_checksum")
                or ""
            )
            if not registered_checksum or live_checksum != registered_checksum:
                deployment["status"] = "blocked"
                deployment["checksum_state"] = "drifted"
                deployment["live_checksum"] = live_checksum
                deployment["failure_reason"] = "flow_checksum_drift"
                deployment["drift_detected_at"] = now_iso()
                for registry_item in record.get("flow_registry") or []:
                    if (
                        isinstance(registry_item, dict)
                        and str(registry_item.get("endpoint_id") or "") == endpoint_id
                        and str(registry_item.get("project_id") or "")
                        == str(deployment.get("project_id") or "")
                        and str(registry_item.get("flow_id") or "") == flow_id
                    ):
                        registry_item["validation_status"] = "blocked"
                        registry_item["checksum_state"] = "drifted"
                        registry_item["live_checksum"] = live_checksum
                        registry_item["failure_reason"] = "flow_checksum_drift"
                self._write(str(record.get("employee_id") or ""), record)
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "flow_checksum_drift",
                        "registered_checksum": registered_checksum,
                        "live_checksum": live_checksum,
                    },
                )
            return {
                "endpoint": endpoint,
                "api_key": api_key,
                "langflow_user_id": str(connection.get("langflow_user_id") or ""),
                "owner_employee_id": str(record.get("employee_id") or ""),
                "endpoint_id": endpoint_id,
                "project_id": str(deployment.get("project_id") or ""),
                "registered_checksum": registered_checksum,
                "live_checksum": live_checksum,
            }
        raise HTTPException(status_code=404, detail="Agent Playground deployment not found")

    def action_flow_view(
        self,
        principal: AuthIdentity,
        action: dict[str, Any],
    ) -> dict[str, Any]:
        """Resolve a catalog Action to a sanitized live Langflow Flow view."""

        require_role(principal, "boi.viewer")
        binding = (
            action.get("connector_binding")
            if isinstance(action.get("connector_binding"), dict)
            else {}
        )
        connector = (
            binding.get("config")
            if isinstance(binding.get("config"), dict)
            else action.get("connector_config")
            if isinstance(action.get("connector_config"), dict)
            else {}
        )
        reference = (
            binding.get("deployment_reference")
            if isinstance(binding.get("deployment_reference"), dict)
            else connector
        )
        if (
            str(action.get("connector_kind") or binding.get("kind") or "")
            != "langflow"
            or str(connector.get("connection_source") or "") != "agent_playground"
        ):
            raise HTTPException(
                status_code=404,
                detail="이 Action에는 표시할 Agent Playground Flow가 없습니다.",
            )
        deployment_id = str(reference.get("deployment_id") or "")
        flow_id = str(reference.get("flow_id") or "")
        if not deployment_id or not flow_id:
            raise HTTPException(status_code=409, detail="Action Flow reference is incomplete")

        owner_hint = str(action.get("owner_employee_id") or "")
        paths: list[Path] = []
        if owner_hint and self._path(owner_hint).exists():
            paths.append(self._path(owner_hint))
        users_root = self.root / "users"
        for path in sorted(users_root.glob("*.json")) if users_root.exists() else []:
            if path not in paths:
                paths.append(path)

        record: dict[str, Any] | None = None
        deployment: dict[str, Any] | None = None
        for path in paths:
            try:
                candidate = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            matched = next(
                (
                    item
                    for item in candidate.get("deployments") or []
                    if isinstance(item, dict)
                    and str(item.get("deployment_id") or "") == deployment_id
                ),
                None,
            )
            if matched is not None:
                record = candidate
                deployment = matched
                break
        if record is None or deployment is None:
            raise HTTPException(status_code=404, detail="연결된 Flow 배포를 찾을 수 없습니다.")

        exact_fields = {
            "endpoint_connection_id": "endpoint_id",
            "deployment_id": "deployment_id",
            "project_id": "project_id",
            "flow_id": "flow_id",
            "artifact_version": "asset_version",
            "artifact_checksum": "artifact_checksum",
        }
        if any(
            str(reference.get(reference_key) or "")
            != str(deployment.get(deployment_key) or "")
            for reference_key, deployment_key in exact_fields.items()
        ):
            raise HTTPException(
                status_code=409,
                detail="Action과 Flow 배포 참조가 일치하지 않습니다.",
            )

        owner_employee_id = str(record.get("employee_id") or "")
        endpoint_id = str(deployment.get("endpoint_id") or "")
        project_id = str(deployment.get("project_id") or "")
        stored_snapshot = (
            connector.get("flow_display_snapshot")
            if isinstance(connector.get("flow_display_snapshot"), dict)
            else {}
        )
        snapshot = {
            "name": str(
                stored_snapshot.get("name")
                or deployment.get("flow_name")
                or "Langflow Flow"
            ),
            "description": str(stored_snapshot.get("description") or ""),
            "endpoint_name": str(stored_snapshot.get("endpoint_name") or ""),
            "node_count": int(stored_snapshot.get("node_count") or 0),
            "edge_count": int(stored_snapshot.get("edge_count") or 0),
            "nodes": list(stored_snapshot.get("nodes") or []),
            "edges": list(stored_snapshot.get("edges") or []),
            "end_to_end_reachable": bool(
                stored_snapshot.get("end_to_end_reachable")
            ),
            "connected_component_ids": list(
                stored_snapshot.get("connected_component_ids") or []
            ),
        }
        live_state = "unavailable"
        live_checksum = ""
        try:
            connection = self._endpoint(record, endpoint_id)
            endpoint = str(
                connection.get("base_url") or connection.get("endpoint") or ""
            )
            api_key = self._api_key(record, endpoint_id)
            live_flow = self.langflow.flow(endpoint, api_key, flow_id)
            snapshot = self.flow_display_snapshot(live_flow)
            live_checksum = self._runtime_flow_checksum(live_flow)
            live_state = "available"
        except HTTPException:
            pass

        registered_checksum = str(
            deployment.get("validated_checksum")
            or deployment.get("artifact_checksum")
            or reference.get("artifact_checksum")
            or ""
        )
        checksum_state = (
            "matched"
            if live_checksum and registered_checksum == live_checksum
            else "drifted"
            if live_checksum and registered_checksum
            else str(deployment.get("checksum_state") or "unknown")
        )
        setups = (
            record.get("endpoint_setups")
            if isinstance(record.get("endpoint_setups"), dict)
            else {}
        )
        setup = (
            setups.get(endpoint_id)
            if isinstance(setups.get(endpoint_id), dict)
            else {}
        )
        project = (
            setup.get("project")
            if isinstance(setup.get("project"), dict)
            else {}
        )
        project_name = str(
            stored_snapshot.get("project_name")
            or project.get("name")
            or f"{PROJECT_PREFIX}{owner_employee_id}"
        )
        can_manage = bool(
            principal.employee_id == owner_employee_id
            and (principal.is_admin or "boi.editor" in principal.roles)
        )
        links = {"playground": "", "langflow": ""}
        technical: dict[str, str] = {}
        if can_manage:
            links["playground"] = "/playground?" + urlencode(
                {
                    "stage": "create",
                    "endpoint_id": endpoint_id,
                    "project_id": project_id,
                    "flow_id": flow_id,
                }
            )
            external_url = str(os.getenv("LANGFLOW_EXTERNAL_URL") or "").rstrip("/")
            if external_url.startswith(("http://", "https://")):
                links["langflow"] = (
                    f"{external_url}/flow/{flow_id}/folder/{project_id}"
                )
            technical = {
                "deployment_id": deployment_id,
                "project_id": project_id,
                "flow_id": flow_id,
                "artifact_version": str(
                    deployment.get("asset_version")
                    or reference.get("artifact_version")
                    or ""
                ),
                "artifact_checksum": registered_checksum,
                "live_checksum": live_checksum,
            }
        return {
            "available": True,
            "action_key": str(action.get("action_key") or ""),
            "flow": snapshot,
            "project_name": project_name,
            "source_origin": str(
                stored_snapshot.get("source_origin")
                or deployment.get("origin")
                or connector.get("source_origin")
                or "agent_playground"
            ),
            "validation_status": (
                "blocked"
                if checksum_state == "drifted"
                else str(deployment.get("status") or "action_linked")
            ),
            "checksum_state": checksum_state,
            "live_state": live_state,
            "validated_at": str(
                stored_snapshot.get("validated_at")
                or deployment.get("validated_at")
                or ""
            ),
            "owner_label": (
                "내 Flow"
                if principal.employee_id == owner_employee_id
                else "공유된 Action Flow"
            ),
            "permissions": {
                "can_open_playground": can_manage,
                "can_open_langflow": bool(can_manage and links["langflow"]),
            },
            "links": links,
            "technical": technical,
        }

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
        universal_mcp_path = (
            self.repo_root
            / "langflow"
            / "flows"
            / "boi_universal_simulation_mcp.json"
        )
        universal_mcp_checksum = (
            self._recommended_flow_checksum()
            if universal_mcp_path.exists()
            else ""
        )
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
        elif (
            universal_mcp_path.exists()
            and str(registry_item.get("artifact_checksum") or "")
            == universal_mcp_checksum
        ):
            universal_export = json.loads(
                universal_mcp_path.read_text(encoding="utf-8")
            )
            serialized_flow = universal_mcp_path.read_bytes()
            safe_flow_name = "boi_universal_simulation_mcp"
            artifact_name = str(
                universal_export.get("name") or UNIVERSAL_MCP_FLOW_NAME
            )
            artifact_endpoint_name = str(
                universal_export.get("endpoint_name")
                or UNIVERSAL_MCP_FLOW_ENDPOINT
            )
        component_root = self.repo_root / "langflow" / "custom_components" / "boi"
        static_paths = [
            *sorted(component_root.glob("*.py")),
            self.repo_root / "langflow" / "flows" / "boi_wiki_agent_loop_model_agent.json",
            self.repo_root / "langflow" / "flows" / "boi_universal_simulation_mcp.json",
            self.repo_root / "langflow" / "compatibility-manifest.json",
            self.repo_root / "langflow" / "agent_hub" / "README.md",
        ]
        missing = [str(path.relative_to(self.repo_root)) for path in static_paths if not path.exists()]
        if missing:
            raise HTTPException(status_code=503, detail={"message": "Agent Hub artifact is incomplete", "missing": missing})
        checksum = hashlib.sha256(serialized_flow).hexdigest()
        serialized_flow_text = serialized_flow.decode("utf-8", errors="ignore")
        model_agent_artifact = "BoIModelAgent" in serialized_flow_text
        universal_mcp_artifact = (
            "BoIUniversalSimulationMCPAgent" in serialized_flow_text
        )
        manifest = {
            "schema_version": "boi-agent-hub-validation-v2",
            "name": artifact_name,
            "endpoint_name": artifact_endpoint_name,
            "version": (
                UNIVERSAL_MCP_FLOW_VERSION
                if universal_mcp_artifact
                else CANONICAL_FLOW_VERSION
            ),
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
                (
                    "BoIUniversalSimulationMCPAgent"
                    if universal_mcp_artifact
                    else "BoIModelAgent"
                    if model_agent_artifact
                    else "BoIAgentSlot"
                ),
                "BoIWikiSave",
            ],
            "credential_variables": (
                [
                    BOI_PAT_VARIABLE_NAME,
                    BOI_LLM_API_KEY_VARIABLE_NAME,
                ]
                if model_agent_artifact or universal_mcp_artifact
                else [BOI_PAT_VARIABLE_NAME]
            ),
            "configuration_variables": (
                ["BOI_LLM_BASE_URL", "BOI_AGENT_EXAMPLE_MODEL"]
                if model_agent_artifact or universal_mcp_artifact
                else []
            ),
            "agent_kind": (
                "openai_compatible_model"
                if model_agent_artifact or universal_mcp_artifact
                else "contract_shell"
            ),
            "mcp": (
                {
                    "enabled": True,
                    "tool_name": UNIVERSAL_MCP_TOOL_NAME,
                    "transport": "streamable_http",
                    "auth": "apikey",
                    "external_save_policy": "preview_only",
                }
                if universal_mcp_artifact
                else {"enabled": False}
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
            "defaults": {
                "save_mode": "preview",
                "write_policy": (
                    "action_token_required"
                    if universal_mcp_artifact
                    else "owner_or_action"
                ),
            },
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
