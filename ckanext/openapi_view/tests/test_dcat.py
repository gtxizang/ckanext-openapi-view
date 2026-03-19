"""Tests for DCAT DataService injection."""

from unittest.mock import patch

from ckanext.openapi_view.dcat import inject_access_services


class TestInjectAccessServices:
    @patch("ckanext.openapi_view.dcat.toolkit")
    def test_injects_service_for_datastore_resource(self, mock_toolkit):
        mock_toolkit.asbool.return_value = True
        mock_toolkit.config.get.side_effect = lambda key, default="": {
            "ckanext.openapi_view.dcat_enabled": "true",
            "ckan.site_url": "https://data.example.com",
        }.get(key, default)

        dataset = {
            "resources": [
                {
                    "id": "res-123",
                    "name": "Energy Prices",
                    "datastore_active": True,
                },
                {
                    "id": "res-456",
                    "name": "Static PDF",
                    "datastore_active": False,
                },
            ]
        }

        result = inject_access_services(dataset)

        # DataStore resource should have access_services
        res_ds = result["resources"][0]
        assert len(res_ds["access_services"]) == 1
        svc = res_ds["access_services"][0]
        assert svc["title"] == "DataStore API for Energy Prices"
        assert "resource_search/res-123" in svc["endpoint_url"]
        assert "resource_openapi/res-123" in svc["endpoint_description"]
        assert svc["conforms_to"] == "https://spec.openapis.org/oas/v3.1.0"

        # Non-DataStore resource should have no access_services
        res_static = result["resources"][1]
        assert "access_services" not in res_static

    @patch("ckanext.openapi_view.dcat.toolkit")
    def test_no_duplicates_on_repeated_calls(self, mock_toolkit):
        mock_toolkit.asbool.return_value = True
        mock_toolkit.config.get.side_effect = lambda key, default="": {
            "ckanext.openapi_view.dcat_enabled": "true",
            "ckan.site_url": "https://data.example.com",
        }.get(key, default)

        dataset = {
            "resources": [
                {"id": "res-123", "name": "Test", "datastore_active": True},
            ]
        }

        result = inject_access_services(dataset)
        result = inject_access_services(result)

        assert len(result["resources"][0]["access_services"]) == 1

    @patch("ckanext.openapi_view.dcat.toolkit")
    def test_disabled_via_config(self, mock_toolkit):
        mock_toolkit.asbool.return_value = False
        mock_toolkit.config.get.side_effect = lambda key, default="": {
            "ckanext.openapi_view.dcat_enabled": "false",
            "ckan.site_url": "https://data.example.com",
        }.get(key, default)

        dataset = {
            "resources": [
                {"id": "res-123", "name": "Test", "datastore_active": True},
            ]
        }

        result = inject_access_services(dataset)
        assert "access_services" not in result["resources"][0]

    @patch("ckanext.openapi_view.dcat.toolkit")
    def test_does_not_mutate_original_dict(self, mock_toolkit):
        """Verify inject_access_services returns a copy, not a mutation."""
        mock_toolkit.asbool.return_value = True
        mock_toolkit.config.get.side_effect = lambda key, default="": {
            "ckanext.openapi_view.dcat_enabled": "true",
            "ckan.site_url": "https://data.example.com",
        }.get(key, default)

        original = {
            "resources": [
                {"id": "res-123", "name": "Test", "datastore_active": True},
            ]
        }

        result = inject_access_services(original)

        # Original should NOT be mutated
        assert "access_services" not in original["resources"][0]
        # Result should have the injection
        assert len(result["resources"][0]["access_services"]) == 1
