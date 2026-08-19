"""Validate a parsed object against extraction output schema v1.

Walks the versioned JSON Schema artifact (T006). A merge-field name that
would also be an ``additionalProperties`` failure is reported as
``merged_facts_and_claims``, so that hard rule can be tested in isolation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from moj_projekt.extraction.types import (
    MERGE_FIELD_NAMES,
    ValidationError,
    ValidationErrorCode,
)

__all__ = ["schema_v1_errors"]

_DEFS_PREFIX = "#/$defs/"


def schema_v1_errors(
    instance: object,
    schema: Mapping[str, Any],
    *,
    json_path: str = "$",
) -> list[ValidationError]:
    """Return schema-v1 (and merge-field) errors; empty means the instance fits."""
    defs = schema.get("$defs")
    defs_map: Mapping[str, Any] = defs if isinstance(defs, dict) else {}
    return _validate(instance, schema, defs_map, json_path)


def _validate(
    instance: object,
    schema: Mapping[str, Any],
    defs: Mapping[str, Any],
    json_path: str,
) -> list[ValidationError]:
    resolved = _resolve(schema, defs)
    errors: list[ValidationError] = []

    const = resolved.get("const")
    if "const" in resolved and instance != const:
        errors.append(
            _schema_error(
                json_path,
                f"expected const {const!r}, got {instance!r}",
            )
        )
        return errors

    expected_type = resolved.get("type")
    if expected_type == "object":
        errors.extend(_validate_object(instance, resolved, defs, json_path))
    elif expected_type == "array":
        errors.extend(_validate_array(instance, resolved, defs, json_path))
    elif expected_type == "string":
        errors.extend(_validate_string(instance, resolved, json_path))
    elif expected_type == "number":
        errors.extend(_validate_number(instance, resolved, json_path))
    return errors


def _validate_object(
    instance: object,
    schema: Mapping[str, Any],
    defs: Mapping[str, Any],
    json_path: str,
) -> list[ValidationError]:
    if not isinstance(instance, dict):
        return [
            _schema_error(
                json_path,
                f"expected object, got {_type_name(instance)}",
            )
        ]
    errors: list[ValidationError] = []
    properties = schema.get("properties")
    properties_map: Mapping[str, Any] = properties if isinstance(properties, dict) else {}
    required = schema.get("required")
    required_keys: Sequence[object] = required if isinstance(required, list) else ()
    for key in required_keys:
        if not isinstance(key, str):
            continue
        if key not in instance:
            errors.append(
                _schema_error(json_path, f"missing required property {key!r}")
            )
    additional = schema.get("additionalProperties", True)
    for key, value in instance.items():
        if not isinstance(key, str):
            errors.append(_schema_error(json_path, f"property name must be a string, got {key!r}"))
            continue
        child_path = f"{json_path}.{key}"
        if key in properties_map:
            child_schema = properties_map[key]
            if isinstance(child_schema, dict):
                errors.extend(_validate(value, child_schema, defs, child_path))
            continue
        if additional is False:
            if key in MERGE_FIELD_NAMES:
                errors.append(
                    ValidationError(
                        code=ValidationErrorCode.MERGED_FACTS_AND_CLAIMS,
                        message=(
                            f"Field {key!r} merges facts and claims; "
                            "extracted_facts and source_claims must stay separate "
                            "(ADR-0008)"
                        ),
                        json_path=child_path,
                    )
                )
            else:
                errors.append(
                    _schema_error(json_path, f"unexpected property {key!r}")
                )
    return errors


def _validate_array(
    instance: object,
    schema: Mapping[str, Any],
    defs: Mapping[str, Any],
    json_path: str,
) -> list[ValidationError]:
    if not isinstance(instance, list):
        return [
            _schema_error(
                json_path,
                f"expected array, got {_type_name(instance)}",
            )
        ]
    errors: list[ValidationError] = []
    min_items = schema.get("minItems")
    if isinstance(min_items, int) and len(instance) < min_items:
        errors.append(
            _schema_error(
                json_path,
                f"expected at least {min_items} item(s), got {len(instance)}",
            )
        )
    items_schema = schema.get("items")
    if isinstance(items_schema, dict):
        for index, item in enumerate(instance):
            errors.extend(
                _validate(item, items_schema, defs, f"{json_path}[{index}]")
            )
    return errors


def _validate_string(
    instance: object,
    schema: Mapping[str, Any],
    json_path: str,
) -> list[ValidationError]:
    if not isinstance(instance, str):
        return [
            _schema_error(
                json_path,
                f"expected string, got {_type_name(instance)}",
            )
        ]
    errors: list[ValidationError] = []
    min_length = schema.get("minLength")
    if isinstance(min_length, int) and len(instance) < min_length:
        errors.append(
            _schema_error(
                json_path,
                f"expected minLength {min_length}, got {len(instance)}",
            )
        )
    if schema.get("format") == "date-time" and not _is_date_time(instance):
        errors.append(
            _schema_error(
                json_path,
                f"expected date-time format, got {instance!r}",
            )
        )
    return errors


def _validate_number(
    instance: object,
    schema: Mapping[str, Any],
    json_path: str,
) -> list[ValidationError]:
    # bool is a subclass of int; a JSON boolean is not a schema number.
    if isinstance(instance, bool) or not isinstance(instance, int | float):
        return [
            _schema_error(
                json_path,
                f"expected number, got {_type_name(instance)}",
            )
        ]
    errors: list[ValidationError] = []
    minimum = schema.get("minimum")
    if isinstance(minimum, int | float) and instance < minimum:
        errors.append(
            _schema_error(
                json_path,
                f"expected minimum {minimum}, got {instance}",
            )
        )
    maximum = schema.get("maximum")
    if isinstance(maximum, int | float) and instance > maximum:
        errors.append(
            _schema_error(
                json_path,
                f"expected maximum {maximum}, got {instance}",
            )
        )
    return errors


def _resolve(schema: Mapping[str, Any], defs: Mapping[str, Any]) -> Mapping[str, Any]:
    ref = schema.get("$ref")
    if not isinstance(ref, str):
        return schema
    if not ref.startswith(_DEFS_PREFIX):
        raise ValueError(f"unsupported $ref {ref!r}; only #/$defs/... is implemented")
    name = ref[len(_DEFS_PREFIX) :]
    resolved = defs.get(name)
    if not isinstance(resolved, dict):
        raise ValueError(f"schema $ref {ref!r} does not resolve to an object definition")
    return resolved


def _is_date_time(value: str) -> bool:
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def _schema_error(json_path: str, message: str) -> ValidationError:
    return ValidationError(
        code=ValidationErrorCode.SCHEMA_V1_VIOLATION,
        message=f"Schema v1 violation at {json_path}: {message}",
        json_path=json_path,
    )


def _type_name(value: object) -> str:
    if value is None:
        return "null"
    return type(value).__name__
