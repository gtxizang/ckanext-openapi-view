"""Tests for template helper functions."""

import sys
from unittest.mock import MagicMock

# Mock the ckan module hierarchy so helpers.py can be imported without CKAN.
# Python's `import a.b.c as x` resolves via attribute access on the parent,
# so we must wire the attribute chain: ckan.plugins.toolkit -> _mock_toolkit.
_mock_toolkit = MagicMock()
_mock_plugins = MagicMock()
_mock_plugins.toolkit = _mock_toolkit
_mock_ckan = MagicMock()
_mock_ckan.plugins = _mock_plugins

sys.modules["ckan"] = _mock_ckan
sys.modules["ckan.plugins"] = _mock_plugins
sys.modules["ckan.plugins.toolkit"] = _mock_toolkit

from ckanext.openapi_view import helpers  # noqa: E402


def _setup_action(return_value=None, side_effect=None):
    """Configure _mock_toolkit.get_action to return a callable mock."""
    action_fn = MagicMock(return_value=return_value, side_effect=side_effect)
    _mock_toolkit.get_action.return_value = action_fn
    return action_fn


class TestHasDatastore:
    def test_returns_true_when_datastore_active(self):
        _setup_action(return_value={"id": "res-1", "datastore_active": True})
        assert helpers.openapi_view_has_datastore("res-1") is True

    def test_returns_false_when_datastore_inactive(self):
        _setup_action(return_value={"id": "res-1", "datastore_active": False})
        assert helpers.openapi_view_has_datastore("res-1") is False

    def test_returns_false_when_flag_missing(self):
        _setup_action(return_value={"id": "res-1"})
        assert helpers.openapi_view_has_datastore("res-1") is False

    def test_returns_false_on_exception(self):
        _setup_action(side_effect=Exception("Not found"))
        assert helpers.openapi_view_has_datastore("res-1") is False


class TestDatasetHasDatastore:
    def test_returns_true_with_mixed_resources(self):
        _setup_action(return_value={
            "resources": [
                {"id": "res-1", "datastore_active": False},
                {"id": "res-2", "datastore_active": True},
                {"id": "res-3"},
            ],
        })
        assert helpers.openapi_view_dataset_has_datastore("ds-1") is True

    def test_returns_false_when_no_datastore_resources(self):
        _setup_action(return_value={
            "resources": [
                {"id": "res-1", "datastore_active": False},
                {"id": "res-2"},
            ],
        })
        assert helpers.openapi_view_dataset_has_datastore("ds-1") is False

    def test_returns_false_on_exception(self):
        _setup_action(side_effect=Exception("Not found"))
        assert helpers.openapi_view_dataset_has_datastore("ds-1") is False

    def test_returns_false_with_empty_resources(self):
        _setup_action(return_value={"resources": []})
        assert helpers.openapi_view_dataset_has_datastore("ds-1") is False
