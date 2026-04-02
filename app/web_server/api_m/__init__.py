# api_m/__init__.py

__all__ = [
    "ApiManager",
]


def __getattr__(name):
    if name == "ApiManager":
        from .api_manager import ApiManager

        return ApiManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
