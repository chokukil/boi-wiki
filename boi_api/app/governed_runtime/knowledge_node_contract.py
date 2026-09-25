"""Exact node selection inside an authorized immutable knowledge revision."""
from pydantic import Field

from .semantic_binding_contract import Digest, FrozenContract, Ref, RevisionRef


class KnowledgeNodeRef(FrozenContract):
    asset_revision: RevisionRef
    node_pointer: Ref = Field(description='Exact pointer supplied by the domain node inventory. A revision may contain many distinct definitions.')
    node_digest: Digest = Field(description='Copy the selected node digest from the inventory, never invent or recompute it with language reasoning.')
