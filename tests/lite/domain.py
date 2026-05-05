import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(WEB_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_SERVER_ROOT))

from tests.core._support.runner import exit_code_from_results, run_domain as run_domain_suite, run_test_module


def lite_app():
    return run_test_module("tests.lite.test_lite_app")


def run_lite():
    return run_domain_suite(
        "lite",
        [
            ("lite_app", lite_app),
        ],
    )


run_domain = run_lite


if __name__ == "__main__":
    raise SystemExit(exit_code_from_results([run_lite()]))
