"""Flask blueprint providing REST-style routes for OpenAPI specs and resource search."""

import json
import re

from flask import Blueprint, Response, request

import ckan.plugins.toolkit as toolkit

openapi_view = Blueprint("openapi_view", __name__)

_UUID_RE = re.compile(
    r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"
)
_DATASET_ID_RE = re.compile(r"^[a-z0-9_-]{2,100}$")


def _json_response(data, status=200):
    """Return a JSON response matching CKAN's envelope format."""
    body = {
        "help": request.path,
        "success": True,
        "result": data,
    }
    return Response(
        json.dumps(body, default=str),
        status=status,
        content_type="application/json; charset=utf-8",
    )


def _error_response(message, status=404):
    body = {
        "help": request.path,
        "success": False,
        "error": {"message": message, "__type": "Not Found"},
    }
    return Response(
        json.dumps(body),
        status=status,
        content_type="application/json; charset=utf-8",
    )


@openapi_view.route(
    "/api/3/action/resource_openapi/<resource_id>", methods=["GET"]
)
def resource_openapi(resource_id):
    """Serve the OpenAPI spec for a single DataStore resource."""
    if not _UUID_RE.match(resource_id):
        return _error_response("Invalid resource ID format", 400)
    try:
        context = {
            "user": toolkit.g.user,
            "auth_user_obj": toolkit.g.userobj,
        }
        spec = toolkit.get_action("resource_openapi_show")(
            context, {"resource_id": resource_id}
        )
        return _json_response(spec)
    except (toolkit.ObjectNotFound, toolkit.NotAuthorized):
        # Unified response prevents resource existence enumeration
        return _error_response("Not found or not authorized", 403)


@openapi_view.route(
    "/api/3/action/dataset_openapi/<dataset_id>", methods=["GET"]
)
def dataset_openapi(dataset_id):
    """Serve the combined OpenAPI spec for all DataStore resources in a dataset."""
    if not (_UUID_RE.match(dataset_id) or _DATASET_ID_RE.match(dataset_id)):
        return _error_response("Invalid dataset ID format", 400)
    try:
        context = {
            "user": toolkit.g.user,
            "auth_user_obj": toolkit.g.userobj,
        }
        spec = toolkit.get_action("dataset_openapi_show")(
            context, {"dataset_id": dataset_id}
        )
        return _json_response(spec)
    except (toolkit.ObjectNotFound, toolkit.NotAuthorized):
        return _error_response("Not found or not authorized", 403)


@openapi_view.route(
    "/api/3/action/resource_search/<resource_id>", methods=["GET"]
)
def resource_search(resource_id):
    """Proxy to datastore_search with the resource_id baked into the path.

    Accepts the same query parameters as datastore_search:
    q, filters, limit, offset, fields, sort, etc.
    Also supports filter_<field>=<value> convenience params.
    """
    if not _UUID_RE.match(resource_id):
        return _error_response("Invalid resource ID format", 400)
    try:
        context = {
            "user": toolkit.g.user,
            "auth_user_obj": toolkit.g.userobj,
        }

        data_dict = {"resource_id": resource_id}

        # Map standard params
        for param in (
            "q", "fields", "sort",
            "records_format", "include_total", "distinct",
        ):
            val = request.args.get(param)
            if val is not None:
                data_dict[param] = val

        # Validate and convert limit/offset
        for int_param, max_val in (("limit", 32000), ("offset", None)):
            raw = request.args.get(int_param)
            if raw is not None:
                try:
                    val = int(raw)
                except ValueError:
                    return _error_response(
                        f"{int_param} must be an integer", 400
                    )
                if val < 0:
                    return _error_response(
                        f"{int_param} must not be negative", 400
                    )
                if max_val is not None:
                    val = min(val, max_val)
                data_dict[int_param] = val

        # Handle filter_<field>=<value> convenience params
        filters = {}
        for key, val in request.args.items():
            if key.startswith("filter_") and val:
                filters[key[7:]] = val

        # Also support explicit filters JSON param — validate structure
        filters_json = request.args.get("filters")
        if filters_json:
            try:
                explicit_filters = json.loads(filters_json)
                if isinstance(explicit_filters, dict):
                    for k, v in explicit_filters.items():
                        if isinstance(k, str) and isinstance(v, (str, list)):
                            filters[k] = v
            except (json.JSONDecodeError, TypeError):
                return _error_response("filters must be valid JSON", 400)

        if filters:
            data_dict["filters"] = filters

        result = toolkit.get_action("datastore_search")(context, data_dict)
        return _json_response(result)
    except (toolkit.ObjectNotFound, toolkit.NotAuthorized):
        return _error_response("Not found or not authorized", 403)
