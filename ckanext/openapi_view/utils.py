"""Shared utilities for ckanext-openapi-view."""

import re

UUID_RE = re.compile(
    r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$",
    re.IGNORECASE,
)

DATASET_ID_RE = re.compile(r"^[a-z0-9_-]{2,100}$")

MAX_VALUE_LEN = 200


def truncate(value, max_len=MAX_VALUE_LEN):
    """Truncate a value to max_len characters, adding ellipsis if needed."""
    if value is None:
        return ""
    s = str(value)
    return s[:max_len] + "\u2026" if len(s) > max_len else s
