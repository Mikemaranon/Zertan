import argparse
import os
import secrets
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from flask import Flask
from werkzeug.serving import make_server


APP_NAME = "Zertan"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5050
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"
DEFAULT_ADMIN_EMAIL = "admin@zertan.local"


def resolve_bundle_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


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

    from server import Server

    app_root = resolve_app_root(project_root)
    app = Flask(
        __name__,
        template_folder=str(app_root / "web_app"),
        static_folder=str(app_root / "web_app" / "static"),
    )
    Server(app, run_server=False)
    return app


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
        self.server = make_server(host, port, app, threaded=True)

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


def build_argument_parser():
    parser = argparse.ArgumentParser(description="Launch the Zertan local server.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Server bind host. Default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Preferred TCP port. Default: 5050")
    parser.add_argument("--data-dir", default="", help="Persistent data directory for Zertan state.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically.")
    return parser


def main(argv=None):
    args = build_argument_parser().parse_args(argv)
    data_dir = Path(args.data_dir).expanduser() if args.data_dir else default_data_dir()
    chosen_port = choose_port(args.host, args.port)
    apply_desktop_environment(data_dir=data_dir, host=args.host, port=chosen_port)

    app = create_desktop_app()
    base_url = f"http://{args.host}:{chosen_port}"
    server_thread = _ServerThread(args.host, chosen_port, app)
    server_thread.start()

    if not wait_for_healthcheck(base_url):
        server_thread.shutdown()
        raise RuntimeError("Zertan did not become healthy in time.")

    print(f"{APP_NAME} started at {base_url}")
    print(f"Data directory: {Path(os.environ['ZERTAN_DATA_DIR']).resolve()}")
    print(f"Default login: {DEFAULT_ADMIN_USERNAME} / {DEFAULT_ADMIN_PASSWORD}")
    print("Press Ctrl+C to stop the server.")

    if not args.no_browser:
        webbrowser.open(base_url)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping Zertan...")
        server_thread.shutdown()
        server_thread.join(timeout=5)


if __name__ == "__main__":
    main()
