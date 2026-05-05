import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(WEB_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_SERVER_ROOT))

from tests.core._support.runner import exit_code_from_results, run_domain as run_domain_suite, run_test_module


def api_manager():
    return run_test_module("tests.core.infrastructure.test_api_manager")


def database_runtime():
    return run_test_module("tests.core.infrastructure.test_database_runtime")


def db_manager():
    return run_test_module("tests.core.infrastructure.test_db_manager")


def infrastructure_lifecycle():
    return run_test_module("tests.core.infrastructure.test_infrastructure_lifecycle")


def run_infrastructure():
    return run_domain_suite(
        "infrastructure",
        [
            ("api_manager", api_manager),
            ("database_runtime", database_runtime),
            ("db_manager", db_manager),
            ("infrastructure_lifecycle", infrastructure_lifecycle),
        ],
    )


run_domain = run_infrastructure


if __name__ == "__main__":
    raise SystemExit(exit_code_from_results([run_infrastructure()]))
