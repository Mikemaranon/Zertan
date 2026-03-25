import argparse
import os
import secrets
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

APP_NAME = "Zertan Server"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5050
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"
DEFAULT_ADMIN_EMAIL = "admin@zertan.local"


def frozen_resource_root(*, executable_path=None, platform_name=None, meipass=None):
    if meipass:
        return Path(meipass).resolve()

    executable = Path(executable_path or sys.executable).resolve()
    platform_name = platform_name or sys.platform

    if platform_name == "darwin":
        contents_root = executable.parents[1]
        for candidate in (
            contents_root / "Resources",
            contents_root / "Frameworks",
            executable.parent,
        ):
            if (candidate / "app").exists():
                return candidate
        return contents_root / "Resources"

    internal_root = executable.parent / "_internal"
    if (internal_root / "app").exists():
        return internal_root
    return executable.parent


def resolve_bundle_root():
    if getattr(sys, "frozen", False):
        return frozen_resource_root(meipass=getattr(sys, "_MEIPASS", ""))
    return Path(__file__).resolve().parents[3]


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
        base = Path(env.get("APPDATA") or (home_path / "AppData" / "Roaming"))
    elif platform_name == "darwin":
        base = home_path / "Library" / "Application Support"
    else:
        base = Path(env.get("XDG_DATA_HOME") or (home_path / ".local" / "share"))

    return base / APP_NAME


def ensure_secret_key(data_dir):
    config_dir = Path(data_dir) / "config"
    secret_path = config_dir / "secret_key.txt"
    config_dir.mkdir(parents=True, exist_ok=True)

    if secret_path.exists():
        secret = secret_path.read_text(encoding="utf-8").strip()
        if secret:
            return secret

    secret = secrets.token_urlsafe(48)
    secret_path.write_text(secret, encoding="utf-8")
    return secret


def apply_desktop_environment(*, data_dir, host, port):
    data_root = Path(data_dir).resolve()
    os.environ.setdefault("ZERTAN_DATA_DIR", str(data_root))
    os.environ.setdefault("HOST", host)
    os.environ.setdefault("PORT", str(port))
    os.environ.setdefault("ZERTAN_SEED_DEMO_CONTENT", "1")
    os.environ.setdefault("ZERTAN_BOOTSTRAP_ADMIN_USERNAME", DEFAULT_ADMIN_USERNAME)
    os.environ.setdefault("ZERTAN_BOOTSTRAP_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
    os.environ.setdefault("ZERTAN_BOOTSTRAP_ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL)
    os.environ.setdefault("ZERTAN_COOKIE_SECURE", "false")
    os.environ.setdefault("ZERTAN_COOKIE_SAMESITE", "Lax")
    os.environ.setdefault("ZERTAN_JWT_HOURS", "8")
    os.environ.setdefault("SECRET_KEY", ensure_secret_key(data_root))
    return data_root


def port_is_available(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock.connect_ex((host, port)) != 0


def choose_port(host, preferred_port):
    if port_is_available(host, preferred_port):
        return preferred_port

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def create_desktop_app(project_root=None):
    prepare_import_paths(project_root)

    from flask import Flask
    from server import Server

    app_root = resolve_app_root(project_root)
    app = Flask(
        __name__,
        template_folder=str(app_root / "web_app"),
        static_folder=str(app_root / "web_app" / "static"),
    )
    backend = Server(app, run_server=False)
    return app, backend


def wait_for_healthcheck(base_url, timeout_seconds=15):
    deadline = time.time() + timeout_seconds
    health_url = f"{base_url}/healthz"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=1) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.2)
    return False


class _ServerThread(threading.Thread):
    def __init__(self, host, port, app):
        super().__init__(daemon=True)
        from werkzeug.serving import make_server

        self.server = make_server(host, port, app, threaded=True)

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


def build_argument_parser():
    parser = argparse.ArgumentParser(description="Launch the Zertan web server.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Server bind host. Default: 0.0.0.0")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Preferred TCP port. Default: 5050")
    parser.add_argument("--data-dir", default="", help="Persistent data directory for Zertan state.")
    parser.add_argument("--headless", action="store_true", help="Do not display the local server status window.")
    return parser


def fallback_display_host(bind_host):
    host = str(bind_host or "").strip()
    if host in {"", "0.0.0.0", "::"}:
        return "127.0.0.1"
    return host


def build_connection_info_service(*, db_manager, runtime_config):
    from services_m.connection_info_service import ConnectionInfoService

    return ConnectionInfoService(db_manager, runtime_config=runtime_config)


def detect_primary_lan_host(*, db_manager, runtime_config, bind_host):
    service = build_connection_info_service(db_manager=db_manager, runtime_config=runtime_config)
    detected_ipv4s = service.list_detected_ipv4_addresses()
    primary_lan_ip = service._select_primary_lan_ip(detected_ipv4s)
    return primary_lan_ip or fallback_display_host(bind_host)


def stop_server(server_thread):
    server_thread.shutdown()
    server_thread.join(timeout=5)


def run_headless_loop(*, server_thread, display_host, port):
    print(f"{APP_NAME} is listening on {display_host}:{port}")
    print(f"Data directory: {Path(os.environ['ZERTAN_DATA_DIR']).resolve()}")
    print(f"Default login: {DEFAULT_ADMIN_USERNAME} / {DEFAULT_ADMIN_PASSWORD}")
    print("Press Ctrl+C to stop the server.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping Zertan...")
        stop_server(server_thread)


def show_server_status_window(*, display_host, port, server_thread):
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError("pywebview is not available for the Zertan Server status window.") from exc

    html = f"""\
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <style>
          :root {{
            color-scheme: light;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          }}
          body {{
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            background: #f6f8fb;
            color: #1f2937;
          }}
          main {{
            width: 100%;
            box-sizing: border-box;
            padding: 24px;
            text-align: center;
          }}
          h1 {{
            margin: 0 0 10px;
            font-size: 22px;
            font-weight: 700;
          }}
          p {{
            margin: 0;
            font-size: 15px;
            color: #4b5563;
          }}
        </style>
      </head>
      <body>
        <main>
          <h1>Server is up!</h1>
          <p>Running in {display_host}:{port}</p>
        </main>
      </body>
    </html>
    """

    def on_close():
        stop_server(server_thread)

    window = webview.create_window(
        APP_NAME,
        html=html,
        width=360,
        height=160,
        resizable=False,
    )
    window.events.closed += on_close
    webview.start()


def run_with_gui_fallback(*, display_host, port, server_thread):
    try:
        show_server_status_window(display_host=display_host, port=port, server_thread=server_thread)
        return
    except Exception as exc:
        print(f"Server status window is unavailable: {exc}")
        print("Falling back to headless server mode.")

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
        raise RuntimeError("Zertan did not become healthy in time.")

    if args.headless:
        run_headless_loop(server_thread=server_thread, display_host=display_host, port=chosen_port)
        return

    run_with_gui_fallback(display_host=display_host, port=chosen_port, server_thread=server_thread)


if __name__ == "__main__":
    main()
