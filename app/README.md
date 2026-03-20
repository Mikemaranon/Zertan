# Zertan Technical Notes

This document keeps the technical view of the project inside `app/`, while the repository root README stays focused on presenting the product.

## Stack

- Python
- Flask
- SQLite
- PyJWT
- HTML
- CSS
- Vanilla JavaScript

The app is server-rendered and keeps a single lightweight deployment target.

## Repository Layout

### Backend

- `app/web_server/main.py`
  Creates the Flask app and serves as the entrypoint.

- `app/web_server/server.py`
  Wires together the server, auth, data, routes, and APIs.

- `app/web_server/app_routes.py`
  Registers the server-rendered HTML routes.

- `app/web_server/api_m/domains/`
  API modules split by domain:
  - `auth_api.py`
  - `user_api.py`
  - `exams_api.py`
  - `questions_api.py`
  - `attempts_api.py`
  - `statistics_api.py`
  - `admin_api.py`
  - `import_export_api.py`

- `app/web_server/data_m/`
  SQLite data layer and repository-style table managers.

- `app/web_server/services_m/`
  Shared logic for exam assembly, question evaluation, and package import or export.

- `app/web_server/user_m/`
  Authentication, JWT handling, and role enforcement.

### Frontend

- `app/web_app/shared/`
  Shared layouts and cross-cutting templates.

- `app/web_app/auth/`
  Authentication templates.

- `app/web_app/home/`
  Workspace-facing pages such as dashboard, catalog, and profile.

- `app/web_app/exam/`
  Exam flow pages for study, builder, runner, and results.

- `app/web_app/management/`
  Management pages for exams, question editing, and administration.

- `app/web_app/static/`
  CSS, JavaScript modules, and uploaded assets.

## Run From The Repository Root

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r app/requirements.txt
PYTHONPATH=app/web_server .venv/bin/python app/web_server/main.py
```

Default local URL:

- `http://127.0.0.1:5050`

Why `PYTHONPATH=app/web_server` is needed:
- `main.py` imports sibling backend modules directly, so launching from the root requires adding `app/web_server` to Python's module search path.

For development, use:

```bash
PYTHONPATH=app/web_server ZERTAN_DEBUG=1 .venv/bin/python app/web_server/main.py
```

For container or production-style runs, the image uses Gunicorn with:

- `app/web_server/wsgi.py`
- `gunicorn --chdir app/web_server ... wsgi:app`

Container deployment assets live under:

- `deploy/docker/Dockerfile`
- `deploy/docker/compose.yml`
- `deploy/docker/.env.example`

## Runtime Configuration

The backend now supports environment-driven storage and runtime configuration.

Important variables:

- `SECRET_KEY`
- `PORT`
- `HOST`
- `ZERTAN_DEBUG`
- `ZERTAN_DATA_DIR`
- `ZERTAN_DB_PATH`
- `ZERTAN_MEDIA_ROOT`
- `ZERTAN_SEED_DEMO_CONTENT`
- `ZERTAN_BOOTSTRAP_ADMIN_USERNAME`
- `ZERTAN_BOOTSTRAP_ADMIN_PASSWORD`
- `ZERTAN_BOOTSTRAP_ADMIN_EMAIL`
- `ZERTAN_COOKIE_SECURE`
- `ZERTAN_COOKIE_SAMESITE`
- `ZERTAN_JWT_HOURS`

Default behavior:

- local development keeps using `app/web_server/data_m/utils/zertan.db`
- local development keeps using `app/web_server/data_m/assets`
- Docker stores both under `/data`

## HTML Structure

The server-rendered templates are organized by purpose:

- `app/web_app/shared/base.html`
- `app/web_app/shared/forbidden.html`
- `app/web_app/auth/login.html`
- `app/web_app/home/dashboard.html`
- `app/web_app/home/catalog.html`
- `app/web_app/home/profile.html`
- `app/web_app/exam/detail.html`
- `app/web_app/exam/builder.html`
- `app/web_app/exam/runner.html`
- `app/web_app/exam/results.html`
- `app/web_app/management/exams.html`
- `app/web_app/management/questions.html`
- `app/web_app/management/question_editor.html`
- `app/web_app/management/admin.html`

## Product Capabilities

- JWT-backed authentication
- hierarchical roles: administrator, examiner, reviewer, user
- study mode with per-question checking
- exam builder and fixed-attempt exam mode
- paginated exam runner with 5 questions per page
- persisted scoring and KPI collection
- editable question banks
- exam package import and export
- support for `single_select`, `multiple_choice`, `hot_spot`, and `drag_drop`

## Database Notes

Primary SQLite file:

- `app/web_server/data_m/utils/zertan.db`

When `ZERTAN_DB_PATH` is set, the SQLite file moves to that location instead.

Main tables include:

- `users`
- `sessions`
- `exams`
- `tags`
- `topics`
- `exam_tags`
- `questions`
- `question_options`
- `question_assets`
- `question_tags`
- `question_topics`
- `exam_attempts`
- `exam_attempt_questions`
- `exam_answers`
- `data_logs`
- `agent_logs`

Operational behavior:

- study mode does not create official attempt records
- exam mode creates fixed attempts on the server
- submitted attempts feed stored statistics and KPIs
- import and export use `zip` packages with `exam.json`, one JSON file per question, and related assets
- runtime media for questions and avatars is stored in `app/web_server/data_m/assets`
- `app/web_app/static/assets` is reserved for branded static UI assets such as the Zertan logo
- when `ZERTAN_MEDIA_ROOT` is set, uploaded files and imported assets move to that directory

## Seed Data

When `ZERTAN_DEBUG=1` or `ZERTAN_SEED_DEMO_CONTENT=1`, the app seeds:

- one administrator user
- one mock exam named `ZT-100`
- sample questions covering all supported question types

Seeded credentials:

- `admin` / `admin123`

The bootstrap user can still be overridden with:

- `ZERTAN_BOOTSTRAP_ADMIN_USERNAME`
- `ZERTAN_BOOTSTRAP_ADMIN_PASSWORD`
- `ZERTAN_BOOTSTRAP_ADMIN_EMAIL`

## Server Routes

HTML pages served by Flask:

- `GET /`
- `GET /dashboard`
- `GET /catalog`
- `GET /login`
- `GET, POST /logout`
- `GET /exams/<int:exam_id>`
- `GET /exams/<int:exam_id>/builder`
- `GET /attempts/<int:attempt_id>/run`
- `GET /attempts/<int:attempt_id>/results`
- `GET /profile`
- `GET /management/exams`
- `GET /management/exams/<int:exam_id>/questions`
- `GET /exams/<int:exam_id>/questions/new`
- `GET /questions/<int:question_id>/edit`
- `GET /admin`

## API Domains

The API is grouped into these backend modules:

- auth
- users
- exams
- questions
- attempts
- statistics
- admin
- import_export

## Current Caveats

- there is no automated browser test suite yet
- hot spot questions are currently represented through structured answer selection rather than freeform click coordinates at runtime
- question editing for drag and drop is form-based even though exam interaction is drag and drop
