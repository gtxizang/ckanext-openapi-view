"""CKAN action functions for OpenAPI spec generation."""

import logging
import re

import ckan.plugins.toolkit as toolkit
from ckan.logic import side_effect_free

from dogpile.cache.api import NO_VALUE

from . import cache
from .introspect import deep_introspect
from .spec_builder import build_resource_spec, build_dataset_spec

log = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"
)

# Maximum DataStore resources to introspect per dataset to prevent
# amplification attacks (100+ queries per resource).
MAX_RESOURCES_PER_DATASET = 20


def _validate_resource_id(resource_id):
    """Validate resource_id format to prevent cache key injection."""
    if not _UUID_RE.match(resource_id):
        raise toolkit.ValidationError(
            {"resource_id": ["Must be a valid UUID"]}
        )


def _get_introspect_config():
    """Build introspect config from CKAN settings."""
    hidden_raw = toolkit.config.get(
        "ckanext.openapi_view.hidden_fields", "_id"
    )
    hidden_fields = set(
        s.strip() for s in hidden_raw.split() if s.strip()
    )
    return {
        "hidden_fields": hidden_fields,
        "enum_threshold": int(
            toolkit.config.get("ckanext.openapi_view.enum_threshold", 25)
        ),
        "max_fields": int(
            toolkit.config.get("ckanext.openapi_view.max_fields", 50)
        ),
    }


def _get_site_url():
    return toolkit.config.get("ckan.site_url", "").rstrip("/")


def _resource_spec(resource_id, context):
    """Generate (or retrieve cached) spec for a single resource.

    Auth is always checked via resource_show/package_show even on cache hits,
    because the context carries the requesting user's identity.
    """
    # resource_show and package_show enforce per-resource auth.
    # We call them BEFORE the cache check so that auth is always verified,
    # preventing stale cached specs from leaking after permission changes.
    resource = toolkit.get_action("resource_show")(
        dict(context), {"id": resource_id}
    )
    dataset = toolkit.get_action("package_show")(
        dict(context), {"id": resource["package_id"]}
    )

    cache_key = cache.resource_cache_key(resource_id)
    cached = cache.get_cached(cache_key)
    if cached is not NO_VALUE:
        return cached

    config = _get_introspect_config()
    introspection = deep_introspect(
        resource_id, context=dict(context), config=config
    )
    if introspection is None:
        return None

    site_url = _get_site_url()
    hidden_fields = list(config["hidden_fields"])
    spec = build_resource_spec(
        resource_id=resource_id,
        site_url=site_url,
        dataset_name=dataset.get("title", dataset["name"]),
        resource_name=(
            resource.get("name")
            or resource.get("description", resource_id)
        ),
        introspection=introspection,
        hidden_fields=hidden_fields,
    )

    cache.set_cached(cache_key, spec)
    return spec


@side_effect_free
def resource_openapi_show(context, data_dict):
    """Return the OpenAPI 3.1.0 spec for a DataStore resource.

    :param resource_id: the resource ID
    :returns: OpenAPI spec dict
    """
    toolkit.check_access("resource_openapi_show", context, data_dict)

    resource_id = toolkit.get_or_bust(data_dict, "resource_id")
    _validate_resource_id(resource_id)

    spec = _resource_spec(resource_id, context)
    if spec is None:
        raise toolkit.ObjectNotFound(
            "Resource not in DataStore or introspection failed"
        )
    return spec


@side_effect_free
def dataset_openapi_show(context, data_dict):
    """Return a combined OpenAPI spec for all DataStore resources in a dataset.

    :param dataset_id: the dataset ID or name
    :returns: OpenAPI spec dict

    Note: dataset-level specs are NOT cached because the set of visible
    resources varies by user permissions.  Per-resource specs are cached
    individually; only the merge is repeated.
    """
    toolkit.check_access("dataset_openapi_show", context, data_dict)

    dataset_id = toolkit.get_or_bust(data_dict, "dataset_id")

    dataset = toolkit.get_action("package_show")(
        dict(context), {"id": dataset_id}
    )

    ds_resources = [
        res for res in dataset.get("resources", [])
        if res.get("datastore_active")
    ]

    if len(ds_resources) > MAX_RESOURCES_PER_DATASET:
        log.info(
            "Dataset %s has %d DataStore resources, capping at %d",
            dataset_id, len(ds_resources), MAX_RESOURCES_PER_DATASET,
        )
        ds_resources = ds_resources[:MAX_RESOURCES_PER_DATASET]

    resource_specs = []
    for res in ds_resources:
        try:
            spec = _resource_spec(res["id"], context)
            if spec:
                res_name = (
                    res.get("name") or res.get("description", res["id"])
                )
                resource_specs.append((res_name, spec))
        except toolkit.NotAuthorized:
            log.debug("Skipping resource %s (not authorized)", res["id"])
        except Exception:
            log.warning(
                "Skipping resource %s in dataset spec",
                res["id"],
                exc_info=True,
            )

    if not resource_specs:
        raise toolkit.ObjectNotFound(
            "No accessible DataStore resources found in dataset"
        )

    site_url = _get_site_url()
    combined = build_dataset_spec(
        dataset_id=dataset_id,
        site_url=site_url,
        dataset_name=dataset.get("title", dataset["name"]),
        resource_specs=resource_specs,
    )

    return combined


def openapi_cache_invalidate(context, data_dict):
    """Invalidate cached OpenAPI spec(s).

    :param resource_id: (optional) invalidate a specific resource
    :param dataset_id: (optional) invalidate a specific dataset
    If neither given, this is a no-op.
    """
    toolkit.check_access("openapi_cache_invalidate", context, data_dict)

    resource_id = data_dict.get("resource_id")
    dataset_id = data_dict.get("dataset_id")

    invalidated = []
    if resource_id:
        _validate_resource_id(resource_id)
        cache.invalidate_resource(resource_id)
        invalidated.append(f"resource:{resource_id}")
    if dataset_id:
        cache.invalidate_dataset(dataset_id)
        invalidated.append(f"dataset:{dataset_id}")

    return {"invalidated": invalidated}
