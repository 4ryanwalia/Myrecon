"""Materialize the five self-contained Draft 2020-12 JSON Schemas."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "schemas"
ROOT.mkdir(exist_ok=True)

short = {"type": "string", "minLength": 8, "maxLength": 160}
name = {"type": "string", "minLength": 2, "maxLength": 100}
paragraph = {"type": "string", "minLength": 80}
https = {"type": "string", "format": "uri", "pattern": "^https://"}
common = {
    "kind": {"type": "string"},
    "slug": {"type": "string", "pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$"},
    "status": {"enum": ["draft", "published"]},
    "title": {"type": "string", "minLength": 25, "maxLength": 70},
    "description": {"type": "string", "minLength": 80, "maxLength": 180},
    "h1": short,
    "focus_keyword": short,
    "intro": paragraph,
    "sections": {"type": "array", "minItems": 3, "items": {"type": "object", "additionalProperties": False,
                 "required": ["heading", "body"], "properties": {"heading": short, "body": paragraph}}},
    "sources": {"type": "array", "minItems": 1, "uniqueItems": True, "items": https},
    "reviewed_at": {"type": "string", "format": "date"},
    "modified_at": {"type": "string", "format": "date"},
    "reviewer": {"type": "string", "minLength": 3},
    "cta": {"type": "object", "additionalProperties": False,
            "required": ["label", "href"], "properties": {
                "label": short, "href": {"type": "string", "pattern": "^/(?:[a-z0-9/?=&-]*)$"}}},
}

extras = {
    "comparison": {
        "competitor": {"type": "object", "additionalProperties": False, "required": ["name", "official_url", "interface"],
                       "properties": {"name": name, "official_url": https, "interface": {"enum": ["CLI", "web", "desktop", "mixed"]}}},
        "capabilities": {"type": "array", "minItems": 3, "items": {"type": "object", "additionalProperties": False,
                         "required": ["name", "myrecon", "competitor", "evidence_url"],
                         "properties": {"name": short, "myrecon": short, "competitor": short, "evidence_url": https}}},
        "benchmark": {"anyOf": [{"type": "null"}, {"type": "object", "additionalProperties": False,
                      "required": ["methodology", "sample_size", "measured_at", "myrecon_seconds", "competitor_seconds"],
                      "properties": {"methodology": paragraph, "sample_size": {"type": "integer", "minimum": 3},
                                     "measured_at": {"type": "string", "format": "date"},
                                     "myrecon_seconds": {"type": "number", "minimum": 0},
                                     "competitor_seconds": {"type": "number", "minimum": 0}}}]},
        "pros": {"type": "array", "minItems": 2, "items": short},
        "cons": {"type": "array", "minItems": 2, "items": short},
        "migration_note": paragraph,
        "faq": {"type": "array", "minItems": 2, "items": {"type": "object", "additionalProperties": False,
                "required": ["question", "answer"], "properties": {"question": short, "answer": paragraph}}},
    },
    "target": {
        "platform": {"type": "object", "additionalProperties": False,
                     "required": ["name", "official_url", "public_lookup", "limitations", "privacy_overview", "false_positive_note"],
                     "properties": {"name": name, "official_url": https, "public_lookup": paragraph,
                                    "limitations": paragraph, "privacy_overview": paragraph, "false_positive_note": paragraph}},
        "manual_steps": {"type": "array", "minItems": 3, "items": paragraph},
        "scan_trigger": {"type": "string", "enum": ["username"]},
    },
    "deletion": {
        "service": {"type": "string", "minLength": 2},
        "official_help_url": https,
        "steps": {"type": "array", "minItems": 3, "items": paragraph},
        "caveat": paragraph,
        "optout_link": {"anyOf": [https, {"type": "null"}]},
        "audit_pitch": paragraph,
    },
    "guide": {
        "takeaways": {"type": "array", "minItems": 3, "items": paragraph},
        "method": paragraph,
    },
    "core": {
        "product_claims": {"type": "array", "minItems": 2, "items": paragraph},
    },
}

for kind, fields in extras.items():
    props = dict(common)
    props["kind"] = {"const": kind}
    props.update(fields)
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"https://www.myrecon.xyz/schemas/{kind}.schema.json",
        "title": f"MyRecon {kind} page",
        "type": "object", "additionalProperties": False,
        "required": list(props), "properties": props,
    }
    (ROOT / f"{kind}.schema.json").write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
