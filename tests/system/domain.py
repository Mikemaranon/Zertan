import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(WEB_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_SERVER_ROOT))

from tests._support.runner import exit_code_from_results, run_domain as run_domain_suite, run_test_module


def app_routes():
    return run_test_module("tests.system.test_app_routes")


def connection_info_service():
    return run_test_module("tests.system.test_connection_info_service")


def runtime_config():
    return run_test_module("tests.system.test_runtime_config")


def storage_paths():
    return run_test_module("tests.system.test_storage_paths")


def run_system():
    return run_domain_suite(
        "system",
        [
            ("app_routes", app_routes),
            ("connection_info_service", connection_info_service),
            ("runtime_config", runtime_config),
            ("storage_paths", storage_paths),
        ],
    )


run_domain = run_system


if __name__ == "__main__":
    raise SystemExit(exit_code_from_results([run_system()]))
