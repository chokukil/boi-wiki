"""Validated presentation artifacts for reviewed Equation Knowledge.

These assets have no verdict authority.  Their digests bind only presentation
bytes to one exact Equation Knowledge identity.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.equation_rendering import validate_equation_svg


class _AssetModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class EquationRendererIdentity(_AssetModel):
    engine: str = Field(min_length=1)
    version: str = Field(min_length=1)
    output: str = Field(min_length=1)
    font: str = Field(min_length=1)


class EquationPresentationAsset(_AssetModel):
    equation_id: str = Field(pattern=r"^sci:equation:[A-Za-z0-9._:-]+$")
    equation_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    display_latex: str = Field(min_length=1, max_length=4096)
    plain_text: str = Field(min_length=1, max_length=4096)
    accessibility_reading: str = Field(min_length=1, max_length=1000)
    sanitized_svg: str = Field(min_length=1, max_length=524_288)
    svg_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    renderer: EquationRendererIdentity
    asset_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def exact_safe_asset(self) -> "EquationPresentationAsset":
        validated = validate_equation_svg(self.sanitized_svg, self.svg_digest)
        if validated.accessibility_reading != self.accessibility_reading:
            raise ValueError("Equation SVG accessibility reading does not match")
        expected = sha256_digest(self.model_dump(mode="json", exclude={"asset_digest"}))
        if self.asset_digest != expected:
            raise ValueError("Equation presentation asset digest does not match")
        return self


class EquationAssetManifest(_AssetModel):
    schema_version: str = Field(pattern=r"^science-equation-assets/0\.1$")
    assets: tuple[EquationPresentationAsset, ...]
    manifest_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def exact_unique_manifest(self) -> "EquationAssetManifest":
        identities = [
            (asset.equation_id, asset.equation_digest) for asset in self.assets
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("Equation presentation assets must be unique")
        if identities != sorted(identities):
            raise ValueError("Equation presentation assets must be canonical")
        expected = sha256_digest(
            self.model_dump(mode="json", exclude={"manifest_digest"})
        )
        if self.manifest_digest != expected:
            raise ValueError("Equation asset manifest digest does not match")
        return self


def default_equation_asset_manifest_path() -> Path:
    return Path(__file__).resolve().parents[1] / "static" / "science-equations.json"


def load_equation_asset_manifest(
    path: Path | None = None,
) -> EquationAssetManifest:
    manifest_path = path or default_equation_asset_manifest_path()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        return EquationAssetManifest.model_validate(payload)
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValidationError,
        ValueError,
    ) as exc:
        raise ValueError("Equation presentation manifest failed closed") from exc


def equation_asset_index(
    path: Path | None = None,
) -> dict[tuple[str, str], EquationPresentationAsset]:
    manifest = load_equation_asset_manifest(path)
    return {
        (asset.equation_id, asset.equation_digest): asset.model_copy(deep=True)
        for asset in manifest.assets
    }


__all__ = [
    "EquationAssetManifest",
    "EquationPresentationAsset",
    "EquationRendererIdentity",
    "default_equation_asset_manifest_path",
    "equation_asset_index",
    "load_equation_asset_manifest",
]
