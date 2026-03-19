"""Tests for action functions."""

from unittest.mock import patch

import pytest

from ckanext.openapi_view.actions import _get_introspect_config, _validate_resource_id


class TestGetIntrospectConfig:
    @patch("ckanext.openapi_view.actions.toolkit")
    def test_defaults(self, mock_toolkit):
        mock_toolkit.config.get.side_effect = lambda key, default=None: {
            "ckanext.openapi_view.hidden_fields": "_id",
            "ckanext.openapi_view.enum_threshold": 25,
            "ckanext.openapi_view.max_fields": 50,
        }.get(key, default)

        config = _get_introspect_config()
        assert "_id" in config["hidden_fields"]
        assert config["enum_threshold"] == 25
        assert config["max_fields"] == 50

    @patch("ckanext.openapi_view.actions.toolkit")
    def test_custom_hidden_fields(self, mock_toolkit):
        mock_toolkit.config.get.side_effect = lambda key, default=None: {
            "ckanext.openapi_view.hidden_fields": "_id _full_text internal_col",
            "ckanext.openapi_view.enum_threshold": 25,
            "ckanext.openapi_view.max_fields": 50,
        }.get(key, default)

        config = _get_introspect_config()
        assert config["hidden_fields"] == {"_id", "_full_text", "internal_col"}


class TestValidateResourceId:
    @patch("ckanext.openapi_view.actions.toolkit")
    def test_valid_uuid(self, mock_toolkit):
        # Should not raise
        _validate_resource_id("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

    @patch("ckanext.openapi_view.actions.toolkit")
    def test_invalid_uuid_raises(self, mock_toolkit):
        mock_toolkit.ValidationError = type("ValidationError", (Exception,), {})
        with pytest.raises(mock_toolkit.ValidationError):
            _validate_resource_id("not-a-uuid")

    @patch("ckanext.openapi_view.actions.toolkit")
    def test_path_traversal_raises(self, mock_toolkit):
        mock_toolkit.ValidationError = type("ValidationError", (Exception,), {})
        with pytest.raises(mock_toolkit.ValidationError):
            _validate_resource_id("../../etc/passwd")

    @patch("ckanext.openapi_view.actions.toolkit")
    def test_cache_key_injection_raises(self, mock_toolkit):
        mock_toolkit.ValidationError = type("ValidationError", (Exception,), {})
        with pytest.raises(mock_toolkit.ValidationError):
            _validate_resource_id("openapi:resource:real-uuid\x00")
