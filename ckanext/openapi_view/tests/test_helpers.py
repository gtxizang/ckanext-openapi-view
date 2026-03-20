"""Tests for template helper functions."""

from unittest.mock import patch, MagicMock

from ckanext.openapi_view import helpers


class TestHasDatastore:
    @patch("ckanext.openapi_view.helpers.toolkit")
    def test_returns_true_when_datastore_active(self, mock_toolkit):
        mock_toolkit.get_action.return_value = MagicMock(
            return_value={"id": "res-1", "datastore_active": True}
        )
        assert helpers.openapi_view_has_datastore("res-1") is True

    @patch("ckanext.openapi_view.helpers.toolkit")
    def test_returns_false_when_datastore_inactive(self, mock_toolkit):
        mock_toolkit.get_action.return_value = MagicMock(
            return_value={"id": "res-1", "datastore_active": False}
        )
        assert helpers.openapi_view_has_datastore("res-1") is False

    @patch("ckanext.openapi_view.helpers.toolkit")
    def test_returns_false_when_flag_missing(self, mock_toolkit):
        mock_toolkit.get_action.return_value = MagicMock(
            return_value={"id": "res-1"}
        )
        assert helpers.openapi_view_has_datastore("res-1") is False

    @patch("ckanext.openapi_view.helpers.toolkit")
    def test_returns_false_on_exception(self, mock_toolkit):
        mock_toolkit.get_action.return_value = MagicMock(
            side_effect=Exception("Not found")
        )
        assert helpers.openapi_view_has_datastore("res-1") is False


class TestDatasetHasDatastore:
    @patch("ckanext.openapi_view.helpers.toolkit")
    def test_returns_true_with_mixed_resources(self, mock_toolkit):
        mock_toolkit.get_action.return_value = MagicMock(
            return_value={
                "resources": [
                    {"id": "res-1", "datastore_active": False},
                    {"id": "res-2", "datastore_active": True},
                    {"id": "res-3"},
                ],
            }
        )
        assert helpers.openapi_view_dataset_has_datastore("ds-1") is True

    @patch("ckanext.openapi_view.helpers.toolkit")
    def test_returns_false_when_no_datastore_resources(self, mock_toolkit):
        mock_toolkit.get_action.return_value = MagicMock(
            return_value={
                "resources": [
                    {"id": "res-1", "datastore_active": False},
                    {"id": "res-2"},
                ],
            }
        )
        assert helpers.openapi_view_dataset_has_datastore("ds-1") is False

    @patch("ckanext.openapi_view.helpers.toolkit")
    def test_returns_false_on_exception(self, mock_toolkit):
        mock_toolkit.get_action.return_value = MagicMock(
            side_effect=Exception("Not found")
        )
        assert helpers.openapi_view_dataset_has_datastore("ds-1") is False

    @patch("ckanext.openapi_view.helpers.toolkit")
    def test_returns_false_with_empty_resources(self, mock_toolkit):
        mock_toolkit.get_action.return_value = MagicMock(
            return_value={"resources": []}
        )
        assert helpers.openapi_view_dataset_has_datastore("ds-1") is False
