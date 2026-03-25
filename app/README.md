# Zertan Technical Notes

This document describes the code structure and operational behavior under `app/`.

## Stack

- Python
- Flask
- SQLite
- PyJWT
- HTML
- CSS
- Vanilla JavaScript

The application remains server-rendered. There is no SPA runtime, no frontend build pipeline, and no database service outside SQLite.

## Backend Structure

- [`app/web_server/main.py`](/Users/myke/Desktop/codes/Projects/Zertan/app/web_server/main.py)
  Local entrypoint for Werkzeug-based runs.

- [`app/web_server/wsgi.py`](/Users/myke/Desktop/codes/Projects/Zertan/app/web_server/wsgi.py)
  WSGI entrypoint used by Gunicorn and container deployments.

- [`app/web_server/server.py`](/Users/myke/Desktop/codes/Projects/Zertan/app/web_server/server.py)
  Creates the Flask app, loads runtime config, wires managers, routes, and services.

- [`app/web_server/app_routes.py`](/Users/myke/Desktop/codes/Projects/Zertan/app/web_server/app_routes.py)
  Registers server-rendered HTML routes and shared protected-page behavior.

- [`app/web_server/api_m`](/Users/myke/Desktop/codes/Projects/Zertan/app/web_server/api_m)
  API bootstrap and domain-specific Flask endpoints.

- [`app/web_server/data_m`](/Users/myke/Desktop/codes/Projects/Zertan/app/web_server/data_m)
  SQLite database bootstrap, migrations, seed logic, and repository-style table access.

- [`app/web_server/services_m`](/Users/myke/Desktop/codes/Projects/Zertan/app/web_server/services_m)
  Service-layer logic for question evaluation, fixed attempts, live exams, and package import/export.

- [`app/web_server/user_m`](/Users/myke/Desktop/codes/Projects/Zertan/app/web_server/user_m)
  JWT auth, role hierarchy, login lifecycle, and profile management.

- [`app/web_server/support_m`](/Users/myke/Desktop/codes/Projects/Zertan/app/web_server/support_m)
  Runtime config, storage path helpers, and protected page rendering.

## Frontend Structure

- [`app/web_app/shared`](/Users/myke/Desktop/codes/Projects/Zertan/app/web_app/shared)
  Shared layouts and base templates.

- [`app/web_app/auth`](/Users/myke/Desktop/codes/Projects/Zertan/app/web_app/auth)
  Login view.

- [`app/web_app/home`](/Users/myke/Desktop/codes/Projects/Zertan/app/web_app/home)
  Dashboard, catalog, profile, live exams, and platform statistics views.

- [`app/web_app/exam`](/Users/myke/Desktop/codes/Projects/Zertan/app/web_app/exam)
  Study mode, builder, exam runner, and results pages.

- [`app/web_app/management`](/Users/myke/Desktop/codes/Projects/Zertan/app/web_app/management)
  Exam management, question management, question editor, and admin panel.

- [`app/web_app/static/JS`](/Users/myke/Desktop/codes/Projects/Zertan/app/web_app/static/JS)
  Vanilla JS modules split into `core`, `components`, and page scripts.

- [`app/web_app/static/CSS`](/Users/myke/Desktop/codes/Projects/Zertan/app/web_app/static/CSS)
  Tokens, layout, component styles, and page-specific CSS.

## Data Model

Primary tables:

- `users`
- `user_groups`
- `user_group_memberships`
- `sessions`
- `exams`
- `tags`
- `topics`
- `exam_tags`
- `exam_group_assignments`
- `questions`
- `question_options`
- `question_assets`
- `question_tags`
- `question_topics`
- `exam_attempts`
- `exam_attempt_questions`
- `exam_answers`
- `live_exams`
- `live_exam_assignments`
- `site_features`
- `data_logs`
- `agent_logs`

Notable operational rules:

- study mode does not persist official KPI data
- exam mode creates a fixed server-built attempt
- attempt pages are frozen in groups of 5 questions
- question import/export uses `exam.json`, one JSON file per question, and related assets
- uploaded files and imported assets live under the runtime media root, not inside static source assets

## Runtime Configuration

Important environment variables:

- `SECRET_KEY`
- `HOST`
- `PORT`
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

Behavior summary:

- with `ZERTAN_DEBUG=1`, demo content is enabled by default on a fresh database
- with `ZERTAN_SEED_DEMO_CONTENT=0`, the first startup requires `ZERTAN_BOOTSTRAP_ADMIN_PASSWORD`
- local default database path is `app/web_server/data_m/database/zertan.db`
- local default media path is `app/web_server/data_m/assets`
- Docker uses `/data` as the operational data root

## Running The App

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r app/requirements.txt
PYTHONPATH=app/web_server ZERTAN_DEBUG=1 .venv/bin/python app/web_server/main.py
```

Production-style local run on a fresh database:

```bash
SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')" \
ZERTAN_BOOTSTRAP_ADMIN_PASSWORD='ChangeThisAdminPassword' \
PYTHONPATH=app/web_server \
.venv/bin/python app/web_server/main.py
```

Gunicorn entrypoint:

```bash
gunicorn --chdir app/web_server --bind 0.0.0.0:5050 wsgi:app
```

## Testing

Run all automated tests:

```bash
PYTHONPATH=app/web_server .venv/bin/python -m unittest discover -s tests
```

Coverage focus today:

- authentication, role checks, and profile rules
- route protection and API registration
- question normalization, parsing, and public/private payload shaping
- exam pagination and live exam assignment behavior
- import/export archive validation
- bootstrap/runtime database behavior and query batching on question reads

Still relatively thin:

- browser-level end-to-end flows
- full request/response integration coverage for every API domain
- performance regression checks against larger SQLite datasets

## Deployment

Docker assets:

- [`deploy/src/docker/Dockerfile`](/Users/myke/Desktop/codes/Projects/Zertan/deploy/src/docker/Dockerfile)
- [`deploy/src/docker/compose.yml`](/Users/myke/Desktop/codes/Projects/Zertan/deploy/src/docker/compose.yml)
- [`deploy/src/docker/compose.ghcr.yml`](/Users/myke/Desktop/codes/Projects/Zertan/deploy/src/docker/compose.ghcr.yml)
- [`deploy/src/docker/.env.example`](/Users/myke/Desktop/codes/Projects/Zertan/deploy/src/docker/.env.example)

Server packaging assets:

- [`deploy/src/server/desktop_launcher.py`](/Users/myke/Desktop/codes/Projects/Zertan/deploy/src/server/desktop_launcher.py)
- [`deploy/src/server/server_launcher.py`](/Users/myke/Desktop/codes/Projects/Zertan/deploy/src/server/server_launcher.py)
- [`deploy/src/server/build_release.py`](/Users/myke/Desktop/codes/Projects/Zertan/deploy/src/server/build_release.py)
- [`deploy/src/server/zertan.spec`](/Users/myke/Desktop/codes/Projects/Zertan/deploy/src/server/zertan.spec)

Client packaging assets:

- [`deploy/src/client/package.json`](/Users/myke/Desktop/codes/Projects/Zertan/deploy/src/client/package.json)
- [`deploy/src/client/build_release.py`](/Users/myke/Desktop/codes/Projects/Zertan/deploy/src/client/build_release.py)
- [`deploy/src/client/src-tauri/tauri.conf.json`](/Users/myke/Desktop/codes/Projects/Zertan/deploy/src/client/src-tauri/tauri.conf.json)
- [`deploy/src/client/src-tauri/src/lib.rs`](/Users/myke/Desktop/codes/Projects/Zertan/deploy/src/client/src-tauri/src/lib.rs)
- [`deploy/src/client/ui/index.html`](/Users/myke/Desktop/codes/Projects/Zertan/deploy/src/client/ui/index.html)

Build orchestration assets:

- [`deploy/builds/build.py`](/Users/myke/Desktop/codes/Projects/Zertan/deploy/builds/build.py)
- [`deploy/builds/windows`](/Users/myke/Desktop/codes/Projects/Zertan/deploy/builds/windows)
- [`deploy/builds/linux`](/Users/myke/Desktop/codes/Projects/Zertan/deploy/builds/linux)
- [`deploy/builds/mac`](/Users/myke/Desktop/codes/Projects/Zertan/deploy/builds/mac)

## Troubleshooting

`First startup requires ZERTAN_BOOTSTRAP_ADMIN_PASSWORD`

- Fresh database plus `ZERTAN_SEED_DEMO_CONTENT=0`.
- Set a bootstrap password explicitly.

`Question assets or avatars are missing after moving data directories`

- Confirm `ZERTAN_MEDIA_ROOT`.
- Legacy paths are migrated to the runtime media root during startup, but only when those files still exist.

`Tests pass locally but Docker behaves differently`

- Verify `.env` under `deploy/src/docker/`.
- Docker stores state under `/data`, not in the repository tree.
