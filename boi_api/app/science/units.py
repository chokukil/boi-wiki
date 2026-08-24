"""Deterministic quantity validation using one locked Pint registry."""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from typing import Any

import pint

from boi_api.app.science.models import (
    ClaimPacket,
    ClaimQuantity,
    ConversionKind,
    ScienceModel,
    canonical_science_unit_token,
)


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


def canonical_unit_token(unit: object) -> str:
    """Canonicalize spelling noise before any unit policy or registry lookup."""

    try:
        return canonical_science_unit_token(unit)
    except ValueError as exc:
        if str(exc) == "ambiguous unit token: pH":
            raise AmbiguousUnitError(str(exc)) from exc
        raise InvalidQuantityError(str(exc)) from exc


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
            key = (
                canonical_unit_token(definition.source_unit),
                canonical_unit_token(definition.target_unit),
                definition.kind,
            )
            if key in keyed:
                raise ValueError(
                    f"duplicate conversion registration: {definition.conversion_id}"
                )
            if definition.kind not in {
                ConversionKind.MULTIPLICATIVE,
                ConversionKind.AFFINE,
            }:
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
        source_unit = canonical_unit_token(source_unit)
        target_unit = canonical_unit_token(target_unit)
        if (
            source_unit == target_unit
            and conversion_id is None
            and kind in {ConversionKind.MULTIPLICATIVE, ConversionKind.AFFINE}
        ):
            return magnitude
        definition = self._definitions.get((source_unit, target_unit, kind))
        if definition is None or (
            conversion_id is not None and definition.conversion_id != conversion_id
        ):
            if kind is ConversionKind.PROCEDURE_DEFINED:
                raise UnregisteredConversionError(
                    "procedure conversion is unregistered"
                )
            raise UnregisteredConversionError(
                f"unregistered {kind.value} conversion: {source_unit} -> {target_unit}"
            )
        offset = Decimal("0") if interval else definition.offset
        return magnitude * definition.scale + offset

    def convert_registered(
        self,
        value: Decimal | int | str,
        source_unit: str,
        target_unit: str,
        *,
        interval: bool = False,
    ) -> Decimal:
        """Use the one reviewed conversion registered for this exact unit pair."""

        source_unit = canonical_unit_token(source_unit)
        target_unit = canonical_unit_token(target_unit)
        matches = [
            definition
            for (source, target, _kind), definition in self._definitions.items()
            if source == source_unit and target == target_unit
        ]
        if len(matches) != 1:
            raise UnregisteredConversionError(
                f"unregistered conversion: {source_unit} -> {target_unit}"
            )
        definition = matches[0]
        return self.convert(
            value,
            source_unit,
            target_unit,
            kind=definition.kind,
            interval=interval,
            conversion_id=definition.conversion_id,
        )

    def reviewed_unit_tokens(self) -> tuple[str, ...]:
        """Return the exact unit spellings admitted by the reviewed registry."""

        return tuple(
            sorted(
                {
                    unit
                    for source, target, _kind in self._definitions
                    for unit in (source, target)
                },
                key=lambda item: (-len(item), item),
            )
        )


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
            (
                "sci-conversion:ohm-law-product-voltage",
                ConversionKind.MULTIPLICATIVE,
                "ampere * ohm",
                "volt",
                Decimal("1"),
                Decimal("0"),
            ),
            (
                "sci-conversion:voltage-ohm-law-product",
                ConversionKind.MULTIPLICATIVE,
                "volt",
                "ampere * ohm",
                Decimal("1"),
                Decimal("0"),
            ),
            (
                "sci-conversion:celsius-kelvin",
                ConversionKind.AFFINE,
                "°C",
                "kelvin",
                Decimal("1"),
                Decimal("273.15"),
            ),
            (
                "sci-conversion:kelvin-celsius",
                ConversionKind.AFFINE,
                "kelvin",
                "°C",
                Decimal("1"),
                Decimal("-273.15"),
            ),
            (
                "sci-conversion:radian-per-second-radian-per-millisecond",
                ConversionKind.MULTIPLICATIVE,
                "radian / second",
                "radian / millisecond",
                Decimal("0.001"),
                Decimal("0"),
            ),
            (
                "sci-conversion:radian-per-millisecond-radian-per-second",
                ConversionKind.MULTIPLICATIVE,
                "radian / millisecond",
                "radian / second",
                Decimal("1000"),
                Decimal("0"),
            ),
            (
                "sci-conversion:newton-millinewton",
                ConversionKind.MULTIPLICATIVE,
                "newton",
                "millinewton",
                Decimal("1000"),
                Decimal("0"),
            ),
            (
                "sci-conversion:millinewton-newton",
                ConversionKind.MULTIPLICATIVE,
                "millinewton",
                "newton",
                Decimal("0.001"),
                Decimal("0"),
            ),
            (
                "sci-conversion:joule-millijoule",
                ConversionKind.MULTIPLICATIVE,
                "joule",
                "millijoule",
                Decimal("1000"),
                Decimal("0"),
            ),
            (
                "sci-conversion:millijoule-joule",
                ConversionKind.MULTIPLICATIVE,
                "millijoule",
                "joule",
                Decimal("0.001"),
                Decimal("0"),
            ),
            (
                "sci-conversion:pascal-millipascal",
                ConversionKind.MULTIPLICATIVE,
                "pascal",
                "millipascal",
                Decimal("1000"),
                Decimal("0"),
            ),
            (
                "sci-conversion:millipascal-pascal",
                ConversionKind.MULTIPLICATIVE,
                "millipascal",
                "pascal",
                Decimal("0.001"),
                Decimal("0"),
            ),
            (
                "sci-conversion:mole-per-liter-mole-per-cubic-meter",
                ConversionKind.MULTIPLICATIVE,
                "mole / liter",
                "mole / meter ** 3",
                Decimal("1000"),
                Decimal("0"),
            ),
            (
                "sci-conversion:mole-per-cubic-meter-mole-per-liter",
                ConversionKind.MULTIPLICATIVE,
                "mole / meter ** 3",
                "mole / liter",
                Decimal("0.001"),
                Decimal("0"),
            ),
            (
                "sci-conversion:ampere-milliampere",
                ConversionKind.MULTIPLICATIVE,
                "ampere",
                "milliampere",
                Decimal("1000"),
                Decimal("0"),
            ),
            (
                "sci-conversion:milliampere-ampere",
                ConversionKind.MULTIPLICATIVE,
                "milliampere",
                "ampere",
                Decimal("0.001"),
                Decimal("0"),
            ),
            (
                "sci-conversion:volt-millivolt",
                ConversionKind.MULTIPLICATIVE,
                "volt",
                "millivolt",
                Decimal("1000"),
                Decimal("0"),
            ),
            (
                "sci-conversion:millivolt-volt",
                ConversionKind.MULTIPLICATIVE,
                "millivolt",
                "volt",
                Decimal("0.001"),
                Decimal("0"),
            ),
            (
                "sci-conversion:ohm-milliohm",
                ConversionKind.MULTIPLICATIVE,
                "ohm",
                "milliohm",
                Decimal("1000"),
                Decimal("0"),
            ),
            (
                "sci-conversion:milliohm-ohm",
                ConversionKind.MULTIPLICATIVE,
                "milliohm",
                "ohm",
                Decimal("0.001"),
                Decimal("0"),
            ),
            (
                "sci-conversion:farad-millifarad",
                ConversionKind.MULTIPLICATIVE,
                "farad",
                "millifarad",
                Decimal("1000"),
                Decimal("0"),
            ),
            (
                "sci-conversion:millifarad-farad",
                ConversionKind.MULTIPLICATIVE,
                "millifarad",
                "farad",
                Decimal("0.001"),
                Decimal("0"),
            ),
            (
                "sci-conversion:square-meter-per-second-square-centimeter-per-second",
                ConversionKind.MULTIPLICATIVE,
                "meter ** 2 / second",
                "centimeter ** 2 / second",
                Decimal("10000"),
                Decimal("0"),
            ),
            (
                "sci-conversion:square-centimeter-per-second-square-meter-per-second",
                ConversionKind.MULTIPLICATIVE,
                "centimeter ** 2 / second",
                "meter ** 2 / second",
                Decimal("0.0001"),
                Decimal("0"),
            ),
            (
                "sci-conversion:electron-volt-millielectron-volt",
                ConversionKind.MULTIPLICATIVE,
                "electron_volt",
                "millielectron_volt",
                Decimal("1000"),
                Decimal("0"),
            ),
            (
                "sci-conversion:millielectron-volt-electron-volt",
                ConversionKind.MULTIPLICATIVE,
                "millielectron_volt",
                "electron_volt",
                Decimal("0.001"),
                Decimal("0"),
            ),
            (
                "sci-conversion:siemens-per-meter-millisiemens-per-centimeter",
                ConversionKind.MULTIPLICATIVE,
                "siemens / meter",
                "millisiemens / centimeter",
                Decimal("10"),
                Decimal("0"),
            ),
            (
                "sci-conversion:millisiemens-per-centimeter-siemens-per-meter",
                ConversionKind.MULTIPLICATIVE,
                "millisiemens / centimeter",
                "siemens / meter",
                Decimal("0.1"),
                Decimal("0"),
            ),
            (
                "sci-conversion:nanometer-micrometer",
                ConversionKind.MULTIPLICATIVE,
                "nanometer",
                "micrometer",
                Decimal("0.001"),
                Decimal("0"),
            ),
            (
                "sci-conversion:micrometer-nanometer",
                ConversionKind.MULTIPLICATIVE,
                "micrometer",
                "nanometer",
                Decimal("1000"),
                Decimal("0"),
            ),
            (
                "sci-conversion:pascal-second-millipascal-second",
                ConversionKind.MULTIPLICATIVE,
                "pascal * second",
                "millipascal * second",
                Decimal("1000"),
                Decimal("0"),
            ),
            (
                "sci-conversion:millipascal-second-pascal-second",
                ConversionKind.MULTIPLICATIVE,
                "millipascal * second",
                "pascal * second",
                Decimal("0.001"),
                Decimal("0"),
            ),
            (
                "sci-conversion:rpm-revolution-per-minute",
                ConversionKind.MULTIPLICATIVE,
                "rpm",
                "revolution / minute",
                Decimal("1"),
                Decimal("0"),
            ),
            (
                "sci-conversion:revolution-per-minute-rpm",
                ConversionKind.MULTIPLICATIVE,
                "revolution / minute",
                "rpm",
                Decimal("1"),
                Decimal("0"),
            ),
            (
                "sci-conversion:kilogram-gram",
                ConversionKind.MULTIPLICATIVE,
                "kilogram",
                "gram",
                Decimal("1000"),
                Decimal("0"),
            ),
            (
                "sci-conversion:gram-kilogram",
                ConversionKind.MULTIPLICATIVE,
                "gram",
                "kilogram",
                Decimal("0.001"),
                Decimal("0"),
            ),
            (
                "sci-conversion:second-millisecond",
                ConversionKind.MULTIPLICATIVE,
                "second",
                "millisecond",
                Decimal("1000"),
                Decimal("0"),
            ),
            (
                "sci-conversion:millisecond-second",
                ConversionKind.MULTIPLICATIVE,
                "millisecond",
                "second",
                Decimal("0.001"),
                Decimal("0"),
            ),
            (
                "sci-conversion:dimensionless-percent",
                ConversionKind.MULTIPLICATIVE,
                "dimensionless",
                "percent",
                Decimal("100"),
                Decimal("0"),
            ),
            (
                "sci-conversion:percent-dimensionless",
                ConversionKind.MULTIPLICATIVE,
                "percent",
                "dimensionless",
                Decimal("0.01"),
                Decimal("0"),
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


def _validated_claim_quantity(
    quantity: ClaimQuantity | dict[str, object],
) -> ClaimQuantity:
    raw_value = (
        quantity.value if isinstance(quantity, ClaimQuantity) else quantity.get("value")
    )
    try:
        if raw_value is not None and not Decimal(str(raw_value)).is_finite():
            raise InvalidQuantityError("quantity magnitude must be finite")
    except InvalidQuantityError:
        raise
    except (ArithmeticError, ValueError):
        pass
    raw_unit = (
        quantity.unit if isinstance(quantity, ClaimQuantity) else quantity.get("unit")
    )
    unit = canonical_unit_token(raw_unit)
    try:
        parsed = (
            quantity
            if isinstance(quantity, ClaimQuantity)
            else ClaimQuantity.model_validate({**quantity, "unit": unit})
        )
    except (TypeError, ValueError) as exc:
        raise InvalidQuantityError("invalid quantity") from exc
    if not parsed.value.is_finite():
        raise InvalidQuantityError("quantity magnitude must be finite")
    return parsed


def _pint_quantity(quantity: ClaimQuantity | dict[str, object]) -> pint.Quantity:
    parsed = _validated_claim_quantity(quantity)
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


def validate_quantity(
    quantity: ClaimQuantity | dict[str, object],
) -> NormalizedQuantity:
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

    unit = canonical_unit_token(unit)
    try:
        quantity = ureg.Quantity(Decimal(1), unit).to_base_units()
    except (pint.UndefinedUnitError, ValueError, TypeError) as exc:
        raise InvalidQuantityError(f"undefined unit: {unit}") from exc
    return str(quantity.dimensionality)


def comparable_values(
    left_value: Decimal | int | str,
    left_unit: str,
    right_value: Decimal | int | str,
    right_unit: str,
    *,
    interval: bool = False,
) -> tuple[Decimal, Decimal]:
    """Return magnitudes in one unit using only an exact reviewed conversion."""

    left_unit = canonical_unit_token(left_unit)
    right_unit = canonical_unit_token(right_unit)
    try:
        left = Decimal(str(left_value))
        right = Decimal(str(right_value))
    except (ArithmeticError, ValueError) as exc:
        raise InvalidQuantityError("quantity magnitude must be finite") from exc
    if not left.is_finite() or not right.is_finite():
        raise InvalidQuantityError("quantity magnitude must be finite")
    try:
        left_dimension = ureg.Quantity(Decimal(1), left_unit).dimensionality
        right_dimension = ureg.Quantity(Decimal(1), right_unit).dimensionality
    except (pint.UndefinedUnitError, ValueError, TypeError) as exc:
        raise InvalidQuantityError("undefined unit in quantity comparison") from exc
    if left_dimension != right_dimension:
        raise IncompatibleDimensionsError(
            f"incompatible dimensions: {left_dimension} and {right_dimension}"
        )
    if left_unit == right_unit:
        return left, right
    try:
        return left, conversion_registry.convert_registered(
            right,
            right_unit,
            left_unit,
            interval=interval,
        )
    except UnregisteredConversionError:
        try:
            return conversion_registry.convert_registered(
                left,
                left_unit,
                right_unit,
                interval=interval,
            ), right
        except UnregisteredConversionError as exc:
            raise UnregisteredConversionError(
                f"unregistered conversion: {left_unit} <-> {right_unit}"
            ) from exc


def compare_quantities(
    left: ClaimQuantity | dict[str, object],
    right: ClaimQuantity | dict[str, object],
    *,
    interval: bool = False,
) -> int:
    """Compare compatible quantities, returning ``-1``, ``0``, or ``1``."""

    left_quantity = _validated_claim_quantity(left)
    right_quantity = _validated_claim_quantity(right)
    left_value, right_value = comparable_values(
        left_quantity.value,
        left_quantity.unit,
        right_quantity.value,
        right_quantity.unit,
        interval=interval,
    )
    return (left_value > right_value) - (left_value < right_value)


_NUMBER_TOKEN = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


def reviewed_quantity_mentions(text: str) -> tuple[ClaimQuantity, ...]:
    """Extract explicit number-plus-reviewed-unit mentions without an LLM."""

    units = conversion_registry.reviewed_unit_tokens()
    unit_pattern = "|".join(re.escape(unit) for unit in units)
    pattern = re.compile(
        rf"(?<![\w.])(?P<value>{_NUMBER_TOKEN})\s+(?P<unit>{unit_pattern})"
        rf"(?![\w*]|\s*[/·*])",
        re.IGNORECASE,
    )
    mentions: list[ClaimQuantity] = []
    for index, match in enumerate(pattern.finditer(text)):
        matched_unit = match.group("unit")
        canonical = next(
            unit for unit in units if unit.casefold() == matched_unit.casefold()
        )
        mentions.append(
            ClaimQuantity(
                quantity_kind=f"source_mention_{index}",
                value=Decimal(match.group("value")),
                unit=canonical,
            )
        )
    return tuple(mentions)


def source_span_mentions_quantity(text: str, quantity: ClaimQuantity) -> bool:
    """Return whether source text explicitly states this numeric value and unit."""

    pattern = re.compile(
        rf"(?<![\w.])(?P<value>{_NUMBER_TOKEN})\s+{re.escape(quantity.unit)}"
        rf"(?![\w*]|\s*[/·*])",
        re.IGNORECASE,
    )
    return any(
        Decimal(match.group("value")) == quantity.value
        for match in pattern.finditer(text)
    )


def unmatched_reviewed_quantity_mentions(claim: ClaimPacket) -> tuple[str, ...]:
    """Find explicit source quantities omitted from the normalized Claim operands."""

    available = list(claim.normalized_claim.quantities)
    unmatched: list[str] = []
    for mention in reviewed_quantity_mentions(claim.source_span.exact):
        matched_index = None
        for index, quantity in enumerate(available):
            try:
                equivalent = compare_quantities(mention, quantity) == 0
            except InvalidQuantityError:
                equivalent = False
            if equivalent:
                matched_index = index
                break
        if matched_index is None:
            unmatched.append(f"{mention.value} {mention.unit}")
        else:
            available.pop(matched_index)
    return tuple(unmatched)
