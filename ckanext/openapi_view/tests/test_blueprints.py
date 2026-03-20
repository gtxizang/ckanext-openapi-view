"""Tests for blueprint route handlers."""

import json

from ckanext.openapi_view.blueprints import _json_response, _error_response, _build_csp


class TestJsonResponse:
    def test_wraps_in_ckan_envelope(self):
        resp = _json_response({"key": "value"})
        body = json.loads(resp.get_data(as_text=True))
        assert body["success"] is True
        assert body["result"] == {"key": "value"}
        assert resp.status_code == 200
        assert "application/json" in resp.content_type


class TestErrorResponse:
    def test_returns_error_envelope(self):
        resp = _error_response("Something went wrong", 400)
        body = json.loads(resp.get_data(as_text=True))
        assert body["success"] is False
        assert body["error"]["message"] == "Something went wrong"
        assert body["error"]["__type"] == "Validation Error"
        assert resp.status_code == 400

    def test_403_type(self):
        resp = _error_response("Not allowed", 403)
        body = json.loads(resp.get_data(as_text=True))
        assert body["error"]["__type"] == "Authorization Error"

    def test_404_type(self):
        resp = _error_response("Missing", 404)
        body = json.loads(resp.get_data(as_text=True))
        assert body["error"]["__type"] == "Not Found"


class TestBuildCsp:
    def test_includes_site_origin(self):
        csp = _build_csp("https://data.example.com/catalog")
        assert "https://data.example.com" in csp
        assert "connect-src" in csp
        assert "unpkg.com" in csp

    def test_handles_url_with_port(self):
        csp = _build_csp("http://localhost:5050")
        assert "http://localhost:5050" in csp
