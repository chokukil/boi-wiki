"""Deterministic quantity validation using one locked Pint registry."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pint

from boi_api.app.science.models import ClaimQuantity, ConversionKind, ScienceModel


class InvalidQuantityError(ValueError):
    """A quantity cannot be parsed into a finite value and defined unit."""


class IncompatibleDimensionsError(InvalidQuantityError):
    """Two quantities cannot be compared because their dimensions differ."""


class AmbiguousUnitError(InvalidQuantityError):
    """A token has a domain meaning that conflicts with SI-prefix parsing."""


class UnsupportedConversionError(InvalidQuantityError):
    """A conversion kind has no qualified deterministic implementation."""


class UnregisteredConversionError(InvalidQuantityError):
    """No exact allowlisted conversion is registered for the requested pair."""


class NormalizedQuantity(ScienceModel):
    """A finite quantity represented in Pint base units."""

    magnitude: Decimal
    unit: str
    dimensionality: str


class ConversionDefinition(ScienceModel):
    """One immutable multiplicative or affine conversion allowlist entry."""

    conversion_id: str
    kind: ConversionKind
    source_unit: str
    target_unit: str
    scale: Decimal
    offset: Decimal = Decimal("0")


class ConversionRegistry:
    """A closed registry of reviewed, Decimal-only unit conversions."""

    def __init__(self, definitions: tuple[ConversionDefinition, ...]):
        keyed: dict[tuple[str, str, ConversionKind], ConversionDefinition] = {}
        for definition in definitions:
            key = (definition.source_unit, definition.target_unit, definition.kind)
            if key in keyed:
                raise ValueError(f"duplicate conversion registration: {definition.conversion_id}")
            if definition.kind not in {ConversionKind.MULTIPLICATIVE, ConversionKind.AFFINE}:
                raise UnsupportedConversionError(
                    f"{definition.kind.value} conversion is unsupported"
                )
            keyed[key] = definition
        self._definitions = keyed

    def convert(
        self,
        value: Decimal | int | str,
        source_unit: str,
        target_unit: str,
        *,
        kind: ConversionKind,
        interval: bool = False,
        conversion_id: str | None = None,
    ) -> Decimal:
        try:
            magnitude = Decimal(str(value))
        except (ArithmeticError, ValueError) as exc:
            raise InvalidQuantityError("conversion value must be finite") from exc
        if not magnitude.is_finite():
            raise InvalidQuantityError("conversion value must be finite")
        if kind is ConversionKind.LOGARITHMIC:
            raise UnsupportedConversionError("logarithmic conversion is unsupported")
        definition = self._definitions.get((source_unit, target_unit, kind))
        if definition is None or (
            conversion_id is not None and definition.conversion_id != conversion_id
        ):
            if kind is ConversionKind.PROCEDURE_DEFINED:
                raise UnregisteredConversionError("procedure conversion is unregistered")
            raise UnregisteredConversionError(
                f"unregistered {kind.value} conversion: {source_unit} -> {target_unit}"
            )
        offset = Decimal("0") if interval else definition.offset
        return magnitude * definition.scale + offset


conversion_registry = ConversionRegistry(
    tuple(
        ConversionDefinition(
            conversion_id=conversion_id,
            kind=kind,
            source_unit=source_unit,
            target_unit=target_unit,
            scale=scale,
            offset=offset,
        )
        for conversion_id, kind, source_unit, target_unit, scale, offset in (
            (
                "sci-conversion:centimeter-meter",
                ConversionKind.MULTIPLICATIVE,
                "centimeter",
                "meter",
                Decimal("0.01"),
                Decimal("0"),
            ),
            (
                "sci-conversion:meter-centimeter",
                ConversionKind.MULTIPLICATIVE,
                "meter",
                "centimeter",
                Decimal("100"),
                Decimal("0"),
            ),
            *(
                (
                    "sci-conversion:celsius-kelvin",
                    ConversionKind.AFFINE,
                    source,
                    target,
                    Decimal("1"),
                    Decimal("273.15"),
                )
                for source in ("°C", "degC", "degree_Celsius")
                for target in ("K", "kelvin")
            ),
            *(
                (
                    "sci-conversion:kelvin-celsius",
                    ConversionKind.AFFINE,
                    source,
                    target,
                    Decimal("1"),
                    Decimal("-273.15"),
                )
                for source in ("K", "kelvin")
                for target in ("°C", "degC", "degree_Celsius")
            ),
        )
    )
)


def convert_value(
    value: Decimal | int | str,
    source_unit: str,
    target_unit: str,
    *,
    kind: ConversionKind,
    interval: bool = False,
    conversion_id: str | None = None,
) -> Decimal:
    """Convert only through the immutable reviewed registry."""

    return conversion_registry.convert(
        value,
        source_unit,
        target_unit,
        kind=kind,
        interval=interval,
        conversion_id=conversion_id,
    )


class LockedUnitRegistry(pint.UnitRegistry):
    """A registry whose bundled definitions cannot be extended after startup."""

    _science_locked: bool

    def __init__(self) -> None:
        self._science_locked = False
        super().__init__(
            filename="",
            autoconvert_offset_to_baseunit=True,
            cache_folder=None,
        )

    def _after_init(self) -> None:
        super()._after_init()
        self._science_locked = True

    def load_definitions(self, file: str | Path, is_resource: bool = False) -> Any:
        if self._science_locked:
            raise PermissionError("Science unit registry is locked")
        return super().load_definitions(file, is_resource=is_resource)

    def define(self, definition: Any) -> None:
        if self._science_locked:
            raise PermissionError("Science unit registry is locked")
        return super().define(definition)


ureg = LockedUnitRegistry()

_AMBIGUOUS_UNIT_TOKENS = frozenset({"pH"})


def _reject_ambiguous_unit(unit: str) -> None:
    if unit in _AMBIGUOUS_UNIT_TOKENS:
        raise AmbiguousUnitError(f"ambiguous unit token: {unit}")


def _validated_claim_quantity(quantity: ClaimQuantity | dict[str, object]) -> ClaimQuantity:
    raw_value = quantity.value if isinstance(quantity, ClaimQuantity) else quantity.get("value")
    try:
        if raw_value is not None and not Decimal(str(raw_value)).is_finite():
            raise InvalidQuantityError("quantity magnitude must be finite")
    except InvalidQuantityError:
        raise
    except (ArithmeticError, ValueError):
        pass
    try:
        parsed = quantity if isinstance(quantity, ClaimQuantity) else ClaimQuantity.model_validate(quantity)
    except (TypeError, ValueError) as exc:
        raise InvalidQuantityError("invalid quantity") from exc
    if not parsed.value.is_finite():
        raise InvalidQuantityError("quantity magnitude must be finite")
    return parsed


def _pint_quantity(quantity: ClaimQuantity | dict[str, object]) -> pint.Quantity:
    parsed = _validated_claim_quantity(quantity)
    _reject_ambiguous_unit(parsed.unit)
    try:
        if parsed.unit in {"°C", "degC", "degree_Celsius"}:
            kelvin = convert_value(
                parsed.value,
                parsed.unit,
                "kelvin",
                kind=ConversionKind.AFFINE,
            )
            result = ureg.Quantity(kelvin, "kelvin")
        else:
            result = ureg.Quantity(parsed.value, parsed.unit)
    except (pint.UndefinedUnitError, ValueError, TypeError) as exc:
        raise InvalidQuantityError(f"undefined unit: {parsed.unit}") from exc
    try:
        result = result.to_base_units()
    except (pint.DimensionalityError, ValueError, TypeError) as exc:
        raise InvalidQuantityError(f"invalid unit conversion: {parsed.unit}") from exc
    magnitude = Decimal(str(result.magnitude))
    if not magnitude.is_finite():
        raise InvalidQuantityError("normalized quantity magnitude must be finite")
    return result


def validate_quantity(quantity: ClaimQuantity | dict[str, object]) -> NormalizedQuantity:
    """Parse a claim quantity against bundled definitions and normalize it."""

    result = _pint_quantity(quantity)
    return NormalizedQuantity(
        magnitude=Decimal(str(result.magnitude)),
        unit=f"{result.units:~}",
        dimensionality=str(result.dimensionality),
    )


def normalized_quantity(value: Decimal, unit: str) -> NormalizedQuantity:
    """Normalize a value/unit pair using the same locked validation path."""

    return validate_quantity(
        ClaimQuantity(quantity_kind="anonymous", value=value, unit=unit)
    )


def expected_dimensionality(unit: str) -> str:
    """Return the dimensionality of a trusted rule-declared unit."""

    _reject_ambiguous_unit(unit)
    try:
        quantity = ureg.Quantity(Decimal(1), unit).to_base_units()
    except (pint.UndefinedUnitError, ValueError, TypeError) as exc:
        raise InvalidQuantityError(f"undefined unit: {unit}") from exc
    return str(quantity.dimensionality)


def compare_quantities(
    left: ClaimQuantity | dict[str, object],
    right: ClaimQuantity | dict[str, object],
) -> int:
    """Compare compatible quantities, returning ``-1``, ``0``, or ``1``."""

    left_quantity = _pint_quantity(left)
    right_quantity = _pint_quantity(right)
    if left_quantity.dimensionality != right_quantity.dimensionality:
        raise IncompatibleDimensionsError(
            "incompatible dimensions: "
            f"{left_quantity.dimensionality} and {right_quantity.dimensionality}"
        )
    left_value = Decimal(str(left_quantity.magnitude))
    right_value = Decimal(str(right_quantity.magnitude))
    return (left_value > right_value) - (left_value < right_value)
