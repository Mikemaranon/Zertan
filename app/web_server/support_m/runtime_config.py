import os
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_ROOT = APP_ROOT / "data_m"
DEFAULT_DB_PATH = DEFAULT_DATA_ROOT / "database" / "zertan.db"
DEFAULT_MEDIA_ROOT = DEFAULT_DATA_ROOT / "assets"
INSECURE_SECRET_KEYS = {
    "",
    "change-this-before-production",
}


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_path(value, default_path, *, base_path=APP_ROOT):
    raw_path = Path(value).expanduser() if value else Path(default_path)
    if not raw_path.is_absolute():
        raw_path = base_path / raw_path
    return raw_path.resolve()


def get_runtime_config():
    debug_enabled = _env_bool("ZERTAN_DEBUG", False)
    secret_key = os.environ.get(
        "SECRET_KEY",
        "zertan-development-secret-key-2026-32b",
    )
    data_root = _resolve_path(os.environ.get("ZERTAN_DATA_DIR"), DEFAULT_DATA_ROOT)
    db_path = _resolve_db_path(data_root)
    media_root = _resolve_path(os.environ.get("ZERTAN_MEDIA_ROOT"), data_root / "assets")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    media_root.mkdir(parents=True, exist_ok=True)

    if not debug_enabled and secret_key.strip() in INSECURE_SECRET_KEYS:
        raise RuntimeError(
            "Production startup requires SECRET_KEY to be set to a non-default value."
        )

    return {
        "app_root": APP_ROOT,
        "data_root": data_root,
        "db_path": db_path,
        "media_root": media_root,
        "secret_key": secret_key,
        "host": os.environ.get("HOST", "0.0.0.0"),
        "port": int(os.environ.get("PORT", 5050)),
        "debug": debug_enabled,
        "cookie_secure": _env_bool("ZERTAN_COOKIE_SECURE", False),
        "cookie_samesite": os.environ.get("ZERTAN_COOKIE_SAMESITE", "Lax"),
        "jwt_lifetime_hours": int(os.environ.get("ZERTAN_JWT_HOURS", 8)),
        "seed_demo_content": _env_bool("ZERTAN_SEED_DEMO_CONTENT", debug_enabled),
        "bootstrap_admin_username": (os.environ.get("ZERTAN_BOOTSTRAP_ADMIN_USERNAME") or "").strip(),
        "bootstrap_admin_password": os.environ.get("ZERTAN_BOOTSTRAP_ADMIN_PASSWORD") or "",
        "bootstrap_admin_email": (os.environ.get("ZERTAN_BOOTSTRAP_ADMIN_EMAIL") or "").strip(),
    }


def _resolve_db_path(data_root):
    configured_db_path = os.environ.get("ZERTAN_DB_PATH")
    default_db_path = _resolve_path(None, Path(data_root) / "database" / "zertan.db")
    if configured_db_path:
        return _resolve_path(configured_db_path, default_db_path)

    legacy_db_path = _resolve_path(None, Path(data_root) / "utils" / "zertan.db")
    if legacy_db_path.exists() and not default_db_path.exists():
        default_db_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_db_path.replace(default_db_path)

        legacy_lock = legacy_db_path.with_name(f"{legacy_db_path.name}.init.lock")
        target_lock = default_db_path.with_name(f"{default_db_path.name}.init.lock")
        if legacy_lock.exists() and not target_lock.exists():
            legacy_lock.replace(target_lock)

    return default_db_path
