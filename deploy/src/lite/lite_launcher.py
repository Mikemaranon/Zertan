import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy.src.server import server_launcher as base_launcher


APP_NAME = "Zertan Lite"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5051
DEFAULT_USER_LOGIN = "lite"
DEFAULT_USER_NAME = "Local User"
DEFAULT_USER_ROLE = "administrator"

frozen_resource_root = base_launcher.frozen_resource_root
resolve_bundle_root = base_launcher.resolve_bundle_root
wait_for_healthcheck = base_launcher.wait_for_healthcheck
_ServerThread = base_launcher._ServerThread
stop_server = base_launcher.stop_server
port_is_available = base_launcher.port_is_available
choose_port = base_launcher.choose_port
fallback_display_host = base_launcher.fallback_display_host
build_connection_info_service = base_launcher.build_connection_info_service
detect_primary_lan_host = base_launcher.detect_primary_lan_host
ensure_secret_key = base_launcher.ensure_secret_key


def resolve_app_root(project_root=None):
    return Path(project_root or resolve_bundle_root()) / "app"


def prepare_import_paths(project_root=None):
    if getattr(sys, "frozen", False):
        return

    root = Path(project_root or resolve_bundle_root()).resolve()
    web_server_root = root / "app" / "web_server"
    for path in (root, web_server_root):
        raw = str(path)
        if raw not in sys.path:
            sys.path.insert(0, raw)


def default_data_dir(platform_name=None, env=None, home=None):
    env = env or os.environ
    platform_name = platform_name or sys.platform
    home_path = Path(home or Path.home())

    if platform_name.startswith("win"):
        base_path = Path(env.get("APPDATA") or (home_path / "AppData" / "Roaming"))
    elif platform_name == "darwin":
        base_path = home_path / "Library" / "Application Support"
    else:
        base_path = Path(env.get("XDG_DATA_HOME") or (home_path / ".local" / "share"))

    return base_path / APP_NAME


def apply_desktop_environment(*, data_dir, host, port):
    data_root = Path(data_dir).resolve()
    os.environ.setdefault("ZERTAN_LITE_DATA_DIR", str(data_root))
    os.environ.setdefault("HOST", host)
    os.environ.setdefault("PORT", str(port))
    os.environ.setdefault("ZERTAN_LITE_SEED_DEMO_CONTENT", "1")
    os.environ.setdefault("ZERTAN_LITE_USER_LOGIN", DEFAULT_USER_LOGIN)
    os.environ.setdefault("ZERTAN_LITE_USER_NAME", DEFAULT_USER_NAME)
    os.environ.setdefault("ZERTAN_LITE_USER_ROLE", DEFAULT_USER_ROLE)
    os.environ.setdefault("ZERTAN_COOKIE_SECURE", "false")
    os.environ.setdefault("ZERTAN_COOKIE_SAMESITE", "Lax")
    os.environ.setdefault("ZERTAN_LITE_JWT_HOURS", "8")
    os.environ.setdefault("SECRET_KEY", ensure_secret_key(data_root))
    return data_root


def create_desktop_app(project_root=None):
    prepare_import_paths(project_root)

    from lite.web_server.server import create_app

    app = create_app(run_server=False)
    backend = app.extensions["lite_server"]
    return app, backend


def build_argument_parser():
    parser = argparse.ArgumentParser(description="Launch Zertan Lite.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Server bind host. Default: 0.0.0.0")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Preferred TCP port. Default: 5051")
    parser.add_argument("--data-dir", default="", help="Persistent data directory for Zertan Lite state.")
    parser.add_argument("--headless", action="store_true", help="Do not display the local app window.")
    return parser


def run_headless_loop(*, server_thread, display_host, port):
    print(f"{APP_NAME} is listening on {display_host}:{port}")
    print(f"Data directory: {Path(os.environ['ZERTAN_LITE_DATA_DIR']).resolve()}")
    print(f"Local user: {os.environ['ZERTAN_LITE_USER_LOGIN']}")
    print("Press Ctrl+C to stop the server.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping Zertan Lite...")
        stop_server(server_thread)


def show_client_window(*, port, server_thread):
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError("pywebview is not available for the Zertan Lite desktop window.") from exc

    def on_close():
        stop_server(server_thread)

    base_url = f"http://127.0.0.1:{port}"

    window = webview.create_window(
        APP_NAME,
        url=f"{base_url}/home",
        width=1480,
        height=960,
        resizable=True,
    )
    window.events.closed += on_close
    webview.start()


def run_with_gui_fallback(*, port, server_thread):
    try:
        show_client_window(port=port, server_thread=server_thread)
        return
    except Exception as exc:
        print(f"Desktop app window is unavailable: {exc}")
        print("Falling back to headless Lite mode.")

    run_headless_loop(server_thread=server_thread, display_host=display_host, port=port)


def main(argv=None):
    args = build_argument_parser().parse_args(argv)
    data_dir = Path(args.data_dir).expanduser() if args.data_dir else default_data_dir()
    chosen_port = choose_port(args.host, args.port)
    apply_desktop_environment(data_dir=data_dir, host=args.host, port=chosen_port)

    app, backend = create_desktop_app()
    display_host = detect_primary_lan_host(
        db_manager=backend.DBManager,
        runtime_config=backend.runtime_config,
        bind_host=args.host,
    )
    base_url = f"http://{fallback_display_host(args.host)}:{chosen_port}"
    server_thread = _ServerThread(args.host, chosen_port, app)
    server_thread.start()

    if not wait_for_healthcheck(base_url):
        stop_server(server_thread)
        raise RuntimeError("Zertan Lite did not become healthy in time.")

    if args.headless:
        run_headless_loop(server_thread=server_thread, display_host=display_host, port=chosen_port)
        return

    run_with_gui_fallback(port=chosen_port, server_thread=server_thread)


if __name__ == "__main__":
    main()
