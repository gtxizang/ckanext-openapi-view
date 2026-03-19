"""Tests for the introspection module."""

from unittest.mock import patch, MagicMock

from ckanext.openapi_view.introspect import deep_introspect, _safe_sql_identifier


class TestSafeSqlIdentifier:
    def test_simple_name(self):
        assert _safe_sql_identifier("column") == '"column"'

    def test_name_with_quotes(self):
        assert _safe_sql_identifier('my"col') == '"my""col"'

    def test_null_bytes_stripped(self):
        assert _safe_sql_identifier("col\x00umn") == '"column"'

    def test_name_with_spaces(self):
        assert _safe_sql_identifier("my column") == '"my column"'


class TestDeepIntrospect:
    @patch("ckanext.openapi_view.introspect.toolkit")
    def test_returns_none_on_meta_failure(self, mock_toolkit):
        mock_toolkit.get_action.return_value = MagicMock(
            side_effect=Exception("DataStore not found")
        )
        result = deep_introspect("test-resource-id")
        assert result is None

    @patch("ckanext.openapi_view.introspect.toolkit")
    def test_basic_introspection(self, mock_toolkit):
        meta_result = {
            "fields": [
                {"id": "_id", "type": "int4"},
                {"id": "name", "type": "text"},
                {"id": "value", "type": "float8"},
            ],
            "total": 100,
        }
        sample_result = {
            "records": [
                {"_id": 1, "name": "test", "value": 1.5},
            ]
        }
        enum_result = {
            "records": [
                {"name": "alpha"},
                {"name": "beta"},
            ]
        }
        range_result = {
            "records": [{"min_val": 0.0, "max_val": 99.9}]
        }

        call_count = {"n": 0}

        def mock_action(action_name):
            def action_fn(context, data_dict):
                if action_name == "datastore_search":
                    if data_dict.get("limit") == 0:
                        return meta_result
                    return sample_result
                elif action_name == "datastore_search_sql":
                    call_count["n"] += 1
                    sql = data_dict.get("sql", "")
                    if "DISTINCT" in sql:
                        return enum_result
                    if "MIN" in sql:
                        return range_result
                    return {"records": []}
                return {}
            return action_fn

        mock_toolkit.get_action.side_effect = mock_action

        result = deep_introspect("test-resource-id")
        assert result is not None
        assert result["totalRecords"] == 100
        assert len(result["fields"]) == 3

        # Check enriched data
        name_field = next(f for f in result["fields"] if f["id"] == "name")
        assert name_field["isEnum"] is True
        assert "alpha" in name_field["enumValues"]

        value_field = next(f for f in result["fields"] if f["id"] == "value")
        assert value_field["min"] == 0.0
        assert value_field["max"] == 99.9

    @patch("ckanext.openapi_view.introspect.toolkit")
    def test_unsafe_field_names_skipped(self, mock_toolkit):
        meta_result = {
            "fields": [
                {"id": "safe_name", "type": "text"},
                {"id": "DROP TABLE;--", "type": "text"},  # Unsafe
            ],
            "total": 10,
        }

        def mock_action(action_name):
            def action_fn(context, data_dict):
                if action_name == "datastore_search":
                    if data_dict.get("limit") == 0:
                        return meta_result
                    return {"records": []}
                elif action_name == "datastore_search_sql":
                    return {"records": [{"safe_name": "val"}]}
                return {}
            return action_fn

        mock_toolkit.get_action.side_effect = mock_action

        result = deep_introspect("test-resource-id")
        assert result is not None
        # The unsafe field should still be in the output (all fields are),
        # but no SQL query should have been issued for it.
        field_ids = [f["id"] for f in result["fields"]]
        assert "safe_name" in field_ids
        assert "DROP TABLE;--" in field_ids
        # But the unsafe field should NOT have enum data
        unsafe_field = next(f for f in result["fields"] if f["id"] == "DROP TABLE;--")
        assert "enumValues" not in unsafe_field
