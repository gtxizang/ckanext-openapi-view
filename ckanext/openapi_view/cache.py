"""Caching layer using dogpile.cache.

Supports Redis (production) and in-memory (development) backends.
Uses JSON serialization (not pickle) to prevent deserialization attacks
on shared Redis instances.
"""

import json
import logging

from dogpile.cache import make_region
from dogpile.cache.api import NO_VALUE

import ckan.plugins.toolkit as toolkit

log = logging.getLogger(__name__)

_region = None


def _json_serializer(value):
    """Serialize cache values as JSON bytes (safe alternative to pickle)."""
    return json.dumps(value).encode("utf-8")


def _json_deserializer(raw):
    """Deserialize JSON bytes from cache."""
    return json.loads(raw)


def _get_config(key, default=None):
    return toolkit.config.get(f"ckanext.openapi_view.{key}", default)


def get_region():
    """Get or initialise the dogpile.cache region."""
    global _region
    if _region is not None:
        return _region

    backend = _get_config("cache.backend", "dogpile.cache.memory")
    expiry = int(_get_config("cache.expiry", 3600))

    arguments = {}

    if backend == "dogpile.cache.redis":
        redis_url = _get_config(
            "cache.redis_url",
            toolkit.config.get("ckan.redis.url", "redis://localhost:6379/1"),
        )
        arguments = {
            "url": redis_url,
            "redis_expiration_time": expiry + 60,
            "distributed_lock": True,
        }

    _region = make_region().configure(
        backend,
        expiration_time=expiry,
        arguments=arguments,
    )

    # Use JSON serialization instead of pickle to prevent RCE via
    # deserialization of malicious payloads on shared Redis instances.
    _region.serializer = _json_serializer
    _region.deserializer = _json_deserializer

    log.info(
        "OpenAPI cache configured: backend=%s, expiry=%ds, serializer=json",
        backend,
        expiry,
    )
    return _region


def resource_cache_key(resource_id):
    return f"openapi:resource:{resource_id}"


def dataset_cache_key(dataset_id):
    return f"openapi:dataset:{dataset_id}"


def get_cached(key):
    """Get a value from cache. Returns NO_VALUE sentinel if not cached."""
    region = get_region()
    value = region.get(key)
    log.debug("Cache %s: %s", "hit" if value is not NO_VALUE else "miss", key)
    return value


def set_cached(key, value):
    """Set a value in cache."""
    region = get_region()
    region.set(key, value)


def invalidate(key):
    """Delete a key from cache."""
    region = get_region()
    region.delete(key)


def invalidate_resource(resource_id):
    """Invalidate the cached spec for a resource."""
    invalidate(resource_cache_key(resource_id))


def invalidate_dataset(dataset_id):
    """Invalidate the cached spec for a dataset."""
    invalidate(dataset_cache_key(dataset_id))
