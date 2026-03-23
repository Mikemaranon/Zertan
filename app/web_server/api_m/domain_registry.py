import importlib
import inspect
import pkgutil

from api_m.domains.base_api import BaseAPI


FALLBACK_DOMAIN_MODULES = (
    "admin_api",
    "attempts_api",
    "auth_api",
    "exams_api",
    "import_export_api",
    "live_exams_api",
    "questions_api",
    "statistics_api",
    "user_api",
)


def _discover_domain_module_names(package):
    discovered_names = [module_name for _, module_name, _ in pkgutil.iter_modules(package.__path__)]
    if discovered_names:
        return discovered_names
    return list(FALLBACK_DOMAIN_MODULES)


def discover_domain_api_classes(package_name="api_m.domains"):
    package = importlib.import_module(package_name)
    discovered = []
    for module_name in _discover_domain_module_names(package):
        module = importlib.import_module(f"{package.__name__}.{module_name}")
        for _, member in inspect.getmembers(module, inspect.isclass):
            if member is BaseAPI:
                continue
            if member.__module__ != module.__name__:
                continue
            if issubclass(member, BaseAPI):
                discovered.append(member)
    return discovered


def register_domain_apis(app, user_manager, db_manager, service_manager, package_name="api_m.domains"):
    registered_names = []
    for api_class in discover_domain_api_classes(package_name):
        api_class(app, user_manager, db_manager, service_manager).register()
        registered_names.append(api_class.__name__)
    return registered_names
