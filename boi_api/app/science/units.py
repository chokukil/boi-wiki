"""Deterministic quantity validation using one locked Pint registry."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pint

from boi_api.app.science.models import ClaimQuantity, ScienceModel


class InvalidQuantityError(ValueError):
    """A quantity cannot be parsed into a finite value and defined unit."""


class IncompatibleDimensionsError(InvalidQuantityError):
    """Two quantities cannot be compared because their dimensions differ."""


class NormalizedQuantity(ScienceModel):
    """A finite quantity represented in Pint base units."""

    magnitude: Decimal
    unit: str
    dimensionality: str


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
    try:
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
