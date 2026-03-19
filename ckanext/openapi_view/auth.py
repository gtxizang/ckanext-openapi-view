"""Auth functions — mirror datastore_search access checks.

resource_openapi_show and dataset_openapi_show need
@auth_allow_anonymous_access so that anonymous users can reach the
auth function body for public resources.  Without it, CKAN's auth
middleware rejects anonymous requests before the function runs.
"""

import ckan.plugins.toolkit as toolkit


@toolkit.auth_allow_anonymous_access
def resource_openapi_show(context, data_dict):
    """Allow if user can datastore_search this resource."""
    try:
        toolkit.check_access(
            "datastore_search", context,
            {"resource_id": data_dict.get("resource_id")},
        )
        return {"success": True}
    except toolkit.NotAuthorized:
        return {
            "success": False,
            "msg": "User not authorized to access this resource",
        }


@toolkit.auth_allow_anonymous_access
def dataset_openapi_show(context, data_dict):
    """Allow if user can read the dataset."""
    try:
        toolkit.check_access(
            "package_show", context,
            {"id": data_dict.get("dataset_id")},
        )
        return {"success": True}
    except toolkit.NotAuthorized:
        return {
            "success": False,
            "msg": "User not authorized to access this dataset",
        }


def openapi_cache_invalidate(context, data_dict):
    """Sysadmin only — returns ``{"success": False}`` by convention.

    In CKAN's auth system, returning ``success: False`` denies access for
    normal users.  However, CKAN automatically grants sysadmins access to
    *all* actions before the auth function is even called, so sysadmins
    bypass this denial entirely.  This is the standard CKAN pattern for
    sysadmin-only actions.
    """
    return {"success": False, "msg": "Only sysadmins may invalidate the cache"}
