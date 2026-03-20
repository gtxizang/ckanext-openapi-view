# ckanext-openapi-view

Server-side OpenAPI 3.1.0 spec generation for CKAN DataStore resources.

## Background

This is the backend companion to [ckanext-swagger-view](https://github.com/gtxizang/ckanext-swagger-view). Eric reviewed swagger-view and said the introspection (enum detection, type mapping, range analysis) should happen server-side in Python, not client-side in JavaScript. This extension does exactly that.

**ckanext-swagger-view** = the Swagger UI modal on resource pages (frontend)
**ckanext-openapi-view** = server-side OpenAPI spec generation, caching, DCAT integration (backend)

When both are installed, swagger-view fetches a pre-built spec in one HTTP request instead of running 30+ SQL queries client-side. If openapi-view is not installed, swagger-view falls back to its original client-side introspection -- so the two extensions are independent and neither requires the other.

## What you get

Each DataStore resource gets three new endpoints:

| Endpoint | What it does |
|---|---|
| `GET /api/3/action/resource_openapi/<resource_id>` | OpenAPI 3.1.0 spec with typed response schema, enum params, data dictionary |
| `GET /api/3/action/resource_search/<resource_id>` | REST-style search (proxies datastore_search with resource_id in the path) |
| `GET /api/3/action/dataset_openapi/<dataset_id>` | Combined spec for all DataStore resources in a dataset |

The key improvement over swagger-view's client-side spec: **typed response schemas**. Instead of `records: [{type: object}]`, you get:

```yaml
records:
  type: array
  items:
    type: object
    properties:
      bidding_zone: { type: string, enum: [SE1, SE2, SE3, SE4] }
      volume_mw: { type: number, format: double, minimum: 0.0, maximum: 9999.99 }
      timestamp: { type: string, format: date-time }
```

PostgreSQL types are mapped to JSON Schema: `text` -> `string`, `int4` -> `integer`, `float8` -> `number/double`, `timestamp` -> `string/date-time`, `bool` -> `boolean`, `_text` -> `array/string`, etc. (full mapping in `type_map.py`).

## How it works

1. **Introspect** (`introspect.py`) -- Python port of `deepIntrospect()` from swagger-explorer.js. Calls `datastore_search` for metadata + samples, then runs `SELECT DISTINCT` (enum detection) and `SELECT MIN/MAX` (range analysis) per field. Same safety: field name regex, double-quote escaping for SQL identifiers, configurable field limits.

2. **Build spec** (`spec_builder.py`) -- Generates OpenAPI 3.1.0 with typed response schemas, enum filter parameters, SQL examples, and a collapsible data dictionary in `info.description`.

3. **Cache** (`cache.py`) -- Per-resource specs cached via dogpile.cache (Redis in production, in-memory for dev). TTL default 1 hour. Invalidated automatically on dataset update, or manually via sysadmin action.

4. **DCAT** (`dcat.py`) -- Injects `access_services` into each DataStore resource so ckanext-dcat serializes them as `dcat:DataService` in RDF output. No custom RDF code needed.

## Installation

```bash
# Clone and install in development mode
git clone https://github.com/gtxizang/ckanext-openapi-view.git
cd ckanext-openapi-view
pip install -e .

# Add to your CKAN config (ckan.ini or production.ini)
ckan.plugins = ... openapi_view ...
```

Requires CKAN 2.10+ and `dogpile.cache` (installed automatically via setup.py). Redis is optional but recommended for production.

## Configuration

Add these to your CKAN `.ini` file. All have sensible defaults -- you can start with zero configuration.

```ini
# Fields to hide from specs (space-separated). Default: _id
ckanext.openapi_view.hidden_fields = _id _full_text

# Cache backend. Default: dogpile.cache.memory (use redis in production)
ckanext.openapi_view.cache.backend = dogpile.cache.redis

# Cache TTL in seconds. Default: 3600 (1 hour)
ckanext.openapi_view.cache.expiry = 3600

# Redis URL. Default: falls back to ckan.redis.url
ckanext.openapi_view.cache.redis_url = redis://localhost:6379/1

# Max distinct values to treat as enum. Default: 25
ckanext.openapi_view.enum_threshold = 25

# Max fields to introspect per resource. Default: 50
ckanext.openapi_view.max_fields = 50

# Max resources to include in a dataset combined spec. Default: 20
ckanext.openapi_view.max_resources_per_dataset = 20

# Inject DCAT DataService into access_services. Default: true
ckanext.openapi_view.dcat_enabled = true
```

## CKAN Actions

These are available via the standard CKAN action API (`/api/action/...`) as well as the blueprint routes above.

| Action | Auth | Description |
|---|---|---|
| `resource_openapi_show` | Same as `datastore_search` | Returns cached OpenAPI spec for a resource |
| `dataset_openapi_show` | Same as `package_show` | Returns combined spec (only includes resources the user can access) |
| `openapi_cache_invalidate` | Sysadmin only | Manually invalidate cached specs |

## How swagger-view uses this

When both extensions are installed, swagger-view's JS detects the spec URL and fetches it:

```
Button click
  -> fetch /api/3/action/resource_openapi/<id>
  -> pass spec to SwaggerUIBundle
  -> done (one request, ~100ms)
```

Without openapi-view, it falls back to the original flow:

```
Button click
  -> datastore_search (metadata)
  -> datastore_search (samples)
  -> SELECT DISTINCT per text field (enum detection)
  -> SELECT MIN/MAX per numeric field (range analysis)
  -> build spec client-side
  -> pass to SwaggerUIBundle
  -> done (30+ requests, 2-5 seconds)
```

The fallback is automatic and seamless. No configuration needed.

## DCAT 3 DataService

When `dcat_enabled = true`, each DataStore resource's `access_services` gets:

```json
{
  "title": "DataStore API for <resource_name>",
  "endpoint_url": "https://yoursite.com/api/3/action/resource_search/<id>",
  "endpoint_description": "https://yoursite.com/api/3/action/resource_openapi/<id>",
  "conforms_to": "https://spec.openapis.org/oas/v3.1.0"
}
```

ckanext-dcat picks this up and serializes it as `dcat:DataService` in RDF/DCAT output. The `endpoint_url` gives each resource a proper REST endpoint, and `endpoint_description` points to its OpenAPI spec. This is what Eric was asking for.

## Project structure

```
ckanext/openapi_view/
  plugin.py          # IConfigurer, IActions, IAuthFunctions, IBlueprint, IPackageController, ITemplateHelpers
  actions.py         # resource_openapi_show, dataset_openapi_show, openapi_cache_invalidate
  auth.py            # Auth functions (mirrors datastore_search / package_show)
  blueprints.py      # Flask routes for the three endpoints
  introspect.py      # Python port of deepIntrospect from swagger-explorer.js
  spec_builder.py    # OpenAPI 3.1.0 spec generation with typed responses
  type_map.py        # PostgreSQL -> JSON Schema type mapping
  cache.py           # dogpile.cache with JSON serialization (Redis or memory)
  dcat.py            # DCAT DataService injection into access_services
  helpers.py         # Template helpers for spec URLs
  tests/             # pytest tests for introspection, spec builder, actions, DCAT
```

## Security notes

- Auth mirrors CKAN's own access controls: per-resource for specs, per-dataset for combined specs
- SQL identifiers are double-quoted with null byte stripping; field names validated by regex before SQL use
- Cache uses JSON serialization (not pickle) to prevent deserialization attacks on shared Redis
- Markdown/HTML escaped in all spec content to prevent XSS through Swagger UI
- Unified 403 responses (no 404 vs 403 distinction) to prevent resource enumeration
- UUID validation at both blueprint and action levels
- Dataset combined specs are not cached (they vary by user permissions)
- DCAT injection uses deep copy to avoid mutating shared dict state

## License

MIT
