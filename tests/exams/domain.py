import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(WEB_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_SERVER_ROOT))

from tests._support.runner import exit_code_from_results, run_domain as run_domain_suite, run_test_module


def attempt_service():
    return run_test_module("tests.exams.test_attempt_service")


def attempts_api():
    return run_test_module("tests.exams.test_attempts_api")


def exam_scope_rules():
    return run_test_module("tests.exams.test_exam_scope_rules")


def exams_api():
    return run_test_module("tests.exams.test_exams_api")


def global_exam_permissions():
    return run_test_module("tests.exams.test_global_exam_permissions")


def live_exam_service():
    return run_test_module("tests.exams.test_live_exam_service")


def live_exams_api():
    return run_test_module("tests.exams.test_live_exams_api")


def log_registry():
    return run_test_module("tests.exams.test_log_registry")


def log_registry_service():
    return run_test_module("tests.exams.test_log_registry_service")


def package_service():
    return run_test_module("tests.exams.test_package_service")


def question_logic():
    return run_test_module("tests.exams.test_question_logic")


def question_payload_parser():
    return run_test_module("tests.exams.test_question_payload_parser")


def questions_api():
    return run_test_module("tests.exams.test_questions_api")


def statistics_api():
    return run_test_module("tests.exams.test_statistics_api")


def system_and_import_export_api():
    return run_test_module("tests.exams.test_system_and_import_export_api")


def run_exams():
    return run_domain_suite(
        "exams",
        [
            ("attempt_service", attempt_service),
            ("attempts_api", attempts_api),
            ("exam_scope_rules", exam_scope_rules),
            ("exams_api", exams_api),
            ("global_exam_permissions", global_exam_permissions),
            ("live_exam_service", live_exam_service),
            ("live_exams_api", live_exams_api),
            ("log_registry", log_registry),
            ("log_registry_service", log_registry_service),
            ("package_service", package_service),
            ("question_logic", question_logic),
            ("question_payload_parser", question_payload_parser),
            ("questions_api", questions_api),
            ("statistics_api", statistics_api),
            ("system_and_import_export_api", system_and_import_export_api),
        ],
    )


run_domain = run_exams


if __name__ == "__main__":
    raise SystemExit(exit_code_from_results([run_exams()]))
