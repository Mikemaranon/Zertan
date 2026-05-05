import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(WEB_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_SERVER_ROOT))

from tests.core._support.runner import exit_code_from_results
from tests.core.exams.domain import run_exams
from tests.core.infrastructure.domain import run_infrastructure
from tests.core.packaging.domain import run_packaging
from tests.core.system.domain import run_system
from tests.core.users.domain import run_users


def users():
    return run_users()


def exams():
    return run_exams()


def system():
    return run_system()


def infrastructure():
    return run_infrastructure()


def packaging():
    return run_packaging()


def run_all():
    return [
        users(),
        exams(),
        system(),
        infrastructure(),
        packaging(),
    ]


if __name__ == "__main__":
    raise SystemExit(exit_code_from_results(run_all()))
