from .runtime_config import get_runtime_config
from .storage_paths import build_media_path, normalize_media_path, resolve_stored_path

__all__ = [
    "ProtectedPageRenderer",
    "build_media_path",
    "get_runtime_config",
    "normalize_media_path",
    "resolve_stored_path",
]


def __getattr__(name):
    if name == "ProtectedPageRenderer":
        from .page_renderer import ProtectedPageRenderer

        return ProtectedPageRenderer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
