"""DCAT 3 DataService injection into resource access_services.

Injects access_services entries into DataStore resources so that
ckanext-dcat serializes them as dcat:DataService in RDF output.

Uses copy.deepcopy to avoid mutating shared dict state that other
IPackageController hooks or template rendering may reference.
"""

import copy

import ckan.plugins.toolkit as toolkit


def inject_access_services(dataset_dict):
    """Inject DCAT DataService metadata into DataStore resources.

    Called from IPackageController.after_dataset_show.

    Args:
        dataset_dict: The dataset dict from package_show.

    Returns:
        A new dataset_dict with access_services added (original not mutated).
    """
    enabled = toolkit.asbool(
        toolkit.config.get("ckanext.openapi_view.dcat_enabled", "true")
    )
    if not enabled:
        return dataset_dict

    site_url = toolkit.config.get("ckan.site_url", "").rstrip("/")

    has_ds_resources = any(
        r.get("datastore_active") for r in dataset_dict.get("resources", [])
    )
    if not has_ds_resources:
        return dataset_dict

    # Deep copy to avoid mutating shared state
    dataset_dict = copy.deepcopy(dataset_dict)

    for resource in dataset_dict.get("resources", []):
        if not resource.get("datastore_active"):
            continue

        resource_id = resource["id"]
        resource_name = (
            resource.get("name")
            or resource.get("description")
            or resource_id
        )

        service = {
            "title": f"DataStore API for {resource_name}",
            "endpoint_url": (
                f"{site_url}/api/3/action/resource_search/{resource_id}"
            ),
            "endpoint_description": (
                f"{site_url}/api/3/action/resource_openapi/{resource_id}"
            ),
            "conforms_to": "https://spec.openapis.org/oas/v3.1.0",
        }

        if "access_services" not in resource:
            resource["access_services"] = []

        # Avoid duplicates on repeated calls
        existing_urls = {
            s.get("endpoint_url") for s in resource["access_services"]
        }
        if service["endpoint_url"] not in existing_urls:
            resource["access_services"].append(service)

    return dataset_dict
