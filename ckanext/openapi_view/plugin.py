"""Main plugin — wires together actions, auth, blueprints, DCAT, and helpers."""

import logging

import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit

from . import actions, auth, cache
from .blueprints import openapi_view
from .dcat import inject_access_services
from .helpers import (
    openapi_view_spec_url,
    openapi_view_dataset_spec_url,
    openapi_view_search_url,
)

log = logging.getLogger(__name__)


class OpenApiViewPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IActions)
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.IBlueprint)
    plugins.implements(plugins.IPackageController, inherit=True)
    plugins.implements(plugins.ITemplateHelpers)

    # IConfigurer

    def update_config(self, config):
        pass

    # IActions

    def get_actions(self):
        return {
            "resource_openapi_show": actions.resource_openapi_show,
            "dataset_openapi_show": actions.dataset_openapi_show,
            "openapi_cache_invalidate": actions.openapi_cache_invalidate,
        }

    # IAuthFunctions

    def get_auth_functions(self):
        return {
            "resource_openapi_show": auth.resource_openapi_show,
            "dataset_openapi_show": auth.dataset_openapi_show,
            "openapi_cache_invalidate": auth.openapi_cache_invalidate,
        }

    # IBlueprint

    def get_blueprint(self):
        return [openapi_view]

    # IPackageController

    def after_dataset_show(self, context, pkg_dict):
        return inject_access_services(pkg_dict)

    def after_dataset_update(self, context, pkg_dict):
        """Invalidate cached specs when a dataset is updated."""
        dataset_id = pkg_dict.get("id")
        if dataset_id:
            cache.invalidate_dataset(dataset_id)
            for res in pkg_dict.get("resources", []):
                cache.invalidate_resource(res["id"])

    # ITemplateHelpers

    def get_helpers(self):
        return {
            "openapi_view_spec_url": openapi_view_spec_url,
            "openapi_view_dataset_spec_url": openapi_view_dataset_spec_url,
            "openapi_view_search_url": openapi_view_search_url,
        }
