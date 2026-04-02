# Tests

This directory is organized by domain so API, exam, system, infrastructure, and packaging responsibilities do not live in one flat list of files.

## Structure

- `tests/users/`
  Covers authentication, user management, admin user flows, and shared auth helpers.
- `tests/exams/`
  Covers exam execution, question logic, packages, statistics, live exams, and log registry behavior.
- `tests/system/`
  Covers route protection, connection info, runtime config parsing, and stored-path helpers.
- `tests/infrastructure/`
  Covers API bootstrap, database runtime behavior, DB manager wiring, and lifecycle checks.
- `tests/packaging/`
  Covers desktop/build/release helpers and console UI generation.
- `tests/manual/`
  Contains manual data-generation utilities. These are not part of the automated suite.
- `tests/_support/`
  Shared helpers for domain runners.
- `tests/all_tests.py`
  Master runner that executes every domain in order.

## Domain runners

Each automated domain has its own `domain.py` file. That module exposes:

- one function per test file in the domain
- one function to run the whole domain

Examples:

```bash
PYTHONPATH=app/web_server .venv/bin/python -m tests.users.domain
PYTHONPATH=app/web_server .venv/bin/python -m tests.exams.domain
PYTHONPATH=app/web_server .venv/bin/python -m tests.system.domain
```

## Master runner

To execute all domains in sequence:

```bash
PYTHONPATH=app/web_server .venv/bin/python -m tests.all_tests
```

## Discovery mode

The classic unittest discovery flow still works:

```bash
PYTHONPATH=app/web_server .venv/bin/python -m unittest discover -s tests
```

## Automated coverage map

### `tests/users/`

- `test_admin_api.py`
- `test_auth_user_api.py`
- `test_base_api.py`
- `test_user_manager.py`

### `tests/exams/`

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

### `tests/system/`

- `test_app_routes.py`
- `test_connection_info_service.py`
- `test_runtime_config.py`
- `test_storage_paths.py`

### `tests/infrastructure/`

- `test_api_manager.py`
- `test_database_runtime.py`
- `test_db_manager.py`
- `test_infrastructure_lifecycle.py`

### `tests/packaging/`

- `test_build_release.py`
- `test_client_build_release.py`
- `test_desktop_launcher.py`
- `test_server_console_ui.py`

## Manual utilities

### `tests/manual/generate_synthetic_exam.py`

Creates a synthetic exam bank directly in the SQLite database for manual UI testing. It is intended for pagination, filtering, study mode, and exam mode validation with large question sets.

Example:

```bash
.venv/bin/python tests/manual/generate_synthetic_exam.py --code ZT-400 --count-per-type 100
```

### `tests/manual/seed_mock_global_stats.py`

Seeds mock users, groups, and submitted attempts for manual dashboard and platform statistics validation.

Example:

```bash
.venv/bin/python tests/manual/seed_mock_global_stats.py
```
