# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6", "jsonschema>=4.21"]
# ///
"""Validate contracts/fixtures/** against contracts/openapi.yaml (JSON Schema 2020-12).

    uv run contracts/tools/validate_fixtures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SPEC = yaml.safe_load((ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8"))

FILES = {
    "cities.json": {"type": "array", "items": {"$ref": "#/components/schemas/City"}},
    "health.json": "Health",
    "twins.json": "TwinsResponse",
    "twins_praha_krakow.json": "TwinsResponse",
    "*/meta.json": "Meta",
    "*/score_*.json": "ScoreResponse",
    "*/place.json": "Place",
    "*/commute.json": "CommuteResponse",
    "*/similar.json": "SimilarResponse",
    "*/districts.json": "DistrictList",
    "*/geocode.json": "GeocodeResponse",
    "*/live_air.json": "LiveAir",
}


def validator_for(schema) -> Draft202012Validator:
    if isinstance(schema, str):
        schema = {"$ref": f"#/components/schemas/{schema}"}
    root = {**SPEC, **schema}  # resolve "#/components/..." against the spec
    return Draft202012Validator(root)


def check(name: str, obj, schema) -> list[str]:
    return [f"{name}: {'/'.join(map(str, e.absolute_path))}: {e.message}" for e in validator_for(schema).iter_errors(obj)]


def main() -> int:
    base = ROOT / "contracts/fixtures"
    errors: list[str] = []
    seen = 0
    for pattern, schema in FILES.items():
        for path in sorted(base.glob(pattern)):
            seen += 1
            errors += check(str(path.relative_to(ROOT)), json.loads(path.read_text(encoding="utf-8")), schema)
    for e in errors[:50]:
        print(e)
    print(f"{seen} fixture files checked, {len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
