"""Template helpers for OpenAPI spec URLs."""

import ckan.plugins.toolkit as toolkit


def openapi_view_spec_url(resource_id):
    """Return the URL for a resource's OpenAPI spec."""
    site_url = toolkit.config.get("ckan.site_url", "").rstrip("/")
    return f"{site_url}/api/3/action/resource_openapi/{resource_id}"


def openapi_view_dataset_spec_url(dataset_id):
    """Return the URL for a dataset's combined OpenAPI spec."""
    site_url = toolkit.config.get("ckan.site_url", "").rstrip("/")
    return f"{site_url}/api/3/action/dataset_openapi/{dataset_id}"


def openapi_view_search_url(resource_id):
    """Return the REST-style search URL for a resource."""
    site_url = toolkit.config.get("ckan.site_url", "").rstrip("/")
    return f"{site_url}/api/3/action/resource_search/{resource_id}"


def openapi_view_page_url(resource_id):
    """Return the standalone Swagger UI page URL for a resource."""
    site_url = toolkit.config.get("ckan.site_url", "").rstrip("/")
    return f"{site_url}/openapi/resource/{resource_id}"


def openapi_view_dataset_page_url(dataset_id):
    """Return the standalone Swagger UI page URL for a dataset."""
    site_url = toolkit.config.get("ckan.site_url", "").rstrip("/")
    return f"{site_url}/openapi/dataset/{dataset_id}"


def openapi_view_swagger_ui_url(resource_id):
    """Alias for openapi_view_page_url, used in templates."""
    return openapi_view_page_url(resource_id)


def openapi_view_has_datastore(resource_id):
    """Check if a resource has data in the DataStore.

    Uses the ``datastore_active`` flag from resource metadata rather than
    querying the DataStore directly, avoiding an unnecessary database hit.
    """
    try:
        resource = toolkit.get_action("resource_show")(
            {"ignore_auth": True}, {"id": resource_id}
        )
        return resource.get("datastore_active", False)
    except Exception:
        return False


def openapi_view_dataset_has_datastore(dataset_id):
    """Check if any resource in a dataset has data in the DataStore.

    Uses ``datastore_active`` flags from package metadata, avoiding N+1
    queries to the DataStore.
    """
    try:
        pkg = toolkit.get_action("package_show")(
            {"ignore_auth": True}, {"id": dataset_id}
        )
        return any(
            res.get("datastore_active") for res in pkg.get("resources", [])
        )
    except Exception:
        return False
