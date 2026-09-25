"""Knowledge evidence composition; distinct from SQL NULL and Formula truth.

Inputs are atoms already selected and qualified by the knowledge adapter for
the same source/scope/time. This module cannot establish that qualification.
It preserves participating conflicts/unknowns even if the combined state differs.
"""
from dataclasses import dataclass
from typing import Literal

from .filter_expression import FilterExpression, validate_filter_expression


EvidenceState = Literal['supported', 'refuted', 'conflicted', 'unknown']


@dataclass(frozen=True)
class EvidenceAtom:
    atom_id: str
    supporting_refs: tuple[str, ...] = ()
    refuting_refs: tuple[str, ...] = ()
    unknown_reasons: tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.atom_id, str) or not self.atom_id.strip():
            raise ValueError('KNOWLEDGE_EVIDENCE_ATOM_ID_REQUIRED')
        for values in (self.supporting_refs, self.refuting_refs, self.unknown_reasons):
            if (not isinstance(values, tuple) or len(values) > 256
                    or any(not isinstance(v, str) or not v.strip() for v in values)
                    or len(set(values)) != len(values)):
                raise ValueError('KNOWLEDGE_EVIDENCE_REFERENCES_INVALID')
        if not self.supporting_refs and not self.refuting_refs and not self.unknown_reasons:
            raise ValueError('KNOWLEDGE_EVIDENCE_UNKNOWN_REASON_REQUIRED')

    @property
    def state(self) -> EvidenceState:
        return evidence_state(bool(self.supporting_refs), bool(self.refuting_refs))


def evidence_state(supported: bool, refuted: bool) -> EvidenceState:
    if supported:
        return 'conflicted' if refuted else 'supported'
    return 'refuted' if refuted else 'unknown'


@dataclass(frozen=True)
class EvidenceExpressionResult:
    state: EvidenceState
    atoms: tuple[EvidenceAtom, ...]
    conflict_atom_ids: tuple[str, ...]
    unknown_atom_ids: tuple[str, ...]
    semantic_truth_proven: Literal[False] = False


def evaluate_evidence_expression(expression, atoms) -> EvidenceExpressionResult:
    """Apply the documented four evidence states with existing AST budgets."""
    expression = FilterExpression.model_validate(expression)
    # Bound even a generator before evaluating or materializing its remainder.
    bounded = []
    for atom in atoms:
        if len(bounded) == 256:
            raise ValueError('KNOWLEDGE_EVIDENCE_ATOM_LIMIT')
        if not isinstance(atom, EvidenceAtom):
            raise ValueError('KNOWLEDGE_EVIDENCE_ATOM_REQUIRED')
        bounded.append(atom)
    atoms = tuple(bounded)
    if len({a.atom_id for a in atoms}) != len(atoms):
        raise ValueError('KNOWLEDGE_EVIDENCE_ATOM_DUPLICATE')
    validate_filter_expression(expression, len(atoms))

    def visit(node):
        if node.operator == 'filter':
            atom = atoms[node.filter_index]
            return bool(atom.supporting_refs), bool(atom.refuting_refs)
        pairs = [visit(child) for child in node.arguments]
        if node.operator == 'not':
            s, r = pairs[0]
            return r, s
        if node.operator == 'and':
            return all(s for s, _ in pairs), any(r for _, r in pairs)
        return any(s for s, _ in pairs), all(r for _, r in pairs)

    s, r = visit(expression)
    return EvidenceExpressionResult(evidence_state(s, r), atoms,
        tuple(a.atom_id for a in atoms if a.state == 'conflicted'),
        tuple(a.atom_id for a in atoms if a.state == 'unknown'))
