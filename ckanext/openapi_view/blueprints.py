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


_HELP_URL = "https://docs.ckan.org/en/latest/api/"


def _json_response(data, status=200):
    """Return a JSON response matching CKAN's envelope format."""
    body = {
        "help": _HELP_URL,
        "success": True,
        "result": data,
    }
    return Response(
        json.dumps(body, default=str),
        status=status,
        content_type="application/json; charset=utf-8",
    )


_ERROR_TYPES = {
    400: "Validation Error",
    403: "Authorization Error",
    404: "Not Found",
}


def _error_response(message, status=404):
    body = {
        "help": _HELP_URL,
        "success": False,
        "error": {"message": message, "__type": _ERROR_TYPES.get(status, "Not Found")},
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


# --- Standalone Swagger UI pages ---


_SWAGGER_UI_VERSION = "5.18.2"
_SWAGGER_CSS_SRI = "sha384-rcbEi6xgdPk0iWkAQzT2F3FeBJXdG+ydrawGlfHAFIZG7wU6aKbQaRewysYpmrlW"
_SWAGGER_JS_SRI = "sha384-NXtFPpN61oWCuN4D42K6Zd5Rt2+uxeIT36R7kpXBuY9tLnZorzrJ4ykpqwJfgjpZ"
_SWAGGER_CDN = f"https://unpkg.com/swagger-ui-dist@{_SWAGGER_UI_VERSION}"

_CSP = (
    "default-src 'none'; "
    "script-src 'unsafe-inline' unpkg.com; "
    "style-src 'unsafe-inline' unpkg.com; "
    "img-src 'self' data:; "
    "font-src unpkg.com; "
    "connect-src 'self'"
)


def _swagger_ui_page(title, spec_url, ckan_url, back_url):
    """Return a standalone Swagger UI HTML page."""
    import html as html_mod
    t = html_mod.escape(title)
    # json.dumps for JS context — produces a safely quoted JS string literal
    s_js = json.dumps(spec_url)
    c = html_mod.escape(ckan_url)
    b = html_mod.escape(back_url)
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{t} — API Documentation</title>
<link rel="icon" href="/base/images/ckan.ico" type="image/x-icon">
<link rel="stylesheet" href="{_SWAGGER_CDN}/swagger-ui.css" integrity="{_SWAGGER_CSS_SRI}" crossorigin="anonymous">
<style>
*,*::before,*::after{{box-sizing:border-box}}
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#fafafa}}
.page-header{{background:linear-gradient(135deg,#16213e,#0f3460);color:#fff;padding:20px 32px}}
.page-header h1{{margin:0 0 4px 0;font-size:22px;font-weight:600}}
.page-header p{{margin:0;font-size:14px;opacity:.85}}
.page-header a{{color:#93c5fd;text-decoration:none}}
.page-header a:hover{{text-decoration:underline}}
#swagger-ui{{max-width:1200px;margin:0 auto;padding:0 16px}}
.swagger-ui .topbar{{display:none!important}}
.swagger-ui .info{{margin:20px 0 10px 0}}
.swagger-ui .info .title small{{display:none!important}}
.swagger-ui .scheme-container{{display:none!important}}
.swagger-ui .auth-wrapper{{display:none!important}}
.swagger-ui section.models{{display:none!important}}
.swagger-ui .copy-to-clipboard{{display:none!important}}
.swagger-ui select{{-webkit-appearance:menulist!important;-moz-appearance:menulist!important;appearance:menulist!important;background-image:none!important;cursor:pointer!important}}
.swagger-ui .info .renderedMarkdown table{{width:100%;border-collapse:collapse;font-size:13px;margin:12px 0}}
.swagger-ui .info .renderedMarkdown table th{{background:#16213e;color:#fff;padding:8px 12px;text-align:left;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.5px}}
.swagger-ui .info .renderedMarkdown table td{{padding:6px 12px;border-bottom:1px solid #e5e7eb;vertical-align:top}}
.swagger-ui .info .renderedMarkdown table tr:hover td{{background:#f0f4ff}}
.loading-message{{text-align:center;padding:60px 20px;color:#6366f1;font-size:16px}}
.error-message{{text-align:center;padding:60px 20px;color:#dc2626;font-size:16px}}
</style>
</head>
<body>
<div class="page-header">
  <h1>{t}</h1>
  <p><a href="{c}">{c}</a> &middot; <a href="{b}">Back to dataset</a></p>
</div>
<div id="swagger-ui"><div class="loading-message">Loading API documentation&hellip;</div></div>
<script src="{_SWAGGER_CDN}/swagger-ui-bundle.js" integrity="{_SWAGGER_JS_SRI}" crossorigin="anonymous"></script>
<script>
(function(){{
  fetch({s_js},{{credentials:"same-origin"}})
    .then(function(r){{if(!r.ok)throw new Error("HTTP "+r.status);return r.json()}})
    .then(function(d){{
      var spec=d.result||d;
      if(!spec.openapi)throw new Error("Invalid spec");
      document.getElementById("swagger-ui").innerHTML="";
      SwaggerUIBundle({{
        spec:spec,
        domNode:document.getElementById("swagger-ui"),
        presets:[SwaggerUIBundle.presets.apis],
        plugins:[SwaggerUIBundle.plugins.DownloadUrl],
        layout:"BaseLayout",
        tryItOutEnabled:true,
        docExpansion:"list",
        defaultModelsExpandDepth:0
      }});
    }})
    .catch(function(e){{
      var c=document.getElementById("swagger-ui");
      c.innerHTML="";
      var d=document.createElement("div");
      d.className="error-message";
      var p1=document.createElement("p");
      p1.textContent="Failed to load API documentation.";
      var p2=document.createElement("p");
      p2.textContent=e.message;
      d.appendChild(p1);
      d.appendChild(p2);
      c.appendChild(d);
    }});
}})();
</script>
</body>
</html>"""
    return Response(
        page,
        status=200,
        content_type="text/html; charset=utf-8",
        headers={"Content-Security-Policy": _CSP},
    )


@openapi_view.route("/openapi/resource/<resource_id>", methods=["GET"])
def resource_swagger_ui(resource_id):
    """Standalone Swagger UI page for a single DataStore resource."""
    if not _UUID_RE.match(resource_id):
        return toolkit.abort(404)
    try:
        context = {
            "user": toolkit.g.user,
            "auth_user_obj": toolkit.g.userobj,
        }
        resource = toolkit.get_action("resource_show")(
            dict(context), {"id": resource_id}
        )
        dataset = toolkit.get_action("package_show")(
            dict(context), {"id": resource["package_id"]}
        )
        site_url = toolkit.config.get("ckan.site_url", "").rstrip("/")
        spec_url = f"{site_url}/api/3/action/resource_openapi/{resource_id}"
        back_url = f"{site_url}/dataset/{dataset['name']}"
        title = f"{dataset.get('title', dataset['name'])} — {resource.get('name', resource_id)}"
        return _swagger_ui_page(title, spec_url, site_url, back_url)
    except (toolkit.ObjectNotFound, toolkit.NotAuthorized):
        return toolkit.abort(404)


@openapi_view.route("/openapi/dataset/<dataset_id>", methods=["GET"])
def dataset_swagger_ui(dataset_id):
    """Standalone Swagger UI page for all DataStore resources in a dataset."""
    if not (_UUID_RE.match(dataset_id) or _DATASET_ID_RE.match(dataset_id)):
        return toolkit.abort(404)
    try:
        context = {
            "user": toolkit.g.user,
            "auth_user_obj": toolkit.g.userobj,
        }
        dataset = toolkit.get_action("package_show")(
            dict(context), {"id": dataset_id}
        )
        site_url = toolkit.config.get("ckan.site_url", "").rstrip("/")
        spec_url = f"{site_url}/api/3/action/dataset_openapi/{dataset_id}"
        back_url = f"{site_url}/dataset/{dataset['name']}"
        title = dataset.get("title", dataset["name"])
        return _swagger_ui_page(title, spec_url, site_url, back_url)
    except (toolkit.ObjectNotFound, toolkit.NotAuthorized):
        return toolkit.abort(404)
