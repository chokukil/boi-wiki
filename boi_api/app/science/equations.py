"""Closed, digest-bound Equation Knowledge contracts.

The semantic expression in this module is the scientific identity used for
machine checks.  LaTeX and prose readings are display channels only.  This
module deliberately does not import ``models`` or ``rules`` so those modules
can safely carry immutable Equation Knowledge snapshots without an import
cycle.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from boi_api.app.science.digests import sha256_digest


_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_VARIABLE_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_UNSAFE_TEXT_RE = re.compile(
    r"(?:https?://|file://|data:|javascript:|\\(?:href|url|input|include|includegraphics|"
    r"html|class|style|cssId|def|gdef|edef|newcommand|renewcommand|providecommand|"
    r"require|operatorname)\b|<[A-Za-z!/])",
    re.IGNORECASE,
)
_LATEX_COMMAND_RE = re.compile(r"\\([A-Za-z]+)")
_ALLOWED_LATEX_COMMANDS = {
    "approx",
    "alpha",
    "bar",
    "beta",
    "begin",
    "ce",
    "cdot",
    "cdots",
    "chi",
    "delta",
    "Delta",
    "div",
    "end",
    "epsilon",
    "eta",
    "exp",
    "frac",
    "gamma",
    "Gamma",
    "ge",
    "hat",
    "hbar",
    "infty",
    "int",
    "kappa",
    "lambda",
    "Lambda",
    "le",
    "left",
    "ln",
    "log",
    "mathbb",
    "mathbf",
    "mathcal",
    "mathit",
    "mathrm",
    "mathsf",
    "mathtt",
    "max",
    "min",
    "mu",
    "nabla",
    "neq",
    "nu",
    "omega",
    "Omega",
    "overline",
    "partial",
    "phi",
    "Phi",
    "pi",
    "Pi",
    "pm",
    "propto",
    "psi",
    "Psi",
    "rho",
    "right",
    "rightarrow",
    "sigma",
    "Sigma",
    "sqrt",
    "sum",
    "tau",
    "theta",
    "Theta",
    "times",
    "to",
    "underline",
    "upsilon",
    "vec",
    "varphi",
    "varepsilon",
    "vartheta",
    "xi",
    "Xi",
    "zeta",
}
_ALLOWED_LATEX_ENVIRONMENTS = {"matrix", "pmatrix", "bmatrix", "vmatrix", "cases"}

_SEMANTIC_OPERATORS = {
    "variable",
    "literal",
    "constant",
    "negate",
    "add",
    "subtract",
    "multiply",
    "divide",
    "power",
    "function",
    "relation",
    "vector",
    "matrix",
    "derivative",
    "integral",
    "summation",
    "chemical_reaction",
}
_DETERMINISTIC_OPERATORS = {
    "variable",
    "literal",
    "constant",
    "negate",
    "add",
    "subtract",
    "multiply",
    "divide",
    "power",
    "function",
    "relation",
}


class EquationModel(BaseModel):
    """Local closed model base kept independent from the main model graph."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


def _require_identifier(value: str, field_name: str) -> str:
    value = value.strip()
    if not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"{field_name} must be a closed identifier")
    return value


def _require_exact_sha256(value: str, field_name: str) -> str:
    if not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{field_name} must be an exact SHA-256 digest")
    return value


def _text_sha256(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_bounded_text(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must be nonempty")
    if any(ord(character) < 32 and character not in "\n\t" for character in value):
        raise ValueError(f"{field_name} contains control characters")
    return value


def _validate_latex(value: str) -> str:
    _validate_bounded_text(value, "display_latex")
    if _UNSAFE_TEXT_RE.search(value):
        raise ValueError("unsafe or unsupported LaTeX")
    commands = set(_LATEX_COMMAND_RE.findall(value))
    if not commands <= _ALLOWED_LATEX_COMMANDS:
        raise ValueError("unsafe or unsupported LaTeX")
    if value.count("{") != value.count("}") or value.count("{") > 128:
        raise ValueError("unsafe or unsupported LaTeX")
    brace_depth = 0
    for character in value:
        if character == "{":
            brace_depth += 1
            if brace_depth > 32:
                raise ValueError("unsafe or unsupported LaTeX")
        elif character == "}":
            brace_depth -= 1
            if brace_depth < 0:
                raise ValueError("unsafe or unsupported LaTeX")
    for environment in re.findall(r"\\(?:begin|end)\{([^{}]+)\}", value):
        if environment not in _ALLOWED_LATEX_ENVIRONMENTS:
            raise ValueError("unsafe or unsupported LaTeX")
    if value.count(r"\begin") != value.count(r"\end"):
        raise ValueError("unsafe or unsupported LaTeX")
    return value


class DimensionVector(EquationModel):
    """SI base-dimension exponents; all-zero is dimensionless."""

    mass: int = Field(default=0, ge=-12, le=12)
    length: int = Field(default=0, ge=-12, le=12)
    time: int = Field(default=0, ge=-12, le=12)
    electric_current: int = Field(default=0, ge=-12, le=12)
    thermodynamic_temperature: int = Field(default=0, ge=-12, le=12)
    amount_of_substance: int = Field(default=0, ge=-12, le=12)
    luminous_intensity: int = Field(default=0, ge=-12, le=12)

    def values_tuple(self) -> tuple[int, ...]:
        return (
            self.mass,
            self.length,
            self.time,
            self.electric_current,
            self.thermodynamic_temperature,
            self.amount_of_substance,
            self.luminous_intensity,
        )


class ReactionSpecies(EquationModel):
    species_id: str = Field(min_length=1, max_length=128)
    stoichiometric_coefficient: Decimal = Field(gt=0)

    @field_validator("species_id")
    @classmethod
    def valid_species_id(cls, value: str) -> str:
        return _require_identifier(value, "species_id")

    @field_validator("stoichiometric_coefficient")
    @classmethod
    def finite_coefficient(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("stoichiometric coefficient must be finite")
        return value


SemanticOperator = Literal[
    "variable",
    "literal",
    "constant",
    "negate",
    "add",
    "subtract",
    "multiply",
    "divide",
    "power",
    "function",
    "relation",
    "vector",
    "matrix",
    "derivative",
    "integral",
    "summation",
    "chemical_reaction",
]


class SemanticNode(EquationModel):
    """One node in the versioned closed expression tree."""

    op: SemanticOperator
    variable_id: str | None = Field(default=None, max_length=64)
    value: Decimal | None = None
    unit: str | None = Field(default=None, max_length=128)
    dimension: DimensionVector | None = None
    constant: Literal["pi", "e"] | None = None
    operand: SemanticNode | None = None
    left: SemanticNode | None = None
    right: SemanticNode | None = None
    operands: list[SemanticNode] | None = Field(default=None, min_length=1, max_length=32)
    function_name: Literal["sqrt", "exp", "ln", "log10", "abs"] | None = None
    relation: Literal[
        "eq", "approx", "proportional", "lt", "lte", "gt", "gte"
    ] | None = None
    rows: list[list[SemanticNode]] | None = Field(default=None, min_length=1, max_length=16)
    expression: SemanticNode | None = None
    integrand: SemanticNode | None = None
    with_respect_to: str | None = Field(default=None, max_length=64)
    order: int | None = Field(default=None, ge=1, le=8)
    lower: SemanticNode | None = None
    upper: SemanticNode | None = None
    reactants: list[ReactionSpecies] | None = Field(default=None, min_length=1, max_length=32)
    products: list[ReactionSpecies] | None = Field(default=None, min_length=1, max_length=32)
    reversible: bool | None = None

    @field_validator("variable_id", "with_respect_to")
    @classmethod
    def valid_variable_id(cls, value: str | None) -> str | None:
        if value is not None and not _VARIABLE_ID_RE.fullmatch(value):
            raise ValueError("semantic variable identifier is invalid")
        return value

    @field_validator("value")
    @classmethod
    def finite_literal(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and not value.is_finite():
            raise ValueError("semantic literal must be finite")
        return value

    @field_validator("unit")
    @classmethod
    def safe_unit(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = _validate_bounded_text(value, "semantic literal unit").strip()
        if _UNSAFE_TEXT_RE.search(value):
            raise ValueError("semantic literal unit is unsafe")
        return value

    @model_validator(mode="after")
    def closed_shape(self) -> "SemanticNode":
        required: dict[str, set[str]] = {
            "variable": {"variable_id"},
            "literal": {"value"},
            "constant": {"constant"},
            "negate": {"operand"},
            "add": {"left", "right"},
            "subtract": {"left", "right"},
            "multiply": {"left", "right"},
            "divide": {"left", "right"},
            "power": {"left", "right"},
            "function": {"function_name", "operands"},
            "relation": {"relation", "left", "right"},
            "vector": {"operands"},
            "matrix": {"rows"},
            "derivative": {"expression", "with_respect_to", "order"},
            "integral": {"integrand", "with_respect_to"},
            "summation": {"expression", "with_respect_to", "lower", "upper"},
            "chemical_reaction": {"reactants", "products", "reversible"},
        }
        optional: dict[str, set[str]] = {
            "literal": {"unit", "dimension"},
            "integral": {"lower", "upper"},
        }
        present = {
            field_name
            for field_name in type(self).model_fields
            if field_name != "op" and getattr(self, field_name) is not None
        }
        if not required[self.op] <= present:
            raise ValueError(f"semantic {self.op} node is incomplete")
        if not present <= required[self.op] | optional.get(self.op, set()):
            raise ValueError(f"semantic {self.op} node has fields from another operator")
        if self.op == "matrix":
            assert self.rows is not None
            if any(not row or len(row) > 16 for row in self.rows):
                raise ValueError("semantic matrix rows must contain 1 to 16 items")
            widths = {len(row) for row in self.rows}
            if len(widths) != 1:
                raise ValueError("semantic matrix rows must have equal widths")
        if self.op == "function":
            assert self.operands is not None and self.function_name is not None
            expected_arity = 1
            if len(self.operands) != expected_arity:
                raise ValueError(f"semantic function {self.function_name} requires one operand")
        return self


SemanticNode.model_rebuild()


def _child_nodes(node: SemanticNode) -> list[SemanticNode]:
    children: list[SemanticNode] = []
    for name in ("operand", "left", "right", "expression", "integrand", "lower", "upper"):
        child = getattr(node, name)
        if child is not None:
            children.append(child)
    if node.operands:
        children.extend(node.operands)
    if node.rows:
        children.extend(item for row in node.rows for item in row)
    return children


class SemanticExpression(EquationModel):
    schema_version: Literal["science-expression/0.1"]
    root: SemanticNode

    @model_validator(mode="after")
    def bounded_tree(self) -> "SemanticExpression":
        node_count = 0
        stack = [(self.root, 1)]
        while stack:
            node, depth = stack.pop()
            node_count += 1
            if node_count > 256:
                raise ValueError("semantic expression exceeds 256 nodes")
            if depth > 16:
                raise ValueError("semantic expression exceeds depth 16")
            stack.extend((child, depth + 1) for child in _child_nodes(node))
        return self

    def operators(self) -> set[str]:
        operators: set[str] = set()
        stack = [self.root]
        while stack:
            node = stack.pop()
            operators.add(node.op)
            stack.extend(_child_nodes(node))
        return operators

    def variable_ids(self) -> set[str]:
        identifiers: set[str] = set()
        stack = [self.root]
        while stack:
            node = stack.pop()
            if node.op == "variable" and node.variable_id is not None:
                identifiers.add(node.variable_id)
            if node.with_respect_to is not None:
                identifiers.add(node.with_respect_to)
            stack.extend(_child_nodes(node))
        return identifiers


class EquationVariable(EquationModel):
    variable_id: str = Field(min_length=1, max_length=64)
    symbol: str = Field(min_length=1, max_length=32)
    concept_ref: str = Field(min_length=1, max_length=128)
    quantity_kind: str = Field(min_length=1, max_length=128)
    dimension: DimensionVector
    unit: str = Field(min_length=1, max_length=128)
    definition: str = Field(min_length=1, max_length=1024)
    domain: Literal[
        "real", "integer", "complex", "vector", "matrix", "discrete", "chemical_species"
    ]
    sign_constraint: Literal[
        "any", "positive", "nonnegative", "negative", "nonpositive", "nonzero"
    ]

    @field_validator("variable_id")
    @classmethod
    def valid_variable_id(cls, value: str) -> str:
        if not _VARIABLE_ID_RE.fullmatch(value):
            raise ValueError("variable_id is invalid")
        return value

    @field_validator("concept_ref")
    @classmethod
    def valid_concept_ref(cls, value: str) -> str:
        value = _require_identifier(value, "concept_ref")
        if not value.startswith("sci:concept:"):
            raise ValueError("concept_ref must name a Science concept")
        return value

    @field_validator("quantity_kind")
    @classmethod
    def valid_quantity_kind(cls, value: str) -> str:
        return _require_identifier(value, "quantity_kind")

    @field_validator("symbol", "unit", "definition")
    @classmethod
    def safe_text(cls, value: str, info) -> str:
        value = _validate_bounded_text(value, info.field_name).strip()
        if info.field_name in {"symbol", "unit"} and _UNSAFE_TEXT_RE.search(value):
            raise ValueError(f"{info.field_name} is unsafe")
        return value

    @model_validator(mode="after")
    def compatible_domain_and_sign(self) -> "EquationVariable":
        if self.domain in {"complex", "vector", "matrix", "chemical_species"} and (
            self.sign_constraint != "any"
        ):
            raise ValueError("non-scalar variable domains cannot declare an order sign")
        return self


class BoundaryCondition(EquationModel):
    condition_id: str = Field(min_length=1, max_length=128)
    statement: str = Field(min_length=1, max_length=1024)
    variable_id: str | None = Field(default=None, max_length=64)
    operator: Literal["eq", "ne", "lt", "lte", "gt", "gte", "range"]
    value: Decimal | None = None
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    minimum_inclusive: bool | None = None
    maximum_inclusive: bool | None = None
    unit: str | None = Field(default=None, max_length=128)

    @field_validator("condition_id")
    @classmethod
    def valid_condition_id(cls, value: str) -> str:
        return _require_identifier(value, "condition_id")

    @field_validator("variable_id")
    @classmethod
    def valid_variable_id(cls, value: str | None) -> str | None:
        if value is not None and not _VARIABLE_ID_RE.fullmatch(value):
            raise ValueError("boundary variable_id is invalid")
        return value

    @field_validator("value", "minimum", "maximum")
    @classmethod
    def finite_numeric_value(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and not value.is_finite():
            raise ValueError("boundary value must be finite")
        return value

    @model_validator(mode="after")
    def valid_operand(self) -> "BoundaryCondition":
        if self.operator == "range":
            if self.minimum is None or self.maximum is None or self.value is not None:
                raise ValueError("range boundary requires minimum and maximum only")
            if self.minimum > self.maximum:
                raise ValueError("range boundary minimum cannot exceed maximum")
            if self.minimum_inclusive is None or self.maximum_inclusive is None:
                raise ValueError("range boundary requires inclusive flags")
        elif (
            self.value is None
            or self.minimum is not None
            or self.maximum is not None
            or self.minimum_inclusive is not None
            or self.maximum_inclusive is not None
        ):
            raise ValueError("scalar boundary requires only value")
        return self


class ApproximationMetadata(EquationModel):
    approximation_kind: Literal[
        "asymptotic", "truncation", "linearization", "numerical", "continuum_model"
    ]
    error_statement: str = Field(min_length=1, max_length=2048)
    maximum_absolute_error: Decimal | None = Field(default=None, ge=0)
    error_unit: str | None = Field(default=None, max_length=128)
    validity_conditions: list[str] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def error_unit_matches_bound(self) -> "ApproximationMetadata":
        if (self.maximum_absolute_error is None) != (self.error_unit is None):
            raise ValueError("approximation numeric error and unit must be provided together")
        return self


class EmpiricalFitMetadata(EquationModel):
    fit_method: Literal[
        "linear_regression", "nonlinear_regression", "least_squares", "vendor_curve"
    ]
    fit_source_evidence_ref: str = Field(min_length=1, max_length=128)
    fit_range: list[BoundaryCondition] = Field(min_length=1, max_length=32)
    error_statement: str = Field(min_length=1, max_length=2048)
    r_squared: Decimal | None = Field(default=None, ge=0, le=1)
    rmse: Decimal | None = Field(default=None, ge=0)
    rmse_unit: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def rmse_unit_matches_value(self) -> "EmpiricalFitMetadata":
        if (self.rmse is None) != (self.rmse_unit is None):
            raise ValueError("empirical fit RMSE and unit must be provided together")
        return self


class OriginalNotationMapping(EquationModel):
    source_symbol: str = Field(min_length=1, max_length=64)
    variable_id: str = Field(min_length=1, max_length=64)

    @field_validator("source_symbol")
    @classmethod
    def safe_source_symbol(cls, value: str) -> str:
        value = _validate_bounded_text(value, "source_symbol").strip()
        if _UNSAFE_TEXT_RE.search(value):
            raise ValueError("source_symbol is unsafe")
        return value

    @field_validator("variable_id")
    @classmethod
    def valid_variable_id(cls, value: str) -> str:
        if not _VARIABLE_ID_RE.fullmatch(value):
            raise ValueError("notation variable_id is invalid")
        return value


class EquationVariableContext(EquationModel):
    source_symbol: str = Field(min_length=1, max_length=64)
    definition: str = Field(min_length=1, max_length=2048)
    unit_text: str = Field(min_length=1, max_length=256)


class EquationEvidenceLocator(EquationModel):
    medium: Literal["pdf", "html", "api_json"]
    resource_url: str = Field(min_length=1, max_length=2048)
    content_hash: str
    exact: Literal[True]
    section: str | None = Field(default=None, max_length=512)
    pdf_page_index: int | None = Field(default=None, ge=0)
    printed_page: str | None = Field(default=None, max_length=64)
    heading: str | None = Field(default=None, max_length=512)
    sentence_ordinal: int | None = Field(default=None, ge=1)
    field_path: str | None = Field(default=None, max_length=512)
    equation_label: str = Field(min_length=1, max_length=128)

    @field_validator("resource_url")
    @classmethod
    def https_resource_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("equation Evidence resource_url must be credential-free HTTPS")
        return value

    @field_validator("content_hash")
    @classmethod
    def exact_content_hash(cls, value: str) -> str:
        return _require_exact_sha256(value, "content_hash")

    @model_validator(mode="after")
    def medium_specific_locator(self) -> "EquationEvidenceLocator":
        required = {
            "pdf": (self.section, self.pdf_page_index, self.printed_page),
            "html": (self.heading, self.sentence_ordinal),
            "api_json": (self.field_path,),
        }[self.medium]
        if any(item is None or item == "" for item in required):
            raise ValueError("equation Evidence locator is incomplete for its medium")
        allowed_fields = {
            "pdf": {"section", "pdf_page_index", "printed_page"},
            "html": {"heading", "sentence_ordinal"},
            "api_json": {"field_path"},
        }[self.medium]
        present_fields = {
            name
            for name in (
                "section",
                "pdf_page_index",
                "printed_page",
                "heading",
                "sentence_ordinal",
                "field_path",
            )
            if getattr(self, name) is not None
        }
        if not present_fields <= allowed_fields:
            raise ValueError("equation Evidence locator mixes media-specific coordinates")
        return self


class EquationTranscription(EquationModel):
    transcription_id: str = Field(min_length=1, max_length=128)
    original_notation: str = Field(min_length=1, max_length=4096)
    original_notation_hash: str
    variable_context: list[EquationVariableContext] = Field(max_length=64)
    variable_context_hash: str
    coordinate_convention: str = Field(min_length=1, max_length=2048)
    sign_convention: str = Field(min_length=1, max_length=2048)
    unit_convention: str = Field(min_length=1, max_length=2048)
    conventions_hash: str
    relation_notation: Literal[
        "equals", "approximately_equals", "inequality", "definition", "proportionality", "reaction"
    ]
    transcription_method: Literal["manual", "ocr_reviewed"]
    review_state: Literal["reviewed"]
    reviewer: str = Field(min_length=1, max_length=128)
    reviewed_at: str = Field(min_length=1, max_length=64)
    semantic_expression_digest: str
    transcription_digest: str

    @model_validator(mode="before")
    @classmethod
    def exact_digests_before_coercion(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        original = value.get("original_notation")
        if isinstance(original, str) and value.get("original_notation_hash") != _text_sha256(original):
            raise ValueError("original_notation_hash must match exact UTF-8 transcription")
        context = value.get("variable_context")
        if isinstance(context, list) and value.get("variable_context_hash") != sha256_digest(context):
            raise ValueError("variable_context_hash must match exact variable context")
        conventions = {
            "coordinate_convention": value.get("coordinate_convention"),
            "sign_convention": value.get("sign_convention"),
            "unit_convention": value.get("unit_convention"),
        }
        if value.get("conventions_hash") != sha256_digest(conventions):
            raise ValueError("conventions_hash must match exact conventions")
        digest_payload = {key: item for key, item in value.items() if key != "transcription_digest"}
        if value.get("transcription_digest") != sha256_digest(digest_payload):
            raise ValueError("transcription_digest must match exact transcription")
        return value

    @field_validator(
        "original_notation_hash",
        "variable_context_hash",
        "conventions_hash",
        "semantic_expression_digest",
        "transcription_digest",
    )
    @classmethod
    def exact_hash(cls, value: str, info) -> str:
        return _require_exact_sha256(value, info.field_name)

    @field_validator("reviewed_at")
    @classmethod
    def timezone_aware_review_time(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("reviewed_at must be ISO-8601") from exc
        if parsed.tzinfo is None:
            raise ValueError("reviewed_at must include a timezone")
        return value

    @model_validator(mode="after")
    def canonical_transcription_digest(self) -> "EquationTranscription":
        payload = self.model_dump(
            mode="json", exclude={"transcription_digest"}, exclude_unset=True
        )
        if self.transcription_digest != sha256_digest(payload):
            raise ValueError("transcription_digest must match canonical transcription")
        return self


class EquationEvidenceUse(EquationModel):
    evidence_ref: str = Field(min_length=1, max_length=128)
    purpose: str = Field(min_length=1, max_length=2048)
    claim_scope_hash: str
    locator: EquationEvidenceLocator
    locator_digest: str
    transcription: EquationTranscription

    @field_validator("evidence_ref")
    @classmethod
    def valid_evidence_ref(cls, value: str) -> str:
        value = _require_identifier(value, "evidence_ref")
        if not value.startswith("sci:evidence:"):
            raise ValueError("evidence_ref must name Science Evidence")
        return value

    @field_validator("claim_scope_hash", "locator_digest")
    @classmethod
    def exact_hash(cls, value: str, info) -> str:
        return _require_exact_sha256(value, info.field_name)

    @model_validator(mode="after")
    def exact_locator_digest(self) -> "EquationEvidenceUse":
        if self.locator_digest != sha256_digest(
            self.locator.model_dump(mode="json", exclude_unset=True)
        ):
            raise ValueError("locator_digest must match exact equation Evidence locator")
        return self


class EquationEvaluatorLink(EquationModel):
    evaluator_id: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=32)
    expression_schema_version: Literal["science-expression/0.1"]
    allowed_operators: list[SemanticOperator] = Field(min_length=1, max_length=32)
    evaluator_digest: str

    @field_validator("evaluator_id")
    @classmethod
    def valid_evaluator_id(cls, value: str) -> str:
        return _require_identifier(value, "evaluator_id")

    @field_validator("evaluator_digest")
    @classmethod
    def exact_evaluator_digest(cls, value: str) -> str:
        return _require_exact_sha256(value, "evaluator_digest")

    @model_validator(mode="after")
    def unique_reviewed_operator_allowlist(self) -> "EquationEvaluatorLink":
        if len(self.allowed_operators) != len(set(self.allowed_operators)):
            raise ValueError("evaluator allowed_operators must be unique")
        if not set(self.allowed_operators) <= _DETERMINISTIC_OPERATORS:
            raise ValueError("evaluator contains operators not eligible for deterministic use")
        return self


def _dimension_add(left: tuple[int, ...], right: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(a + b for a, b in zip(left, right, strict=True))


def _dimension_subtract(left: tuple[int, ...], right: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(a - b for a, b in zip(left, right, strict=True))


_DIMENSIONLESS = (0, 0, 0, 0, 0, 0, 0)


def _infer_dimension(
    node: SemanticNode,
    variable_dimensions: dict[str, tuple[int, ...]],
    *,
    allow_undetermined_fractional_power: bool = False,
) -> tuple[int, ...] | None:
    if node.op == "variable":
        assert node.variable_id is not None
        return variable_dimensions[node.variable_id]
    if node.op == "literal":
        return node.dimension.values_tuple() if node.dimension is not None else _DIMENSIONLESS
    if node.op == "constant":
        return _DIMENSIONLESS
    if node.op == "negate":
        assert node.operand is not None
        return _infer_dimension(
            node.operand,
            variable_dimensions,
            allow_undetermined_fractional_power=allow_undetermined_fractional_power,
        )
    if node.op in {"add", "subtract", "relation"}:
        assert node.left is not None and node.right is not None
        left = _infer_dimension(node.left, variable_dimensions)
        right = _infer_dimension(
            node.right,
            variable_dimensions,
            allow_undetermined_fractional_power=(
                node.op == "relation" and node.relation == "proportional"
            ),
        )
        if node.op == "relation" and node.relation == "proportional":
            return _DIMENSIONLESS
        if left is not None and right is not None and left != right:
            raise ValueError("semantic expression is dimensionally inconsistent")
        return _DIMENSIONLESS if node.op == "relation" else left
    if node.op in {"multiply", "divide"}:
        assert node.left is not None and node.right is not None
        left = _infer_dimension(
            node.left,
            variable_dimensions,
            allow_undetermined_fractional_power=allow_undetermined_fractional_power,
        )
        right = _infer_dimension(
            node.right,
            variable_dimensions,
            allow_undetermined_fractional_power=allow_undetermined_fractional_power,
        )
        if left is None or right is None:
            return None
        return _dimension_add(left, right) if node.op == "multiply" else _dimension_subtract(left, right)
    if node.op == "power":
        assert node.left is not None and node.right is not None
        base = _infer_dimension(
            node.left,
            variable_dimensions,
            allow_undetermined_fractional_power=allow_undetermined_fractional_power,
        )
        exponent_dimension = _infer_dimension(node.right, variable_dimensions)
        if exponent_dimension != _DIMENSIONLESS:
            raise ValueError("semantic power exponent must be dimensionless")
        if node.right.op != "literal" or node.right.value is None:
            if base != _DIMENSIONLESS:
                raise ValueError("dimensionful semantic power requires a literal exponent")
            return _DIMENSIONLESS
        exponent = node.right.value
        if exponent != exponent.to_integral_value():
            if base != _DIMENSIONLESS:
                if allow_undetermined_fractional_power:
                    return None
                raise ValueError("fractional semantic power requires a dimensionless base")
            return _DIMENSIONLESS
        return tuple(item * int(exponent) for item in base) if base is not None else None
    if node.op == "function":
        assert node.operands is not None and node.function_name is not None
        operand = _infer_dimension(node.operands[0], variable_dimensions)
        if node.function_name == "abs":
            return operand
        if node.function_name == "sqrt":
            if operand is None:
                return None
            if any(item % 2 for item in operand):
                raise ValueError("semantic square root has nonintegral dimensions")
            return tuple(item // 2 for item in operand)
        if operand != _DIMENSIONLESS:
            raise ValueError("semantic transcendental function requires a dimensionless operand")
        return _DIMENSIONLESS
    if node.op in {"vector", "matrix"}:
        items = node.operands or [item for row in (node.rows or []) for item in row]
        dimensions = [_infer_dimension(item, variable_dimensions) for item in items]
        known = [item for item in dimensions if item is not None]
        if known and any(item != known[0] for item in known[1:]):
            raise ValueError("semantic vector or matrix is dimensionally inconsistent")
        return known[0] if known else None
    if node.op == "derivative":
        assert node.expression is not None and node.with_respect_to is not None and node.order is not None
        expression = _infer_dimension(node.expression, variable_dimensions)
        respect = variable_dimensions[node.with_respect_to]
        if expression is None:
            return None
        result = expression
        for _ in range(node.order):
            result = _dimension_subtract(result, respect)
        return result
    if node.op == "integral":
        assert node.integrand is not None and node.with_respect_to is not None
        integrand = _infer_dimension(node.integrand, variable_dimensions)
        if integrand is None:
            return None
        return _dimension_add(integrand, variable_dimensions[node.with_respect_to])
    if node.op == "summation":
        assert node.expression is not None
        return _infer_dimension(node.expression, variable_dimensions)
    if node.op == "chemical_reaction":
        return None
    raise ValueError("unsupported semantic operator")


def _node_is_nonzero(node: SemanticNode, nonzero_variable_ids: set[str]) -> bool:
    if node.op == "literal":
        return node.value is not None and node.value != 0
    if node.op == "constant":
        return True
    if node.op == "variable":
        return node.variable_id in nonzero_variable_ids
    if node.op == "negate":
        return node.operand is not None and _node_is_nonzero(
            node.operand, nonzero_variable_ids
        )
    if node.op in {"multiply", "divide"}:
        return (
            node.left is not None
            and node.right is not None
            and _node_is_nonzero(node.left, nonzero_variable_ids)
            and _node_is_nonzero(node.right, nonzero_variable_ids)
        )
    if node.op == "power":
        return node.left is not None and _node_is_nonzero(
            node.left, nonzero_variable_ids
        )
    if node.op == "function" and node.function_name == "exp":
        return True
    if node.op == "function" and node.function_name == "abs":
        return bool(node.operands) and _node_is_nonzero(
            node.operands[0], nonzero_variable_ids
        )
    return False


def _validate_deterministic_singularities(
    expression: SemanticExpression, nonzero_variable_ids: set[str]
) -> None:
    stack = [expression.root]
    while stack:
        node = stack.pop()
        if node.op == "divide":
            assert node.right is not None
            if not _node_is_nonzero(node.right, nonzero_variable_ids):
                raise ValueError(
                    "deterministic_rule contains a singular denominator without a nonzero domain"
                )
        if node.op == "power" and node.right is not None and node.right.op == "literal":
            if (
                node.right.value is not None
                and node.right.value < 0
                and node.left is not None
                and not _node_is_nonzero(node.left, nonzero_variable_ids)
            ):
                raise ValueError(
                    "deterministic_rule contains a singular negative power without a nonzero domain"
                )
        stack.extend(_child_nodes(node))


def _expected_relation_notations(
    role: str, expression: SemanticExpression
) -> set[str]:
    root = expression.root
    if root.op == "chemical_reaction":
        return {"reaction"}
    if root.op != "relation":
        return {"definition"} if role == "definition" else {"equals"}
    if root.relation == "eq":
        return {"equals", "definition"} if role == "definition" else {"equals"}
    if root.relation == "approx":
        return {"approximately_equals"}
    if root.relation == "proportional":
        return {"proportionality"}
    return {"inequality"}


class ScienceEquationKnowledge(EquationModel):
    """One reviewed equation package embedded only in Science Knowledge."""

    equation_id: str = Field(min_length=1, max_length=128)
    scientific_role: Literal[
        "definition",
        "invariant",
        "law",
        "derived_model",
        "approximation",
        "empirical_fit",
        "qualified_relation",
    ]
    decision_use: Literal["explanation_only", "deterministic_rule", "formal_reference"]
    semantic_expression: SemanticExpression
    display_latex: str = Field(min_length=1, max_length=4096)
    plain_text: str = Field(min_length=1, max_length=4096)
    accessibility_reading: str = Field(min_length=1, max_length=1000)
    variables: list[EquationVariable] = Field(max_length=64)
    assumptions: list[str] = Field(max_length=64)
    applicability: list[str] = Field(min_length=1, max_length=64)
    invalid_outside: list[str] = Field(min_length=1, max_length=64)
    boundary_conditions: list[BoundaryCondition] = Field(max_length=64)
    approximation: ApproximationMetadata | None = None
    empirical_fit: EmpiricalFitMetadata | None = None
    original_notation_mapping: list[OriginalNotationMapping] = Field(max_length=64)
    evidence_uses: list[EquationEvidenceUse] = Field(min_length=1, max_length=32)
    evaluator: EquationEvaluatorLink | None = None
    equation_digest: str

    @model_validator(mode="before")
    @classmethod
    def exact_equation_digest_before_coercion(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        digest_payload = {key: item for key, item in value.items() if key != "equation_digest"}
        if value.get("equation_digest") != sha256_digest(digest_payload):
            raise ValueError("equation_digest must match the exact Equation Knowledge package")
        return value

    @field_validator("equation_id")
    @classmethod
    def valid_equation_id(cls, value: str) -> str:
        value = _require_identifier(value, "equation_id")
        if not value.startswith("sci:equation:"):
            raise ValueError("equation_id must name Science Equation Knowledge")
        return value

    @field_validator("equation_digest")
    @classmethod
    def exact_equation_digest(cls, value: str) -> str:
        return _require_exact_sha256(value, "equation_digest")

    @field_validator("display_latex")
    @classmethod
    def safe_display_latex(cls, value: str) -> str:
        return _validate_latex(value)

    @field_validator("plain_text", "accessibility_reading")
    @classmethod
    def safe_display_fallback(cls, value: str, info) -> str:
        return _validate_bounded_text(value, info.field_name)

    @field_validator("assumptions", "applicability", "invalid_outside")
    @classmethod
    def nonempty_unique_statements(cls, value: list[str], info) -> list[str]:
        normalized = [_validate_bounded_text(item, info.field_name).strip() for item in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError(f"{info.field_name} must be unique")
        return normalized

    @model_validator(mode="after")
    def scientific_integrity_contract(self) -> "ScienceEquationKnowledge":
        variable_ids = [item.variable_id for item in self.variables]
        symbols = [item.symbol for item in self.variables]
        if len(variable_ids) != len(set(variable_ids)):
            raise ValueError("equation variable_id values must be unique")
        if len(symbols) != len(set(symbols)):
            raise ValueError("equation symbols must be unambiguous")
        semantic_variables = self.semantic_expression.variable_ids()
        if semantic_variables != set(variable_ids):
            raise ValueError("semantic variables must exactly match declared variables")

        mapped_ids = [item.variable_id for item in self.original_notation_mapping]
        source_symbols = [item.source_symbol for item in self.original_notation_mapping]
        if set(mapped_ids) != set(variable_ids) or len(mapped_ids) != len(set(mapped_ids)):
            raise ValueError("original notation must map every variable exactly once")
        if len(source_symbols) != len(set(source_symbols)):
            raise ValueError("original notation source symbols must be unique")

        evidence_refs: list[str] = []
        semantic_digest = sha256_digest(
            self.semantic_expression.model_dump(mode="json", exclude_unset=True)
        )
        for use in self.evidence_uses:
            evidence_refs.append(use.evidence_ref)
            if use.transcription.semantic_expression_digest != semantic_digest:
                raise ValueError("transcription semantic_expression_digest does not match")
            context_symbols = [
                item.source_symbol for item in use.transcription.variable_context
            ]
            if (
                set(context_symbols) != set(source_symbols)
                or len(context_symbols) != len(set(context_symbols))
            ):
                raise ValueError(
                    "Evidence variable context must exactly match original notation"
                )
            expected_notations = _expected_relation_notations(
                self.scientific_role, self.semantic_expression
            )
            if use.transcription.relation_notation not in expected_notations:
                raise ValueError(
                    "Evidence relation notation does not match the semantic expression"
                )
        if len(evidence_refs) != len(set(evidence_refs)):
            raise ValueError("equation Evidence uses must be unique")

        unknown_boundary_ids = {
            item.variable_id
            for item in self.boundary_conditions
            if item.variable_id is not None and item.variable_id not in set(variable_ids)
        }
        if unknown_boundary_ids:
            raise ValueError("boundary conditions reference undeclared variables")

        variable_dimensions = {
            item.variable_id: item.dimension.values_tuple() for item in self.variables
        }
        _infer_dimension(self.semantic_expression.root, variable_dimensions)

        if self.scientific_role == "approximation" and self.approximation is None:
            raise ValueError("approximation role requires approximation metadata")
        if self.scientific_role == "empirical_fit" and self.empirical_fit is None:
            raise ValueError("empirical_fit role requires empirical_fit metadata")
        if self.empirical_fit is not None:
            if self.empirical_fit.fit_source_evidence_ref not in set(evidence_refs):
                raise ValueError("empirical fit source must be an exact Equation Evidence use")

        operators = self.semantic_expression.operators()
        if not operators <= _SEMANTIC_OPERATORS:
            raise ValueError("semantic expression contains unsupported operators")
        if self.decision_use == "deterministic_rule":
            if self.evaluator is None:
                raise ValueError("deterministic_rule requires an explicit reviewed evaluator")
            if (
                self.semantic_expression.root.op != "relation"
                or self.semantic_expression.root.relation != "eq"
            ):
                raise ValueError(
                    "deterministic_rule requires an exact equality semantic root"
                )
            if not operators <= _DETERMINISTIC_OPERATORS:
                raise ValueError("deterministic_rule cannot use unsupported expression operators")
            if not operators <= set(self.evaluator.allowed_operators):
                raise ValueError("deterministic_rule operators must be explicitly allowlisted")
            nonzero_variable_ids = {
                item.variable_id
                for item in self.variables
                if item.sign_constraint in {"positive", "negative", "nonzero"}
            }
            for condition in self.boundary_conditions:
                if condition.variable_id is None:
                    continue
                if condition.operator in {"gt", "lt"} and condition.value == 0:
                    nonzero_variable_ids.add(condition.variable_id)
                elif condition.operator == "ne" and condition.value == 0:
                    nonzero_variable_ids.add(condition.variable_id)
                elif condition.operator == "range":
                    assert condition.minimum is not None and condition.maximum is not None
                    if condition.minimum > 0 or condition.maximum < 0:
                        nonzero_variable_ids.add(condition.variable_id)
            _validate_deterministic_singularities(
                self.semantic_expression, nonzero_variable_ids
            )
        elif self.evaluator is not None:
            raise ValueError("an evaluator link is allowed only for deterministic_rule")
        if self.equation_digest != self.computed_digest():
            raise ValueError("equation_digest must match the canonical Equation Knowledge package")
        return self

    def computed_digest(self) -> str:
        """Return the canonical digest of the validated package without its digest field."""

        return sha256_digest(
            self.model_dump(
                mode="json", exclude={"equation_digest"}, exclude_unset=True
            )
        )


def validate_equation_collection(value: Any) -> list[str]:
    """Validate a Knowledge ``equations`` collection for the sci-profile."""

    if not isinstance(value, list) or not value:
        return ["science.equations must be a nonempty list when present"]
    equations: list[ScienceEquationKnowledge] = []
    for item in value:
        try:
            equations.append(ScienceEquationKnowledge.model_validate(item))
        except (ValueError, TypeError):
            return ["science.equations items must satisfy the closed Equation Knowledge schema"]
    equation_ids = [item.equation_id for item in equations]
    if len(equation_ids) != len(set(equation_ids)):
        return ["science.equations equation_id values must be unique"]
    return []


__all__ = [
    "ApproximationMetadata",
    "BoundaryCondition",
    "DimensionVector",
    "EmpiricalFitMetadata",
    "EquationEvidenceLocator",
    "EquationEvidenceUse",
    "EquationEvaluatorLink",
    "EquationTranscription",
    "EquationVariable",
    "ScienceEquationKnowledge",
    "SemanticExpression",
    "SemanticNode",
    "validate_equation_collection",
]
