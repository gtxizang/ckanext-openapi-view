"""Tests for plugin hooks."""

from unittest.mock import patch, MagicMock

from ckanext.openapi_view.plugin import OpenApiViewPlugin


class TestBeforeResourceDelete:
    @patch("ckanext.openapi_view.plugin.cache")
    def test_invalidates_deleted_resource(self, mock_cache):
        plugin = OpenApiViewPlugin()
        resource = {"id": "abc-123", "name": "Test"}
        remaining = []
        plugin.before_resource_delete({}, resource, remaining)
        mock_cache.invalidate_resource.assert_called_once_with("abc-123")

    @patch("ckanext.openapi_view.plugin.cache")
    def test_handles_missing_id(self, mock_cache):
        plugin = OpenApiViewPlugin()
        plugin.before_resource_delete({}, {}, [])
        mock_cache.invalidate_resource.assert_not_called()
