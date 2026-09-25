"""Additive orientation contract for deterministic relationship quality receipts."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class DirectionalQualityScope(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    contract: Literal['boi/directional-relationship-quality@2'] = 'boi/directional-relationship-quality@2'
    root_endpoint_ref: str = Field(min_length=1)
    target_endpoint_ref: str = Field(min_length=1)
    foreign_key_endpoint_ref: str = Field(min_length=1)
    unique_endpoint_ref: str = Field(min_length=1)
    effective_cardinality: Literal['one_to_many','many_to_one','one_to_one']
    scanned_endpoint_ref: str
    source_snapshot_digest: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')
    physical_schema_digest: str | None = Field(default=None,
        pattern=r'^sha256:[0-9a-f]{64}$',exclude_if=lambda value: value is None)
    mapping_closure_digest: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')
    evaluator_code_digest: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')
    acl_propagation: Literal['INTERSECTION','ROOT_ONLY','RELATIONSHIP_POLICY']
    root_rows: int = Field(ge=0)
    unique_endpoint_null_key_rows: int = Field(ge=0)

    @model_validator(mode='after')
    def coherent_endpoints(self):
        if (self.root_endpoint_ref == self.target_endpoint_ref
            or self.foreign_key_endpoint_ref == self.unique_endpoint_ref
            or {self.root_endpoint_ref,self.target_endpoint_ref} != {self.foreign_key_endpoint_ref,self.unique_endpoint_ref}
            or self.scanned_endpoint_ref != self.foreign_key_endpoint_ref):
            raise ValueError('QUALITY_ENDPOINT_SCOPE_INVALID')
        if self.effective_cardinality != 'one_to_one':
            expected = 'many_to_one' if self.root_endpoint_ref == self.foreign_key_endpoint_ref else 'one_to_many'
            if self.effective_cardinality != expected:
                raise ValueError('QUALITY_CARDINALITY_SCOPE_INVALID')
        return self
