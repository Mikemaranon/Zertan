import importlib
import inspect
import pkgutil

from api_m.domains.base_api import BaseAPI


def discover_domain_api_classes(package_name="api_m.domains"):
    package = importlib.import_module(package_name)
    discovered = []
    for _, module_name, _ in pkgutil.iter_modules(package.__path__):
        module = importlib.import_module(f"{package.__name__}.{module_name}")
        for _, member in inspect.getmembers(module, inspect.isclass):
            if member is BaseAPI:
                continue
            if member.__module__ != module.__name__:
                continue
            if issubclass(member, BaseAPI):
                discovered.append(member)
    return discovered


def register_domain_apis(app, user_manager, db_manager, package_name="api_m.domains"):
    registered_names = []
    for api_class in discover_domain_api_classes(package_name):
        api_class(app, user_manager, db_manager).register()
        registered_names.append(api_class.__name__)
    return registered_names
