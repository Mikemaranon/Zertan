import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(WEB_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_SERVER_ROOT))

from tests.core._support.runner import exit_code_from_results
from tests.core.all_tests import run_all as run_core
from tests.lite.domain import run_lite


def run_all():
    return [*run_core(), run_lite()]


if __name__ == "__main__":
    raise SystemExit(exit_code_from_results(run_all()))
