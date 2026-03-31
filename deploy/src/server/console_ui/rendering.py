import json
from pathlib import Path


CLIENT_CSS_PATHS = (
    ("core", "tokens.css"),
    ("components", "buttons.css"),
    ("components", "forms.css"),
    ("components", "profile-modal.css"),
    ("components", "selection-field.css"),
    ("pages", "management", "admin.css"),
)

SERVER_CSS_PATHS = (
    ("css", "core", "base.css"),
    ("css", "layout", "shell.css"),
    ("css", "components", "navigation.css"),
    ("css", "components", "panels.css"),
    ("css", "components", "modal.css"),
    ("css", "components", "overlay.css"),
    ("css", "views", "directory.css"),
    ("css", "views", "activity.css"),
    ("css", "layout", "responsive.css"),
)

SERVER_JS_PATHS = (
    ("js", "core", "app.js"),
    ("js", "components", "common.js"),
    ("js", "controllers", "directory.js"),
    ("js", "controllers", "modal.js"),
    ("js", "views", "overview.js"),
    ("js", "views", "directory.js"),
    ("js", "views", "features.js"),
    ("js", "views", "activity.js"),
    ("js", "controllers", "nav.js"),
    ("js", "controllers", "app_controller.js"),
    ("js", "bootstrap.js"),
)


def build_server_console_html(*, app_root, initial_snapshot, asset_root=None):
    client_css = _load_client_css(app_root)
    console_asset_root = Path(asset_root).resolve() if asset_root else Path(__file__).resolve().parent / "assets"
    bootstrap = json.dumps(initial_snapshot, ensure_ascii=True).replace("</", "<\\/")
    html = _read_asset(console_asset_root, "templates", "document.html")
    html = html.replace("__CLIENT_CSS__", client_css)
    html = html.replace("__SERVER_CSS__", _load_asset_bundle(console_asset_root, SERVER_CSS_PATHS))
    html = html.replace("__SHELL_HTML__", _render_shell(console_asset_root))
    html = html.replace("__BOOTSTRAP__", bootstrap)
    html = html.replace("__SCRIPT__", _load_asset_bundle(console_asset_root, SERVER_JS_PATHS))
    return html


def _load_client_css(app_root):
    static_root = Path(app_root) / "web_app" / "static" / "CSS"
    chunks = []
    for parts in CLIENT_CSS_PATHS:
        css_path = static_root.joinpath(*parts)
        if css_path.exists():
            chunks.append(css_path.read_text(encoding="utf-8"))
    return "\n\n".join(chunks)


def _render_shell(asset_root):
    html = _read_asset(asset_root, "templates", "shell.html")
    html = html.replace("__SIDEBAR__", _read_asset(asset_root, "templates", "fragments", "sidebar.html"))
    html = html.replace("__MOBILE_HEADER__", _read_asset(asset_root, "templates", "fragments", "mobile_header.html"))
    html = html.replace("__DETAIL_MODAL__", _read_asset(asset_root, "templates", "fragments", "detail_modal.html"))
    return html


def _load_asset_bundle(asset_root, paths):
    return "\n\n".join(_read_asset(asset_root, *parts) for parts in paths)


def _read_asset(asset_root, *parts):
    return Path(asset_root, *parts).read_text(encoding="utf-8")
