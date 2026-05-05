import hashlib
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LITE_ROOT = Path(__file__).resolve().parents[1]
MAIN_APP_ROOT = REPO_ROOT / "app"
DEFAULT_DATA_ROOT = LITE_ROOT / "data"
DEFAULT_DB_PATH = DEFAULT_DATA_ROOT / "database" / "zertan-lite.db"
DEFAULT_MEDIA_ROOT = DEFAULT_DATA_ROOT / "assets"


def _env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_value(name, fallback_name=None, default=""):
    value = os.environ.get(name)
    if value is not None:
        return value
    if fallback_name:
        fallback_value = os.environ.get(fallback_name)
        if fallback_value is not None:
            return fallback_value
    return default


def _resolve_path(value, default_path, *, base_path=LITE_ROOT):
    raw_path = Path(value).expanduser() if value else Path(default_path)
    if not raw_path.is_absolute():
        raw_path = base_path / raw_path
    return raw_path.resolve()


def get_runtime_config():
    debug_enabled = _env_bool("ZERTAN_LITE_DEBUG", _env_bool("ZERTAN_DEBUG", False))
    secret_key = _env_value(
        "ZERTAN_LITE_SECRET_KEY",
        "SECRET_KEY",
        "zertan-lite-development-secret-key-2026-32b",
    ).strip()

    data_root = _resolve_path(_env_value("ZERTAN_LITE_DATA_DIR", "ZERTAN_DATA_DIR"), DEFAULT_DATA_ROOT)
    db_path = _resolve_path(_env_value("ZERTAN_LITE_DB_PATH", "ZERTAN_DB_PATH"), DEFAULT_DB_PATH)
    media_root = _resolve_path(_env_value("ZERTAN_LITE_MEDIA_ROOT", "ZERTAN_MEDIA_ROOT"), DEFAULT_MEDIA_ROOT)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    media_root.mkdir(parents=True, exist_ok=True)

    return {
        "app_root": MAIN_APP_ROOT,
        "repo_root": REPO_ROOT,
        "lite_root": LITE_ROOT,
        "data_root": data_root,
        "db_path": db_path,
        "media_root": media_root,
        "secret_key": secret_key,
        "instance_id": _build_instance_id(secret_key, data_root, db_path),
        "host": _env_value("ZERTAN_LITE_HOST", "HOST", "0.0.0.0"),
        "port": int(_env_value("ZERTAN_LITE_PORT", "PORT", "5051")),
        "debug": debug_enabled,
        "cookie_secure": _env_bool("ZERTAN_COOKIE_SECURE", False),
        "cookie_samesite": _env_value("ZERTAN_COOKIE_SAMESITE", default="Lax"),
        "jwt_lifetime_hours": int(_env_value("ZERTAN_LITE_JWT_HOURS", "ZERTAN_JWT_HOURS", "8")),
        "seed_demo_content": _env_bool("ZERTAN_LITE_SEED_DEMO_CONTENT", True),
        "bootstrap_admin_username": _env_value("ZERTAN_BOOTSTRAP_ADMIN_USERNAME", default="admin").strip(),
        "bootstrap_admin_password": _env_value("ZERTAN_BOOTSTRAP_ADMIN_PASSWORD"),
        "bootstrap_admin_email": _env_value("ZERTAN_BOOTSTRAP_ADMIN_EMAIL", default="admin@zertan.local").strip(),
        "lite_user_login": _env_value("ZERTAN_LITE_USER_LOGIN", default="lite").strip() or "lite",
        "lite_user_display_name": _env_value("ZERTAN_LITE_USER_NAME", default="Local User").strip() or "Local User",
        "lite_user_role": _env_value("ZERTAN_LITE_USER_ROLE", default="administrator").strip() or "administrator",
    }


def _build_instance_id(secret_key, data_root, db_path):
    raw = f"lite|{secret_key}|{Path(data_root).resolve()}|{Path(db_path).resolve()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
