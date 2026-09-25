"""Source contract: body bytes never appear in normalized plan material."""
import base64
import hashlib
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, SecretStr, TypeAdapter
from boi_api.app.governed_runtime.semantic_binding_contract import Digest, Ref


class EnvelopeBase(BaseModel):
    model_config = ConfigDict(extra='forbid',frozen=True,hide_input_in_errors=True)
    role: Literal['sql','corporate_metadata','schema','authoritative_document']


class ArtifactEnvelope(EnvelopeBase):
    kind: Literal['artifact_ref']
    artifact_ref: Annotated[str,Field(pattern=r'^SourceArtifact:sha256:[0-9a-f]{64}$')]
    digest: Digest
    # Transport-only migration hint. It cannot alter canonical source
    # bindings, manifest digests, or existing knowledge revisions.
    display_name: Annotated[str, Field(min_length=1, max_length=255,
        pattern=r'^[^/\\\x00-\x1f\x7f]+$')] | None = Field(default=None,exclude=True)


class ConnectorEnvelope(EnvelopeBase):
    kind: Literal['connector_snapshot']
    connector_ref: Ref
    snapshot_digest: Digest
    selector_manifest_ref: Ref


class InlineEnvelope(EnvelopeBase):
    kind: Literal['inline_source']
    media_type: Literal['text/plain','text/csv','application/json','application/yaml','application/sql']
    content_b64: SecretStr = Field(exclude=True,repr=False)

    def source_bytes(self):
        encoded=self.content_b64.get_secret_value()
        if len(encoded)>87384:raise ValueError('INLINE_SOURCE_BYTE_LIMIT')
        try:raw=base64.b64decode(encoded,validate=True)
        except (ValueError, UnicodeError):raise ValueError('INLINE_SOURCE_ENCODING_INVALID') from None
        if not raw or len(raw)>65536:raise ValueError('INLINE_SOURCE_BYTE_LIMIT')
        return raw


class FileSourceEnvelope(InlineEnvelope):
    """Host-uploaded workbook bytes; separate from the small inline text input."""
    kind: Literal['file_source']
    media_type: Literal['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']
    display_name: Annotated[str, Field(min_length=1, max_length=255,
        pattern=r'^[^/\\\x00-\x1f\x7f]+$')] | None = None

    def source_bytes(self):
        encoded=self.content_b64.get_secret_value()
        if len(encoded)>22369624:raise ValueError('FILE_SOURCE_BYTE_LIMIT')
        try:raw=base64.b64decode(encoded,validate=True)
        except (ValueError,UnicodeError):raise ValueError('SOURCE_ENCODING_INVALID') from None
        if not raw or len(raw)>16777216:raise ValueError('FILE_SOURCE_BYTE_LIMIT')
        return raw


SourceEnvelope = Annotated[ArtifactEnvelope|ConnectorEnvelope|InlineEnvelope|FileSourceEnvelope,Field(discriminator='kind')]


def parse_envelope(raw):
    try:return TypeAdapter(SourceEnvelope).validate_python(raw)
    except ValueError:raise ValueError('SOURCE_ENVELOPE_INVALID') from None


def byte_digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
