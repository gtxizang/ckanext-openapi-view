"""Tests for the spec builder module."""

import copy

from ckanext.openapi_view.spec_builder import build_resource_spec, build_dataset_spec
from ckanext.openapi_view.utils import truncate as _truncate


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

    def test_integer_enum_values(self):
        """Integer values in enumValues should be converted to strings by _truncate."""
        introspection = {
            "fields": [
                {
                    "id": "status_code",
                    "type": "int4",
                    "sample": 200,
                    "samples": [200, 404, 500],
                    "isEnum": True,
                    "enumValues": [200, 404, 500],
                    "distinctCount": 3,
                },
            ],
            "totalRecords": 100,
            "sampleRecords": [],
        }
        spec = build_resource_spec(
            resource_id="test-res-id",
            site_url="https://data.example.com",
            dataset_name="Test",
            resource_name="Test",
            introspection=introspection,
        )
        records_schema = (
            spec["components"]["schemas"]["SearchResponse"]
            ["properties"]["result"]["properties"]["records"]
        )
        props = records_schema["items"]["properties"]
        assert "status_code" in props
        assert props["status_code"]["enum"] == ["200", "404", "500"]

    def test_none_in_enum_values(self):
        """None values in enumValues should not crash _truncate."""
        introspection = {
            "fields": [
                {
                    "id": "category",
                    "type": "text",
                    "sample": "A",
                    "samples": ["A", "B"],
                    "isEnum": True,
                    "enumValues": ["A", None, "B"],
                    "distinctCount": 3,
                },
            ],
            "totalRecords": 50,
            "sampleRecords": [],
        }
        spec = build_resource_spec(
            resource_id="test-res-id",
            site_url="https://data.example.com",
            dataset_name="Test",
            resource_name="Test",
            introspection=introspection,
        )
        records_schema = (
            spec["components"]["schemas"]["SearchResponse"]
            ["properties"]["result"]["properties"]["records"]
        )
        props = records_schema["items"]["properties"]
        assert "category" in props
        # None becomes "" via _truncate
        assert "" in props["category"]["enum"]

    def test_all_fields_hidden(self):
        """When all user fields are hidden, spec should still be valid."""
        introspection = {
            "fields": [
                {"id": "_id", "type": "int4", "sample": 1, "samples": [1]},
                {"id": "_full_text", "type": "tsvector", "sample": None, "samples": []},
            ],
            "totalRecords": 10,
            "sampleRecords": [],
        }
        spec = build_resource_spec(
            resource_id="test-res-id",
            site_url="https://data.example.com",
            dataset_name="Test",
            resource_name="Test",
            introspection=introspection,
            hidden_fields=["_id", "_full_text"],
        )
        assert spec["openapi"] == "3.1.0"
        records_schema = (
            spec["components"]["schemas"]["SearchResponse"]
            ["properties"]["result"]["properties"]["records"]
        )
        # items should be a plain object with no properties
        assert records_schema["items"] == {"type": "object"}


class TestTruncate:
    def test_none_returns_empty(self):
        assert _truncate(None) == ""

    def test_integer_converted(self):
        assert _truncate(42) == "42"

    def test_long_string_truncated(self):
        result = _truncate("x" * 300)
        assert len(result) == 201  # 200 chars + ellipsis
        assert result.endswith("\u2026")


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

    def test_schema_names_namespaced_per_resource(self, introspection_result):
        """Two resources must produce distinct schema names, not overwrite."""
        spec1 = build_resource_spec(
            resource_id="aaaaaaaa-1111-2222-3333-444444444444",
            site_url="https://data.example.com",
            dataset_name="Test",
            resource_name="Resource 1",
            introspection=introspection_result,
        )
        spec2 = build_resource_spec(
            resource_id="bbbbbbbb-1111-2222-3333-444444444444",
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

        schemas = combined["components"]["schemas"]
        # Should have two distinct SearchResponse schemas
        schema_names = list(schemas.keys())
        assert len(schema_names) == 2
        assert schema_names[0] != schema_names[1]
        assert "SearchResponse_aaaaaaaa" in schemas
        assert "SearchResponse_bbbbbbbb" in schemas

        # $ref pointers in each path must point to the correct namespaced schema
        path1 = combined["paths"]["/api/3/action/resource_search/aaaaaaaa-1111-2222-3333-444444444444"]
        ref1 = path1["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        assert ref1 == "#/components/schemas/SearchResponse_aaaaaaaa"

        path2 = combined["paths"]["/api/3/action/resource_search/bbbbbbbb-1111-2222-3333-444444444444"]
        ref2 = path2["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        assert ref2 == "#/components/schemas/SearchResponse_bbbbbbbb"


class TestBuildDatasetSpecMutation:
    def test_input_specs_not_mutated(self, introspection_result):
        """build_dataset_spec must not mutate the input resource specs."""
        spec1 = build_resource_spec(
            resource_id="aaaaaaaa-1111-2222-3333-444444444444",
            site_url="https://data.example.com",
            dataset_name="Test",
            resource_name="Resource 1",
            introspection=introspection_result,
        )
        path_key = "/api/3/action/resource_search/aaaaaaaa-1111-2222-3333-444444444444"
        original_ref = copy.deepcopy(
            spec1["paths"][path_key]["get"]["responses"]["200"]
            ["content"]["application/json"]["schema"]["$ref"]
        )

        build_dataset_spec(
            dataset_id="test-dataset",
            site_url="https://data.example.com",
            dataset_name="Test Dataset",
            resource_specs=[("Resource 1", spec1)],
        )

        current_ref = (
            spec1["paths"][path_key]["get"]["responses"]["200"]
            ["content"]["application/json"]["schema"]["$ref"]
        )
        assert current_ref == original_ref, (
            f"Input spec was mutated: {original_ref!r} -> {current_ref!r}"
        )
