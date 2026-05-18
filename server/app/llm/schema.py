"""JSON Schema definitions for LLM structured outputs.

Schemas are embedded in the system prompt as documentation; we don't rely on
provider-side strict mode (DeepSeek's `response_format={"type":"json_object"}`
guarantees valid JSON but not schema conformance).
"""
from __future__ import annotations

import json
from typing import Any

REMINDER_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["kind", "title", "target_at"],
    "properties": {
        "kind": {
            "type": "string",
            "enum": ["event", "deadline"],
            "description": "event = scheduled point or range; deadline = due date with advance reminders",
        },
        "title": {"type": "string", "minLength": 1, "maxLength": 200},
        "description": {"type": ["string", "null"]},
        "target_at": {
            "type": "string",
            "format": "date-time",
            "description": "ISO 8601 with timezone offset; event=start time, deadline=due time",
        },
        "end_at": {
            "type": ["string", "null"],
            "format": "date-time",
            "description": "Only for event when a range is implied; MUST be null for deadline",
        },
        "duration_minutes": {
            "type": ["integer", "null"],
            "minimum": 1,
            "description": "Only for event; MUST be null for deadline",
        },
        "location": {"type": ["string", "null"], "maxLength": 200},
        "participants": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Names or handles mentioned in the source text",
        },
        "advance_reminders_minutes": {
            "type": "array",
            "items": {"type": "integer", "minimum": 0},
            "description": (
                "Offsets before target_at, each value N means notify N minutes before. "
                "Empty list = silent (notify nothing). "
                "event default [0] (notify at start). "
                "deadline default [1440, 60] (1 day + 1 hour before)."
            ),
        },
    },
    "additionalProperties": False,
}


GENERATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["reminders"],
    "properties": {
        "reminders": {
            "type": "array",
            "minItems": 1,
            "maxItems": 20,
            "items": REMINDER_ITEM_SCHEMA,
        }
    },
    "additionalProperties": False,
}


VERIFY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["pass", "issues"],
    "properties": {
        "pass": {"type": "boolean"},
        "issues": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Empty when pass=true; specific actionable problems when pass=false",
        },
    },
    "additionalProperties": False,
}


def generate_schema_str() -> str:
    return json.dumps(GENERATE_SCHEMA, ensure_ascii=False, indent=2)


def verify_schema_str() -> str:
    return json.dumps(VERIFY_SCHEMA, ensure_ascii=False, indent=2)
