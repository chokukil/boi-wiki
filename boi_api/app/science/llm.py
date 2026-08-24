"""Strict, non-authoritative LLM interpretation boundary."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import httpx
from pydantic import Field, model_validator

from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.models import (
    LLMModelSettings,
    NormalizedClaim,
    ScienceModel,
    SourceSpan,
)


PROMPT_VERSION = "science-interpretation/0.1.0"


class ScienceInterpretationUnavailable(RuntimeError):
    """Interpretation failed without producing a usable claim candidate."""


class CandidateMeaning(ScienceModel):
    ambiguity_id: str | None = None
    surface_term: str = Field(min_length=1)
    ontology_ref: str = Field(min_length=1)
    meaning: str = Field(min_length=1)


class DecisionImpact(ScienceModel):
    ambiguity_id: str = Field(min_length=1)
    changes_outcome: bool
    reason: str = Field(min_length=1)


class LLMClaimCandidate(ScienceModel):
    source_span: SourceSpan
    normalized_claim: NormalizedClaim
    ontology_refs: list[str]
    ambiguity_ids: list[str]
    candidate_meanings: list[CandidateMeaning]
    decision_impact: list[DecisionImpact]

    @model_validator(mode="after")
    def exact_ambiguity_links(self) -> "LLMClaimCandidate":
        if len(self.ontology_refs) != len(set(self.ontology_refs)):
            raise ValueError("ontology_refs must be unique")
        if len(self.ambiguity_ids) != len(set(self.ambiguity_ids)):
            raise ValueError("ambiguity_ids must be unique")
        known = set(self.ambiguity_ids)
        impact_ids = [item.ambiguity_id for item in self.decision_impact]
        if len(impact_ids) != len(set(impact_ids)):
            raise ValueError("decision impact must be unique per ambiguity")
        if set(impact_ids) != known:
            raise ValueError("every ambiguity requires exactly one decision impact")
        meaning_ids = {
            item.ambiguity_id
            for item in self.candidate_meanings
            if item.ambiguity_id is not None
        }
        if meaning_ids - known:
            raise ValueError("candidate meaning references an undeclared ambiguity")
        return self


class ScienceInterpretationPayload(ScienceModel):
    claims: list[LLMClaimCandidate] = Field(min_length=1)


@dataclass(frozen=True)
class ScienceLLMResult:
    payload: ScienceInterpretationPayload
    response_digest: str


@dataclass(frozen=True)
class ScienceLLMConfig:
    """Runtime connection values plus the safe settings allowed in records."""

    model_id: str
    settings: LLMModelSettings = field(default_factory=LLMModelSettings, repr=False)
    _base_url: str = field(default="", repr=False)
    _api_key: str = field(default="", repr=False)

    @staticmethod
    def _first(env: Mapping[str, str], science_name: str, fallback_name: str) -> str:
        science_value = env.get(science_name, "").strip()
        return science_value or env.get(fallback_name, "").strip()

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "ScienceLLMConfig":
        values = os.environ if env is None else env
        base_url = cls._first(
            values, "BOI_SCIENCE_LLM_BASE_URL", "BOI_LLM_BASE_URL"
        ).rstrip("/")
        model_id = cls._first(values, "BOI_SCIENCE_LLM_MODEL", "BOI_LLM_MODEL")
        api_key = cls._first(values, "BOI_SCIENCE_LLM_API_KEY", "BOI_LLM_API_KEY")
        if not base_url or not model_id:
            raise ScienceInterpretationUnavailable(
                "Science LLM base URL and model must be configured"
            )

        setting_names = {
            "temperature": "TEMPERATURE",
            "top_p": "TOP_P",
            "max_tokens": "MAX_TOKENS",
            "seed": "SEED",
            "timeout_seconds": "TIMEOUT_SECONDS",
        }
        raw_settings: dict[str, str] = {}
        for field_name, suffix in setting_names.items():
            value = cls._first(
                values,
                f"BOI_SCIENCE_LLM_{suffix}",
                f"BOI_LLM_{suffix}",
            )
            if value:
                raw_settings[field_name] = value
        try:
            settings = LLMModelSettings.model_validate(raw_settings)
        except ValueError as exc:
            raise ScienceInterpretationUnavailable(
                "Science LLM generation settings are invalid"
            ) from exc
        return cls(
            model_id=model_id,
            settings=settings,
            _base_url=base_url,
            _api_key=api_key,
        )

    def safe_model_settings(self) -> LLMModelSettings:
        return self.settings.model_copy(deep=True)

    def safe_metadata(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "model_settings": self.settings.model_dump(mode="json"),
        }


_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_FORBIDDEN_OUTPUT_TERMS = {"verdict", "citation", "evidence", "locator"}


def _reject_forbidden_output_fields(value: object, *, path: str = "output") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = _CAMEL_BOUNDARY.sub("_", str(key)).replace("-", "_").lower()
            tokens = tuple(token for token in normalized.split("_") if token)
            if any(
                token.startswith(forbidden)
                for token in tokens
                for forbidden in _FORBIDDEN_OUTPUT_TERMS
            ):
                raise ScienceInterpretationUnavailable(
                    f"forbidden LLM output field at {path}.{key}"
                )
            _reject_forbidden_output_fields(item, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_forbidden_output_fields(item, path=f"{path}[{index}]")


class ScienceLLMClient:
    """Call an OpenAI-compatible server and admit only the extraction schema."""

    def __init__(
        self,
        config: ScienceLLMConfig,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config
        self._transport = transport

    @staticmethod
    def _system_prompt() -> str:
        schema = ScienceInterpretationPayload.model_json_schema()
        return (
            "Extract scientific claim candidates only. Ontology entries are candidate "
            "meanings, never truth or a verdict. Do not output verdicts, citations, "
            "evidence IDs, evidence text, or source locators. Do not fill missing "
            "conditions. Return exactly one JSON value matching this strict schema: "
            + json.dumps(schema, ensure_ascii=False, sort_keys=True)
        )

    def interpret(
        self,
        document_text: str,
        *,
        ontology_candidates: Sequence[Mapping[str, Any]],
    ) -> ScienceLLMResult:
        request_body: dict[str, object] = {
            "model": self.config.model_id,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "document_text": document_text,
                            "ontology_candidates": list(ontology_candidates),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "science_interpretation",
                    "strict": True,
                    "schema": ScienceInterpretationPayload.model_json_schema(),
                },
            },
        }
        generation = self.config.settings.model_dump(exclude_none=True)
        timeout = generation.pop("timeout_seconds", None) or 30.0
        request_body.update(generation)
        headers = {"content-type": "application/json"}
        if self.config._api_key:
            headers["authorization"] = f"Bearer {self.config._api_key}"

        try:
            with httpx.Client(
                transport=self._transport,
                timeout=float(timeout),
            ) as client:
                response = client.post(
                    f"{self.config._base_url}/chat/completions",
                    headers=headers,
                    json=request_body,
                )
                response.raise_for_status()
                envelope = response.json()
            if not isinstance(envelope, Mapping):
                raise ValueError("completion envelope must be an object")
            choices = envelope.get("choices")
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError("completion must contain exactly one choice")
            choice = choices[0]
            if not isinstance(choice, Mapping):
                raise ValueError("completion choice must be an object")
            message = choice.get("message")
            if not isinstance(message, Mapping) or message.get("role") != "assistant":
                raise ValueError("completion choice has no assistant message")
            content = message.get("content")
            if not isinstance(content, str):
                raise ValueError("assistant content must be a JSON string")
            decoded = json.loads(content)
            _reject_forbidden_output_fields(decoded)
            payload = ScienceInterpretationPayload.model_validate(decoded)
        except ScienceInterpretationUnavailable:
            raise
        except (httpx.HTTPError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ScienceInterpretationUnavailable(
                "Science interpretation failed closed"
            ) from exc

        return ScienceLLMResult(
            payload=payload,
            response_digest=sha256_digest(content),
        )
