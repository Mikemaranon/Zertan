import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(WEB_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_SERVER_ROOT))

from tests._support.runner import exit_code_from_results, run_domain as run_domain_suite, run_test_module


def build_release():
    return run_test_module("tests.packaging.test_build_release")


def client_build_release():
    return run_test_module("tests.packaging.test_client_build_release")


def desktop_launcher():
    return run_test_module("tests.packaging.test_desktop_launcher")


def server_console_ui():
    return run_test_module("tests.packaging.test_server_console_ui")


def run_packaging():
    return run_domain_suite(
        "packaging",
        [
            ("build_release", build_release),
            ("client_build_release", client_build_release),
            ("desktop_launcher", desktop_launcher),
            ("server_console_ui", server_console_ui),
        ],
    )


run_domain = run_packaging


if __name__ == "__main__":
    raise SystemExit(exit_code_from_results([run_packaging()]))
