# Zertan

<br>
<br>
<p align="center">
  <img src="app/web_app/static/assets/Zertan.png" alt="Zertan" width="340">
</p>
<br>
<br>

Zertan is a collaborative workspace for certification exam preparation.

Its purpose is straightforward:
- create exams
- run exams
- share exam packages
- maintain question banks with multiple roles working on the same platform

This repository is built for multi-user use without turning deployment into a project of its own. It is a Python application that runs on a single server, uses Flask for the web layer, and stores its data in SQLite for a simple, lightweight operational setup.

## Why It Stays Simple

Zertan is intentionally small in operational terms.

- Python is not the most minimal runtime possible, but for this workload and architecture it remains lightweight enough to run comfortably on a modest server.
- SQLite is genuinely lightweight and easy to operate, especially for a single-server deployment where simplicity and maintainability matter more than distributed scale.
- There is no heavy frontend framework, no separate frontend deployment, and no infrastructure split required to get started.

If you want a practical multi-user exam platform that is easy to understand and easy to ship, this stack is a good fit.

## Quick Start

All commands below are meant to be run from the repository root.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r app/requirements.txt
PYTHONPATH=app/web_server ZERTAN_DEBUG=1 .venv/bin/python app/web_server/main.py
```

By default, the application starts on `http://127.0.0.1:5050`.

Technical documentation lives in [`app/README.md`](app/README.md).

By default, the app seeds one administrator account:

- `admin` / `admin123`

The default catalog also includes a single mock exam:

- `ZT-100`

## Docker Deployment

The repository now includes a production-oriented container setup:

- [`deploy/docker/Dockerfile`](deploy/docker/Dockerfile)
- [`deploy/docker/compose.yml`](deploy/docker/compose.yml)
- [`deploy/docker/.env.example`](deploy/docker/.env.example)

Quick start with Docker Compose:

```bash
cd deploy/docker
cp .env.example .env
docker compose -f compose.yml up --build -d
```

Default URL:

- `http://127.0.0.1:5050`

Runtime data is stored in the named volume `zertan_data` and mounted at `/data` inside the container. That volume contains:

- the SQLite database
- uploaded assets
- imported exam package assets

Default container seed:

- `admin` / `admin123`
- mock exam `ZT-100`

For public deployments, whoever operates the stack can override:

- `ZERTAN_BOOTSTRAP_ADMIN_USERNAME`
- `ZERTAN_BOOTSTRAP_ADMIN_PASSWORD`
- `ZERTAN_SEED_DEMO_CONTENT`

`SECRET_KEY` still has to be set to a non-default value.

The container now exposes `GET /healthz` for health probes.

To deploy a published image instead of building locally, set `ZERTAN_IMAGE` in `.env`, for example:

```bash
ZERTAN_IMAGE=ghcr.io/<owner>/<repo>:1.0.0
```

Then run:

```bash
cd deploy/docker
docker compose -f compose.yml pull
docker compose -f compose.yml up -d
```

## Release Flow

The repository also includes a GitHub Actions workflow at [`.github/workflows/release-image.yml`](.github/workflows/release-image.yml).

Recommended release process:

1. Commit the release-ready state.
2. Create and push a semver tag such as `v1.0.0`.
3. Create the GitHub Release from that tag.
4. Let GitHub Actions publish the container image to GHCR.

The workflow publishes tags such as:

- `ghcr.io/<owner>/<repo>:1.0.0`
- `ghcr.io/<owner>/<repo>:1.0`
- `ghcr.io/<owner>/<repo>:latest`

For public consumption, make sure the GitHub Container Registry package is visible to the audience you want to serve.

## Runtime Configuration

The deployment-oriented environment variables are:

- `SECRET_KEY`
- `HOST_PORT`
- `ZERTAN_IMAGE`
- `ZERTAN_SEED_DEMO_CONTENT`
- `ZERTAN_BOOTSTRAP_ADMIN_USERNAME`
- `ZERTAN_BOOTSTRAP_ADMIN_PASSWORD`
- `ZERTAN_BOOTSTRAP_ADMIN_EMAIL`
- `ZERTAN_COOKIE_SECURE`
- `ZERTAN_COOKIE_SAMESITE`
- `ZERTAN_JWT_HOURS`
- `GUNICORN_WORKERS`
- `GUNICORN_THREADS`
- `GUNICORN_TIMEOUT`

## API Endpoints

| Endpoint | Methods | Description |
| --- | --- | --- |
| `/api/auth/login` | `POST` | Sign in and issue the JWT-backed session token. |
| `/api/auth/logout` | `POST` | End the current session and clear the token cookie. |
| `/api/auth/me` | `GET` | Return the authenticated user behind the current token. |
| `/api/auth/profile` | `PUT` | Update the current user profile and optional password change. |
| `/api/auth/profile/avatar` | `POST` | Upload or replace the current user avatar image. |
| `/api/users/me` | `GET` | Return the current user profile for the signed-in account. |
| `/api/users/recent-attempts` | `GET` | Return the latest exam attempts for the current user. |
| `/api/exams` | `GET`, `POST` | List exams or create a new exam bank. |
| `/api/exams/<int:exam_id>` | `GET`, `PUT`, `DELETE` | Read, update, or delete exam metadata and its dependent records. |
| `/api/exams/<int:exam_id>/study` | `GET` | Load the study-mode payload for an exam and its questions. |
| `/api/exams/<int:exam_id>/builder-meta` | `GET` | Return the metadata used to assemble an exam attempt. |
| `/api/exams/<int:exam_id>/builder` | `POST` | Create a fixed exam attempt from builder criteria. |
| `/api/exams/<int:exam_id>/questions` | `GET`, `POST` | List question-management metadata for an exam or create a new question inside it. |
| `/api/questions/<int:question_id>` | `GET`, `PUT`, `DELETE` | Read, update, or delete a question. |
| `/api/questions/<int:question_id>/archive` | `POST` | Archive a question without removing it from the system. |
| `/api/questions/<int:question_id>/check` | `POST` | Evaluate a study-mode response and return correction data. |
| `/api/attempts/<int:attempt_id>` | `GET` | Return the full payload for a saved exam attempt. |
| `/api/attempts/<int:attempt_id>/answers` | `POST` | Save in-progress answers for an attempt page. |
| `/api/attempts/<int:attempt_id>/submit` | `POST` | Submit an attempt and generate official scoring data. |
| `/api/attempts/<int:attempt_id>/result` | `GET` | Return the stored results for a submitted attempt. |
| `/api/statistics/overview` | `GET` | Return dashboard KPIs and recent performance data. |
| `/api/statistics/me` | `GET` | Return detailed personal statistics for the current user. |
| `/api/statistics/exams/<int:exam_id>` | `GET` | Return exam-specific performance statistics. |
| `/api/statistics/platform` | `GET` | Return platform-wide statistics for examiner-level users and above. |
| `/api/admin/users` | `GET`, `POST` | List users or create a new user account. |
| `/api/admin/users/<int:user_id>` | `PUT`, `DELETE` | Update or delete a user account. |
| `/api/import-export/exams/import` | `POST` | Import a zipped exam package into the platform. |
| `/api/import-export/exams/<int:exam_id>/export` | `GET` | Export an exam bank as a zipped package. |
