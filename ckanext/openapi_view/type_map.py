"""PostgreSQL type → JSON Schema type mapping."""

# Maps PostgreSQL DataStore types to JSON Schema type + optional format.
# Returns (json_type, format_or_None).
_PG_TO_JSON_SCHEMA = {
    "text": ("string", None),
    "varchar": ("string", None),
    "name": ("string", None),
    "char": ("string", None),
    "bpchar": ("string", None),
    "citext": ("string", None),
    "uuid": ("string", "uuid"),
    "int": ("integer", None),
    "int2": ("integer", None),
    "int4": ("integer", None),
    "int8": ("integer", "int64"),
    "serial": ("integer", None),
    "bigserial": ("integer", "int64"),
    "float4": ("number", "float"),
    "float8": ("number", "double"),
    "numeric": ("number", None),
    "money": ("number", None),
    "bool": ("boolean", None),
    "boolean": ("boolean", None),
    "date": ("string", "date"),
    "time": ("string", "time"),
    "timetz": ("string", "time"),
    "timestamp": ("string", "date-time"),
    "timestamptz": ("string", "date-time"),
    "interval": ("string", None),
    "json": ("object", None),
    "jsonb": ("object", None),
    "bytea": ("string", "byte"),
    # Array types
    "_text": ("array", None),
    "_int4": ("array", None),
    "_int8": ("array", None),
    "_float8": ("array", None),
    "_bool": ("array", None),
    "_varchar": ("array", None),
    "_numeric": ("array", None),
}

# Item type for array columns
_ARRAY_ITEM_TYPE = {
    "_text": "string",
    "_varchar": "string",
    "_int4": "integer",
    "_int8": "integer",
    "_float8": "number",
    "_bool": "boolean",
    "_numeric": "number",
}


def pg_to_jsonschema(pg_type):
    """Convert a PostgreSQL type name to a JSON Schema property dict.

    Args:
        pg_type: PostgreSQL type name (e.g. "text", "int4", "timestamp").

    Returns:
        dict suitable for use as a JSON Schema property value.
    """
    pg_type = pg_type.lower().strip()
    json_type, fmt = _PG_TO_JSON_SCHEMA.get(pg_type, ("string", None))

    schema = {"type": json_type}
    if fmt:
        schema["format"] = fmt

    if json_type == "array":
        item_type = _ARRAY_ITEM_TYPE.get(pg_type, "string")
        schema["items"] = {"type": item_type}

    return schema


# Sets used by introspect.py to categorise fields
TEXT_TYPES = frozenset({"text", "varchar", "name", "char", "bpchar", "citext"})
NUMERIC_TYPES = frozenset({
    "int", "int2", "int4", "int8", "float4", "float8", "numeric",
    "serial", "bigserial", "money",
})
TIMESTAMP_TYPES = frozenset({"timestamp", "timestamptz", "date", "time", "timetz"})
RANGE_TYPES = NUMERIC_TYPES | TIMESTAMP_TYPES
