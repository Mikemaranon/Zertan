# Tests

This directory contains two kinds of files:

- automated tests that are safe to run repeatedly
- manual data-generation utilities used to seed mock content for UI and workflow validation

Only files named `test_*.py` are part of the normal automated test suite.

## Automated tests

### `test_attempt_service.py`

Verifies the attempt payload pagination logic for formal exams, including page slicing and out-of-range page clamping.

### `test_live_exam_service.py`

Verifies live exam assignment behavior, especially how users are resolved from direct selections, groups, and exclusions.

### `test_package_service.py`

Verifies exam package validation rules, including required package structure and tolerance for irrelevant extra files.

## Manual test data utilities

### `generate_synthetic_exam.py`

Creates a synthetic exam bank directly in the SQLite database for manual UI testing. It is intended for pagination, filtering, study mode, and exam mode validation with large question sets.

Default behavior:

- creates exam code `ZT-400`
- creates 400 questions total
- creates 100 questions of each supported type:
  `single_select`, `multiple_choice`, `hot_spot`, `drag_drop`

Example:

```bash
.venv/bin/python tests/generate_synthetic_exam.py --code ZT-400 --count-per-type 100
```

If the exam code already exists:

```bash
.venv/bin/python tests/generate_synthetic_exam.py --code ZT-400 --count-per-type 100 --replace
```

### `seed_mock_global_stats.py`

Seeds mock users, groups, and submitted attempts for manual dashboard and platform statistics validation. It is intended for chart-heavy admin and analytics views rather than unit testing.

Example:

```bash
.venv/bin/python tests/seed_mock_global_stats.py
```
