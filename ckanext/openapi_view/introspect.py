"""Server-side deep introspection of DataStore resources.

Python port of deepIntrospect() from swagger-explorer.js (lines 114-217).
Uses direct CKAN action calls instead of HTTP requests.
"""

import logging
import re

import ckan.plugins.toolkit as toolkit

from .type_map import TEXT_TYPES, RANGE_TYPES
from .utils import truncate as _truncate

log = logging.getLogger(__name__)

SAFE_FIELD_RE = re.compile(r"^[a-zA-Z0-9_\- .,]+$")
MAX_FIELD_NAME_LEN = 100


def _safe_sql_identifier(name):
    """Double-quote a SQL identifier, escaping internal quotes."""
    s = str(name).replace("\x00", "")
    return '"' + s.replace('"', '""') + '"'


def deep_introspect(resource_id, context=None, config=None):
    """Introspect a DataStore resource and return enriched field metadata.

    Args:
        resource_id: The CKAN resource ID.
        context: CKAN context dict (optional, defaults to ignore_auth).
        config: Dict with optional keys:
            - hidden_fields: set of field IDs to exclude (default {"_id"})
            - enum_threshold: max distinct values for enum (default 25)
            - max_fields: max fields to introspect (default 50)

    Returns:
        dict with keys: fields, totalRecords, sampleRecords
        or None if introspection fails.
    """
    if context is None:
        context = {}

    if config is None:
        config = {}

    hidden_fields = config.get("hidden_fields", {"_id"})
    enum_threshold = config.get("enum_threshold", 25)
    max_fields = config.get("max_fields", 50)

    table_name = _safe_sql_identifier(resource_id)

    try:
        meta_result = toolkit.get_action("datastore_search")(
            dict(context), {"resource_id": resource_id, "limit": 0}
        )
    except Exception:
        log.warning("Failed to fetch metadata for resource %s", resource_id, exc_info=True)
        return None

    if not meta_result or "fields" not in meta_result:
        return None

    try:
        sample_result = toolkit.get_action("datastore_search")(
            dict(context), {"resource_id": resource_id, "limit": 5}
        )
    except Exception:
        sample_result = {"records": []}

    all_fields = meta_result["fields"]
    fields = [f for f in all_fields if f["id"] not in hidden_fields]
    total_records = meta_result.get("total", 0)
    sample_records = sample_result.get("records", [])

    # Filter to safe field names
    safe_fields = [
        f for f in fields
        if SAFE_FIELD_RE.match(f["id"]) and len(f["id"]) <= MAX_FIELD_NAME_LEN
    ]

    text_fields = [
        f for f in safe_fields if f["type"] in TEXT_TYPES
    ][:max_fields]

    range_fields = [
        f for f in safe_fields if f["type"] in RANGE_TYPES
    ][:max_fields]

    # Check if datastore_search_sql is available (not all instances enable it)
    sql_available = True
    try:
        toolkit.get_action("datastore_search_sql")
    except Exception:
        sql_available = False
        log.info(
            "datastore_search_sql not available — specs will be generated "
            "without enum/range metadata"
        )

    # Enum detection for text fields
    enum_data = {}
    if not sql_available:
        text_fields = []
    for f in text_fields:
        safe_id = _safe_sql_identifier(f["id"])
        sql = (
            f"SELECT DISTINCT {safe_id} FROM {table_name} "
            f"WHERE {safe_id} IS NOT NULL "
            f"ORDER BY {safe_id} LIMIT 51"
        )
        try:
            result = toolkit.get_action("datastore_search_sql")(
                dict(context), {"sql": sql}
            )
            if result and "records" in result:
                values = [
                    _truncate(r[f["id"]])
                    for r in result["records"]
                    if r.get(f["id"]) is not None and str(r[f["id"]]) != ""
                ]
                enum_data[f["id"]] = {
                    "values": values[:50],
                    "isEnum": len(values) <= enum_threshold,
                    "distinctCount": "50+" if len(values) >= 51 else len(values),
                }
        except Exception:
            log.debug("Enum query failed for field %s", f["id"], exc_info=True)

    # Range detection for numeric/timestamp fields
    range_data = {}
    if not sql_available:
        range_fields = []
    for f in range_fields:
        safe_id = _safe_sql_identifier(f["id"])
        sql = (
            f"SELECT MIN({safe_id}) as min_val, MAX({safe_id}) as max_val "
            f"FROM {table_name} WHERE {safe_id} IS NOT NULL"
        )
        try:
            result = toolkit.get_action("datastore_search_sql")(
                dict(context), {"sql": sql}
            )
            if result and result.get("records") and result["records"][0]:
                rec = result["records"][0]
                range_data[f["id"]] = {
                    "min": rec.get("min_val"),
                    "max": rec.get("max_val"),
                }
        except Exception:
            log.debug("Range query failed for field %s", f["id"], exc_info=True)

    # Build enriched fields (includes hidden fields in output for completeness)
    enriched_fields = []
    for f in all_fields:
        enriched = {
            "id": f["id"],
            "type": f["type"],
            "sample": sample_records[0].get(f["id"]) if sample_records else None,
            "samples": [
                r[f["id"]] for r in sample_records
                if r.get(f["id"]) is not None
            ],
        }
        if "info" in f:
            enriched["info"] = f["info"]
        if f["id"] in enum_data:
            ed = enum_data[f["id"]]
            enriched["distinctCount"] = ed["distinctCount"]
            enriched["isEnum"] = ed["isEnum"]
            enriched["enumValues"] = ed["values"]
        if f["id"] in range_data:
            enriched["min"] = range_data[f["id"]]["min"]
            enriched["max"] = range_data[f["id"]]["max"]
        enriched_fields.append(enriched)

    return {
        "fields": enriched_fields,
        "totalRecords": total_records,
        "sampleRecords": sample_records,
    }
