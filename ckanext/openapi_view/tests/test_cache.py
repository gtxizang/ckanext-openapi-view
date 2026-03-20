"""Tests for the caching module."""

import json
from unittest.mock import patch

from dogpile.cache.api import NO_VALUE

from ckanext.openapi_view.cache import (
    _json_serializer,
    _json_deserializer,
    resource_cache_key,
    get_cached,
    set_cached,
    invalidate,
)


class TestJsonSerializer:
    def test_serializes_dict_to_bytes(self):
        result = _json_serializer({"key": "value"})
        assert isinstance(result, bytes)
        assert json.loads(result) == {"key": "value"}

    def test_serializes_nested_structure(self):
        data = {"openapi": "3.1.0", "paths": {"/api": {"get": {}}}}
        result = _json_serializer(data)
        assert json.loads(result) == data


class TestJsonDeserializer:
    def test_deserializes_valid_json(self):
        raw = b'{"key": "value"}'
        result = _json_deserializer(raw)
        assert result == {"key": "value"}

    def test_returns_no_value_on_invalid_json(self):
        result = _json_deserializer(b"not json{{{")
        assert result is NO_VALUE

    def test_returns_no_value_on_none(self):
        result = _json_deserializer(None)
        assert result is NO_VALUE

    def test_returns_no_value_on_bad_encoding(self):
        result = _json_deserializer(b"\x80\x81\x82")
        assert result is NO_VALUE


class TestCacheKeys:
    def test_resource_key_format(self):
        key = resource_cache_key("abc-123")
        assert key == "openapi:resource:abc-123"


def _config_side_effect(key, default=None):
    """Return the default value for any config key (simulates empty config)."""
    return default


class TestCacheRoundTrip:
    """Test get/set/invalidate with the in-memory backend."""

    @patch("ckanext.openapi_view.cache.toolkit")
    def test_set_then_get(self, mock_toolkit):
        """Values stored with set_cached should be retrievable with get_cached."""
        mock_toolkit.config.get.side_effect = _config_side_effect
        import ckanext.openapi_view.cache as cache_mod
        cache_mod._region = None

        key = "test:roundtrip:1"
        data = {"openapi": "3.1.0", "paths": {}}
        set_cached(key, data)
        result = get_cached(key)
        assert result == data

    @patch("ckanext.openapi_view.cache.toolkit")
    def test_invalidate_removes_entry(self, mock_toolkit):
        """After invalidation, get_cached should return NO_VALUE."""
        mock_toolkit.config.get.side_effect = _config_side_effect
        import ckanext.openapi_view.cache as cache_mod
        cache_mod._region = None

        key = "test:roundtrip:2"
        set_cached(key, {"data": True})
        invalidate(key)
        result = get_cached(key)
        assert result is NO_VALUE

    @patch("ckanext.openapi_view.cache.toolkit")
    def test_get_missing_key_returns_no_value(self, mock_toolkit):
        mock_toolkit.config.get.side_effect = _config_side_effect
        import ckanext.openapi_view.cache as cache_mod
        cache_mod._region = None

        result = get_cached("test:nonexistent:key")
        assert result is NO_VALUE
