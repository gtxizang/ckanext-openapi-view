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
