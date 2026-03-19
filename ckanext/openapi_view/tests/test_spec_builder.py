"""Tests for the spec builder module."""

from ckanext.openapi_view.spec_builder import build_resource_spec, build_dataset_spec


class TestBuildResourceSpec:
    def test_produces_valid_openapi_structure(self, introspection_result):
        spec = build_resource_spec(
            resource_id="test-res-id",
            site_url="https://data.example.com",
            dataset_name="Energy Market Data",
            resource_name="Hourly Prices",
            introspection=introspection_result,
        )

        assert spec["openapi"] == "3.1.0"
        assert "Energy Market Data" in spec["info"]["title"]
        assert "Hourly Prices" in spec["info"]["title"]
        assert spec["servers"][0]["url"] == "https://data.example.com"

    def test_resource_search_path_present(self, introspection_result):
        spec = build_resource_spec(
            resource_id="test-res-id",
            site_url="https://data.example.com",
            dataset_name="Test",
            resource_name="Test Resource",
            introspection=introspection_result,
        )
        assert "/api/3/action/resource_search/test-res-id" in spec["paths"]

    def test_typed_response_schema(self, introspection_result):
        spec = build_resource_spec(
            resource_id="test-res-id",
            site_url="https://data.example.com",
            dataset_name="Test",
            resource_name="Test Resource",
            introspection=introspection_result,
        )
        records_schema = (
            spec["components"]["schemas"]["SearchResponse"]
            ["properties"]["result"]["properties"]["records"]
        )
        props = records_schema["items"]["properties"]

        # bidding_zone is text with enum
        assert props["bidding_zone"]["type"] == "string"
        assert props["bidding_zone"]["enum"] == ["SE1", "SE2", "SE3", "SE4"]

        # volume_mw is float8 → number + double
        assert props["volume_mw"]["type"] == "number"
        assert props["volume_mw"]["format"] == "double"
        assert props["volume_mw"]["minimum"] == 0.0

        # timestamp → string + date-time
        assert props["timestamp"]["type"] == "string"
        assert props["timestamp"]["format"] == "date-time"

        # is_active → boolean
        assert props["is_active"]["type"] == "boolean"

        # tags → array
        assert props["tags"]["type"] == "array"

    def test_enum_filter_params(self, introspection_result):
        spec = build_resource_spec(
            resource_id="test-res-id",
            site_url="https://data.example.com",
            dataset_name="Test",
            resource_name="Test Resource",
            introspection=introspection_result,
        )
        search_path = spec["paths"]["/api/3/action/resource_search/test-res-id"]
        params = search_path["get"]["parameters"]
        filter_params = [p for p in params if p["name"].startswith("filter_")]

        assert len(filter_params) == 1
        assert filter_params[0]["name"] == "filter_bidding_zone"
        assert filter_params[0]["schema"]["enum"] == ["SE1", "SE2", "SE3", "SE4"]

    def test_hidden_fields_excluded_from_schema(self, introspection_result):
        spec = build_resource_spec(
            resource_id="test-res-id",
            site_url="https://data.example.com",
            dataset_name="Test",
            resource_name="Test Resource",
            introspection=introspection_result,
            hidden_fields=["_id"],
        )
        records_schema = (
            spec["components"]["schemas"]["SearchResponse"]
            ["properties"]["result"]["properties"]["records"]
        )
        props = records_schema["items"]["properties"]
        assert "_id" not in props

    def test_only_resource_search_path(self, introspection_result):
        spec = build_resource_spec(
            resource_id="test-res-id",
            site_url="https://data.example.com",
            dataset_name="Test",
            resource_name="Test Resource",
            introspection=introspection_result,
        )
        assert len(spec["paths"]) == 1
        assert "/api/3/action/resource_search/test-res-id" in spec["paths"]

    def test_data_dictionary_in_description(self, introspection_result):
        spec = build_resource_spec(
            resource_id="test-res-id",
            site_url="https://data.example.com",
            dataset_name="Test",
            resource_name="Test Resource",
            introspection=introspection_result,
        )
        desc = spec["info"]["description"]
        assert "Data Dictionary" in desc
        assert "bidding_zone" in desc
        assert "15,432" in desc  # total records formatted

    def test_title_escapes_html(self, introspection_result):
        """info.title must escape HTML to prevent XSS via Swagger UI."""
        spec = build_resource_spec(
            resource_id="test-res-id",
            site_url="https://data.example.com",
            dataset_name='<img src=x onerror=alert(1)>',
            resource_name='<script>alert(2)</script>',
            introspection=introspection_result,
        )
        title = spec["info"]["title"]
        assert "<img" not in title
        assert "<script>" not in title
        assert "&lt;" in title

    def test_empty_introspection(self):
        spec = build_resource_spec(
            resource_id="test-res-id",
            site_url="https://data.example.com",
            dataset_name="Test",
            resource_name="Test Resource",
            introspection=None,
        )
        assert spec["openapi"] == "3.1.0"
        assert spec["paths"]


class TestBuildDatasetSpec:
    def test_combines_resource_specs(self, introspection_result):
        spec1 = build_resource_spec(
            resource_id="res-1",
            site_url="https://data.example.com",
            dataset_name="Test",
            resource_name="Resource 1",
            introspection=introspection_result,
        )
        spec2 = build_resource_spec(
            resource_id="res-2",
            site_url="https://data.example.com",
            dataset_name="Test",
            resource_name="Resource 2",
            introspection=introspection_result,
        )

        combined = build_dataset_spec(
            dataset_id="test-dataset",
            site_url="https://data.example.com",
            dataset_name="Test Dataset",
            resource_specs=[("Resource 1", spec1), ("Resource 2", spec2)],
        )

        assert combined["openapi"] == "3.1.0"
        assert "Test Dataset" in combined["info"]["title"]
        # Both resource search paths should be present
        assert "/api/3/action/resource_search/res-1" in combined["paths"]
        assert "/api/3/action/resource_search/res-2" in combined["paths"]
