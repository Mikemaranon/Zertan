from pathlib import Path


LEGACY_MEDIA_PREFIX = "web_server/data_m/assets/"
STATIC_PREFIX = "web_app/"


def normalize_media_path(stored_path):
    value = str(stored_path or "").strip().replace("\\", "/")
    if not value:
        return ""
    if value.startswith(LEGACY_MEDIA_PREFIX):
        return value[len(LEGACY_MEDIA_PREFIX):]
    if value.startswith("/"):
        return value.lstrip("/")
    return value


def build_media_path(*parts):
    clean_parts = []
    for part in parts:
        value = str(part or "").strip().replace("\\", "/").strip("/")
        if value:
            clean_parts.append(value)
    return "/".join(clean_parts)


def resolve_stored_path(stored_path, *, media_root, app_root):
    normalized = normalize_media_path(stored_path)
    if not normalized:
        return None
    if normalized.startswith(STATIC_PREFIX):
        return (Path(app_root) / normalized).resolve()
    return (Path(media_root) / normalized).resolve()
