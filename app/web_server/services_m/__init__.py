# services_m/__init__.py

__all__ = [
    "ServiceManager",
]


def __getattr__(name):
    if name == "ServiceManager":
        from .service_manager import ServiceManager

        return ServiceManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
