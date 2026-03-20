"""Integration tests against a live CKAN 2.11 instance.

Run with: pytest tests/test_integration.py -v -m integration
Requires: CKAN at http://localhost:5050 with openapi_view enabled
          and at least one DataStore resource.

Skipped automatically if CKAN is not reachable.
"""

import json
import urllib.request
import urllib.error

import pytest

CKAN_URL = "http://localhost:5050"


def _api_get(path):
    """Make a GET request to the CKAN API."""
    url = f"{CKAN_URL}{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read()), resp.status


def _ckan_available():
    try:
        _api_get("/api/action/status_show")
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def datastore_resource():
    """Find the first DataStore-active resource. Session-scoped to avoid repeated lookups."""
    try:
        data, _ = _api_get("/api/action/package_list")
        for pkg_name in data["result"]:
            pkg_data, _ = _api_get(f"/api/action/package_show?id={pkg_name}")
            for res in pkg_data["result"]["resources"]:
                if res.get("datastore_active"):
                    return res["id"], pkg_data["result"]["name"]
    except Exception:
        pass
    pytest.skip("No DataStore resources found")


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _ckan_available(), reason=f"CKAN not available at {CKAN_URL}"),
]


class TestResourceOpenApiEndpoint:
    def test_returns_valid_openapi_spec(self, datastore_resource):
        resource_id, _ = datastore_resource
        data, status = _api_get(
            f"/api/3/action/resource_openapi/{resource_id}"
        )
        assert status == 200
        assert data["success"] is True
        spec = data["result"]
        assert spec["openapi"] == "3.1.0"
        assert "paths" in spec
        assert "components" in spec

    def test_spec_has_typed_schema(self, datastore_resource):
        resource_id, _ = datastore_resource
        data, _ = _api_get(
            f"/api/3/action/resource_openapi/{resource_id}"
        )
        spec = data["result"]
        schemas = spec["components"]["schemas"]
        assert "SearchResponse" in schemas
        records_schema = (
            schemas["SearchResponse"]["properties"]["result"]
            ["properties"]["records"]
        )
        assert records_schema["type"] == "array"
        assert "properties" in records_schema["items"]

    def test_invalid_uuid_returns_400(self):
        try:
            _api_get("/api/3/action/resource_openapi/not-a-uuid")
            assert False, "Should have raised"
        except urllib.error.HTTPError as e:
            assert e.code == 400

    def test_nonexistent_resource_returns_403(self):
        """Non-existent UUIDs return 403 (unified with NotAuthorized to prevent enumeration)."""
        try:
            _api_get(
                "/api/3/action/resource_openapi/"
                "00000000-0000-0000-0000-000000000000"
            )
            assert False, "Should have raised"
        except urllib.error.HTTPError as e:
            assert e.code in (403, 404)


class TestResourceSearchEndpoint:
    def test_returns_records(self, datastore_resource):
        resource_id, _ = datastore_resource
        data, status = _api_get(
            f"/api/3/action/resource_search/{resource_id}?limit=2"
        )
        assert status == 200
        assert data["success"] is True
        assert "records" in data["result"]
        assert len(data["result"]["records"]) <= 2

    def test_negative_limit_returns_400(self, datastore_resource):
        resource_id, _ = datastore_resource
        try:
            _api_get(
                f"/api/3/action/resource_search/{resource_id}?limit=-1"
            )
            assert False, "Should have raised"
        except urllib.error.HTTPError as e:
            assert e.code == 400

    def test_non_integer_limit_returns_400(self, datastore_resource):
        resource_id, _ = datastore_resource
        try:
            _api_get(
                f"/api/3/action/resource_search/{resource_id}?limit=abc"
            )
            assert False, "Should have raised"
        except urllib.error.HTTPError as e:
            assert e.code == 400


class TestDatasetOpenApiEndpoint:
    def test_returns_combined_spec(self, datastore_resource):
        _, dataset_name = datastore_resource
        data, status = _api_get(
            f"/api/3/action/dataset_openapi/{dataset_name}"
        )
        assert status == 200
        spec = data["result"]
        assert spec["openapi"] == "3.1.0"
        assert len(spec["paths"]) >= 1

    def test_invalid_dataset_id_returns_400(self):
        try:
            _api_get("/api/3/action/dataset_openapi/DROP%20TABLE;--")
            assert False, "Should have raised"
        except urllib.error.HTTPError as e:
            assert e.code == 400


class TestSwaggerUiPages:
    def test_resource_swagger_ui_returns_html(self, datastore_resource):
        resource_id, _ = datastore_resource
        url = f"{CKAN_URL}/openapi/resource/{resource_id}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode()
            assert resp.status == 200
            assert "swagger-ui" in body
            assert "Content-Security-Policy" in dict(resp.headers)

    def test_dataset_swagger_ui_returns_html(self, datastore_resource):
        _, dataset_name = datastore_resource
        url = f"{CKAN_URL}/openapi/dataset/{dataset_name}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode()
            assert resp.status == 200
            assert "swagger-ui" in body
