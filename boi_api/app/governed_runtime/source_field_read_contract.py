"""Bounded pages of already registered source fields, without interpretation."""
from pydantic import Field, model_validator

from .semantic_binding_contract import FrozenContract, Ref
from .source_envelope import ArtifactEnvelope


class SourceFieldPage(FrozenContract):
    span_ref: Ref
    offset: int = Field(default=0, ge=0, strict=True)
    limit: int = Field(default=4096, ge=1, le=8192, strict=True)


class SourceFieldBatchReadRequest(FrozenContract):
    reference: ArtifactEnvelope
    fields: tuple[SourceFieldPage, ...] = Field(min_length=1, max_length=128)
    max_characters: int = Field(default=32768, ge=1, le=65536, strict=True)

    @model_validator(mode='after')
    def unique_fields(self):
        if len({f.span_ref for f in self.fields}) != len(self.fields):
            raise ValueError('SOURCE_FIELD_BATCH_DUPLICATE')
        return self
