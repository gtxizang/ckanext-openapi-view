"""OpenAPI 3.1.0 spec generation for DataStore resources.

Python port of buildOpenApiSpec() from swagger-explorer.js (lines 223-432),
enhanced with typed response schemas using PostgreSQL → JSON Schema mapping.
"""

import copy
import html

from .type_map import pg_to_jsonschema
from .utils import truncate as _truncate, MAX_VALUE_LEN

MAX_FIELD_NAME_LEN = 100


def _escape_markdown(s):
    """Escape a string for safe embedding in markdown."""
    if s is None:
        return ""
    s = str(s)
    s = html.escape(s, quote=True)
    for char, repl in [
        ("|", "&#124;"), ("[", "&#91;"), ("]", "&#93;"),
        ("(", "&#40;"), (")", "&#41;"), ("\\", "&#92;"),
        ("`", "&#x60;"),
    ]:
        s = s.replace(char, repl)
    s = s.replace("\n", " ").replace("\r", "")
    return s


def build_resource_spec(resource_id, site_url, dataset_name, resource_name,
                        introspection, hidden_fields=None):
    """Build an OpenAPI 3.1.0 spec for a single DataStore resource.

    Args:
        resource_id: CKAN resource ID.
        site_url: CKAN site URL (no trailing slash).
        dataset_name: Human-readable dataset title.
        resource_name: Human-readable resource name.
        introspection: Result from deep_introspect().
        hidden_fields: List of field IDs to hide (default ["_id"]).

    Returns:
        dict: OpenAPI 3.1.0 specification.
    """
    if hidden_fields is None:
        hidden_fields = ["_id"]

    all_fields = (introspection or {}).get("fields", [])
    total_records = (introspection or {}).get("totalRecords", 0)

    hidden_set = set(hidden_fields)
    user_fields = [f for f in all_fields if f["id"] not in hidden_set]
    field_names = [f["id"] for f in user_fields]
    enum_fields = [
        f for f in user_fields
        if f.get("isEnum") and f.get("enumValues") and len(f["enumValues"]) > 1
    ]

    safe_dataset_name = _escape_markdown(dataset_name)
    search_path = f"/api/3/action/resource_search/{resource_id}"

    # --- Info description with Data Dictionary ---
    info_desc = f"**Dataset:** {safe_dataset_name}\n\n"
    info_desc += (
        f"**Source:** [{_escape_markdown(site_url)}]({site_url})\n\n"
    )
    if total_records:
        info_desc += f"**Total records:** {total_records:,}\n\n"

    if all_fields:
        info_desc += f"#### Data Dictionary ({len(all_fields)} fields)\n\n"
        info_desc += "| Field | Type | Details |\n|---|---|---|\n"
        for f in all_fields:
            safe_id = _escape_markdown(_truncate(f["id"], MAX_FIELD_NAME_LEN))
            safe_type = _escape_markdown(f["type"])
            details = ""
            if f.get("isEnum") and f.get("enumValues"):
                safe_vals = [
                    _escape_markdown(_truncate(v, MAX_VALUE_LEN))
                    for v in f["enumValues"]
                ]
                details = "Values: " + ", ".join(safe_vals)
            elif f.get("min") is not None:
                details = (
                    f"Range: {_escape_markdown(str(f['min']))} "
                    f"\u2014 {_escape_markdown(str(f['max']))}"
                )
            elif f.get("distinctCount"):
                details = f"{_escape_markdown(str(f['distinctCount']))} distinct values"

            if (
                f.get("sample") is not None
                and not f.get("isEnum")
            ):
                safe_sample = _escape_markdown(_truncate(f["sample"], MAX_VALUE_LEN))
                details += f". Sample: {safe_sample}" if details else f"Sample: {safe_sample}"

            info_desc += f"| {safe_id} | {safe_type} | {details} |\n"
        info_desc += "\n"

    # --- Typed record schema ---
    record_properties = {}
    for f in user_fields:
        prop = pg_to_jsonschema(f["type"])
        if f.get("isEnum") and f.get("enumValues"):
            prop["enum"] = [_truncate(v, MAX_VALUE_LEN) for v in f["enumValues"]]
        if f.get("min") is not None and prop.get("type") in ("number", "integer"):
            try:
                prop["minimum"] = float(f["min"]) if "." in str(f["min"]) else int(f["min"])
            except (ValueError, TypeError):
                pass
        if f.get("max") is not None and prop.get("type") in ("number", "integer"):
            try:
                prop["maximum"] = float(f["max"]) if "." in str(f["max"]) else int(f["max"])
            except (ValueError, TypeError):
                pass
        record_properties[f["id"]] = prop

    # --- Enum filter params ---
    enum_filter_params = []
    for f in enum_fields:
        enum_filter_params.append({
            "name": f"filter_{f['id']}",
            "in": "query",
            "required": False,
            "schema": {
                "type": "string",
                "enum": [_truncate(v, MAX_VALUE_LEN) for v in f["enumValues"]],
            },
            "description": (
                f"Filter by {_escape_markdown(f['id'])} "
                f"({len(f['enumValues'])} values)"
            ),
        })

    safe_field_names = [_escape_markdown(n) for n in field_names]
    sort_desc = (
        f'Sort string. Fields: {", ".join(safe_field_names)}. '
        f'e.g. "{safe_field_names[0]} asc"'
        if safe_field_names
        else 'e.g. "field_name asc"'
    )
    fields_desc = (
        f"Comma-separated fields to return. Available: {', '.join(safe_field_names)}"
        if safe_field_names
        else "Comma-separated field names to return"
    )

    # --- The spec ---
    total_str = f"{total_records:,}" if total_records else "0"

    return {
        "openapi": "3.1.0",
        "info": {
            "title": f"{_escape_markdown(dataset_name)} — {_escape_markdown(resource_name)}",
            "description": info_desc,
            "version": "1.0.0",
        },
        "servers": [{"url": site_url}],
        "paths": {
            search_path: {
                "get": {
                    "operationId": "resourceSearch",
                    "summary": "Search DataStore",
                    "description": (
                        f"Query with filters, full-text search, sorting, "
                        f"and pagination. Total records: **{total_str}**"
                    ),
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "schema": {"type": "string"},
                            "description": "Full-text search across all fields",
                        },
                        *enum_filter_params,
                        {
                            "name": "limit",
                            "in": "query",
                            "schema": {
                                "type": "integer",
                                "default": 10,
                                "maximum": 32000,
                            },
                            "description": "Max rows to return (max 32,000)",
                        },
                        {
                            "name": "offset",
                            "in": "query",
                            "schema": {"type": "integer", "default": 0},
                            "description": "Number of rows to skip",
                        },
                        {
                            "name": "fields",
                            "in": "query",
                            "schema": {"type": "string"},
                            "description": fields_desc,
                        },
                        {
                            "name": "sort",
                            "in": "query",
                            "schema": {"type": "string"},
                            "description": sort_desc,
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Success",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/SearchResponse",
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "components": {
            "schemas": {
                "SearchResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "result": {
                            "type": "object",
                            "properties": {
                                "records": {
                                    "type": "array",
                                    "description": "Row objects",
                                    "items": {
                                        "type": "object",
                                        "properties": record_properties,
                                    } if record_properties else {
                                        "type": "object",
                                    },
                                },
                                "fields": {
                                    "type": "array",
                                    "items": {"type": "object"},
                                    "description": "Field metadata",
                                },
                                "total": {"type": "integer"},
                                "limit": {"type": "integer"},
                                "offset": {"type": "integer"},
                                "_links": {"type": "object"},
                            },
                        },
                    },
                },
            },
        },
    }


def _rewrite_refs(obj, old_name, new_name):
    """Recursively rewrite $ref pointers in a spec fragment."""
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key == "$ref" and isinstance(val, str):
                obj[key] = val.replace(
                    f"#/components/schemas/{old_name}",
                    f"#/components/schemas/{new_name}",
                )
            else:
                _rewrite_refs(val, old_name, new_name)
    elif isinstance(obj, list):
        for item in obj:
            _rewrite_refs(item, old_name, new_name)


def build_dataset_spec(dataset_id, site_url, dataset_name,
                       resource_specs):
    """Build a combined OpenAPI spec for all DataStore resources in a dataset.

    Args:
        dataset_id: CKAN dataset ID/name.
        site_url: CKAN site URL (no trailing slash).
        dataset_name: Human-readable dataset title.
        resource_specs: List of (resource_name, spec_dict) tuples.

    Returns:
        dict: Combined OpenAPI 3.1.0 specification.
    """
    combined_paths = {}
    combined_schemas = {}
    tags = set()

    for resource_name, spec in resource_specs:
        spec = copy.deepcopy(spec)  # Don't mutate caller's (possibly cached) dicts
        for path, path_item in spec.get("paths", {}).items():
            # Extract resource_id suffix from path for schema namespacing
            res_id_suffix = path.rsplit("/", 1)[-1][:8]
            for schema_name, schema in spec.get("components", {}).get("schemas", {}).items():
                namespaced = f"{schema_name}_{res_id_suffix}"
                combined_schemas[namespaced] = schema
                # Rewrite $ref pointers in this path's responses
                _rewrite_refs(path_item, schema_name, namespaced)
            # Make operationId unique per resource (OpenAPI 3.1 requirement)
            for method_obj in path_item.values():
                if isinstance(method_obj, dict) and "operationId" in method_obj:
                    method_obj["operationId"] = f"{method_obj['operationId']}_{res_id_suffix}"
            combined_paths[path] = path_item
        for tag in spec.get("tags", []):
            tags.add(tag["name"])

    return {
        "openapi": "3.1.0",
        "info": {
            "title": _escape_markdown(dataset_name),
            "description": f"Combined API for all DataStore resources in **{_escape_markdown(dataset_name)}**",
            "version": "1.0.0",
        },
        "servers": [{"url": site_url}],
        "tags": [{"name": t} for t in sorted(tags)],
        "paths": combined_paths,
        "components": {"schemas": combined_schemas},
    }
