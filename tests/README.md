# Tests

This directory is split into two groups:

- `tests/core/` for the main Zertan application and shared packaging/build coverage
- `tests/lite/` for Zertan Lite-specific automated coverage

## Structure

- `tests/core/users/`
  Covers authentication, user management, admin user flows, and shared auth helpers.
- `tests/core/exams/`
  Covers exam execution, question logic, packages, statistics, live exams, and log registry behavior.
- `tests/core/system/`
  Covers route protection, connection info, runtime config parsing, and stored-path helpers.
- `tests/core/infrastructure/`
  Covers API bootstrap, database runtime behavior, DB manager wiring, and lifecycle checks.
- `tests/core/packaging/`
  Covers desktop/build/release helpers, build entrypoints, Lite packaging, and console UI generation.
- `tests/core/manual/`
  Contains manual data-generation utilities. These are not part of the automated suite.
- `tests/core/_support/`
  Shared helpers for domain runners.
- `tests/lite/`
  Covers Lite routing, session bootstrapping, and reduced primary navigation behavior.
- `tests/all_tests.py`
  Master runner that executes `core` and `lite` in order.

## Domain runners

Each automated domain has its own `domain.py` file. That module exposes:

- one function per test file in the domain
- one function to run the whole domain

Examples:

```bash
PYTHONPATH=app/web_server .venv/bin/python -m tests.core.users.domain
PYTHONPATH=app/web_server .venv/bin/python -m tests.core.exams.domain
PYTHONPATH=app/web_server .venv/bin/python -m tests.core.system.domain
PYTHONPATH=app/web_server .venv/bin/python -m tests.lite.domain
```

## Master runner

To execute the core domains in sequence:

```bash
PYTHONPATH=app/web_server .venv/bin/python -m tests.core.all_tests
```

To execute both `core` and `lite` in sequence:

```bash
PYTHONPATH=app/web_server .venv/bin/python -m tests.all_tests
```

## Discovery mode

The classic unittest discovery flow still works:

```bash
PYTHONPATH=app/web_server .venv/bin/python -m unittest discover -s tests -t .
```

## Automated coverage map

### `tests/core/users/`

- `test_admin_api.py`
- `test_auth_user_api.py`
- `test_base_api.py`
- `test_user_manager.py`

### `tests/core/exams/`

- `test_attempt_service.py`
- `test_attempts_api.py`
- `test_exam_scope_rules.py`
- `test_exams_api.py`
- `test_global_exam_permissions.py`
- `test_live_exam_service.py`
- `test_live_exams_api.py`
- `test_log_registry.py`
- `test_log_registry_service.py`
- `test_package_service.py`
- `test_question_logic.py`
- `test_question_payload_parser.py`
- `test_questions_api.py`
- `test_statistics_api.py`
- `test_system_and_import_export_api.py`

### `tests/core/system/`

- `test_app_routes.py`
- `test_connection_info_service.py`
- `test_runtime_config.py`
- `test_storage_paths.py`

### `tests/core/infrastructure/`

- `test_api_manager.py`
- `test_database_runtime.py`
- `test_db_manager.py`
- `test_infrastructure_lifecycle.py`

### `tests/core/packaging/`

- `test_build_release.py`
- `test_builds_entrypoint.py`
- `test_client_build_release.py`
- `test_desktop_launcher.py`
- `test_lite_build_release.py`
- `test_server_console_ui.py`

### `tests/lite/`

- `test_lite_app.py`

## Manual utilities

### `tests/core/manual/generate_synthetic_exam.py`

Creates a synthetic exam bank directly in the SQLite database for manual UI testing. It is intended for pagination, filtering, study mode, and exam mode validation with large question sets.

Example:

```bash
.venv/bin/python tests/core/manual/generate_synthetic_exam.py --code ZT-400 --count-per-type 100
```

### `tests/core/manual/seed_mock_global_stats.py`

Seeds mock users, groups, and submitted attempts for manual dashboard and platform statistics validation.

Example:

```bash
.venv/bin/python tests/core/manual/seed_mock_global_stats.py
```
