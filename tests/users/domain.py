import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(WEB_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_SERVER_ROOT))

from tests._support.runner import exit_code_from_results, run_domain as run_domain_suite, run_test_module


def admin_api():
    return run_test_module("tests.users.test_admin_api")


def auth_user_api():
    return run_test_module("tests.users.test_auth_user_api")


def base_api():
    return run_test_module("tests.users.test_base_api")


def user_manager():
    return run_test_module("tests.users.test_user_manager")


def run_users():
    return run_domain_suite(
        "users",
        [
            ("admin_api", admin_api),
            ("auth_user_api", auth_user_api),
            ("base_api", base_api),
            ("user_manager", user_manager),
        ],
    )


run_domain = run_users


if __name__ == "__main__":
    raise SystemExit(exit_code_from_results([run_users()]))
