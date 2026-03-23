# Zertan

<br>
<br>
<p align="center">
  <img src="app/web_app/static/assets/Zertan.png" alt="Zertan" width="340">
</p>
<br>
<br>

Zertan is a serious certification exam preparation platform built on a small operational stack:

- Flask for the web layer
- SQLite for persistence
- JWT-backed sessions for authentication
- HTML, CSS, and vanilla JavaScript for the frontend

The project is intentionally server-rendered and single-server friendly. It supports role-based administration, study mode, formal exam mode, editable question banks, import/export packages, and persisted statistics without introducing a separate SPA or infrastructure-heavy deployment model.

## Prerequisites

- Python 3.12 or newer
- `venv`
- Docker Desktop or Docker Engine if you want to run the containerized deployment

## Local Development

Run these commands from the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r app/requirements.txt
PYTHONPATH=app/web_server ZERTAN_DEBUG=1 .venv/bin/python app/web_server/main.py
```

Default URL:

- `http://127.0.0.1:5050`

When `ZERTAN_DEBUG=1`, Zertan seeds demo content automatically on a fresh database:

- user: `admin`
- password: `admin123`
- demo exam: `ZT-100`

## First Run Without Demo Seed

Production-style startup requires an explicit admin bootstrap password on a fresh database:

```bash
SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')" \
ZERTAN_BOOTSTRAP_ADMIN_PASSWORD='ChangeThisAdminPassword' \
PYTHONPATH=app/web_server \
.venv/bin/python app/web_server/main.py
```

If `ZERTAN_SEED_DEMO_CONTENT=0` and no users exist yet, Zertan will refuse to start without `ZERTAN_BOOTSTRAP_ADMIN_PASSWORD`.

## Testing

Run the automated suite from the repository root:

```bash
PYTHONPATH=app/web_server .venv/bin/python -m unittest discover -s tests
```

What is covered today:

- auth and role handling
- protected routes and API bootstrap
- question normalization and payload parsing
- exam pagination and live exam assignment rules
- import/export package validation
- database bootstrap behavior and query batching for question retrieval

Manual data generators live in [`tests/README.md`](/Users/myke/Desktop/codes/Projects/Zertan/tests/README.md).

## Project Layout

- [`app/web_server`](/Users/myke/Desktop/codes/Projects/Zertan/app/web_server): Flask app, APIs, services, data layer, auth, and runtime helpers
- [`app/web_app`](/Users/myke/Desktop/codes/Projects/Zertan/app/web_app): server-rendered templates plus vanilla JS and CSS
- [`deploy/docker`](/Users/myke/Desktop/codes/Projects/Zertan/deploy/docker): container image and compose files
- [`deploy/desktop`](/Users/myke/Desktop/codes/Projects/Zertan/deploy/desktop): PyInstaller-based desktop packaging
- [`tests`](/Users/myke/Desktop/codes/Projects/Zertan/tests): automated tests and manual data utilities

Technical details live in [`app/README.md`](/Users/myke/Desktop/codes/Projects/Zertan/app/README.md).

## Docker

Local image build:

```bash
cd deploy/docker
cp .env.example .env
docker compose -f compose.yml up --build -d
```

Published image deployment:

```bash
cd deploy/docker
cp .env.example .env
# set ZERTAN_IMAGE in .env, for example ghcr.io/<owner>/<repo>:1.2.0
docker compose -f compose.ghcr.yml pull
docker compose -f compose.ghcr.yml up -d
```

Container defaults:

- data volume: `zertan_data`
- in-container data root: `/data`
- health endpoint: `GET /healthz`

Recommended before public exposure:

- set a real `SECRET_KEY`
- set a real `ZERTAN_BOOTSTRAP_ADMIN_PASSWORD`
- set `ZERTAN_SEED_DEMO_CONTENT=0`
- terminate TLS in a reverse proxy and then enable `ZERTAN_COOKIE_SECURE=true`

## Desktop Bundles

Build a desktop bundle for the current operating system:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r deploy/desktop/requirements.txt
.venv/bin/python -m unittest discover -s tests
.venv/bin/python deploy/desktop/build_release.py --version 1.0.0
```

Artifacts are generated under `deploy/desktop/dist/`.

The desktop launcher:

- stores data in a per-user application directory
- generates and persists a secret key locally
- seeds demo content on first run
- starts the local Flask server and opens the browser

## CI/CD And Releases

The repository now ships with three workflows:

- [`ci.yml`](/Users/myke/Desktop/codes/Projects/Zertan/.github/workflows/ci.yml): tests on push and pull request, then verifies the Docker image builds
- [`release-image.yml`](/Users/myke/Desktop/codes/Projects/Zertan/.github/workflows/release-image.yml): publishes the Docker image to GHCR and creates a GitHub Release
- [`release-desktop.yml`](/Users/myke/Desktop/codes/Projects/Zertan/.github/workflows/release-desktop.yml): builds desktop bundles for Linux, macOS, and Windows and attaches them to a GitHub Release

Release options:

1. Push a tag such as `v1.2.0` to publish the Docker image release.
2. Push a tag such as `desktop-v1.2.0` to publish desktop bundles.
3. Use manual workflow dispatch when you want GitHub Actions to create the release tag and release from the selected commit.

The release workflows were updated to use Node 24 compatible action versions where applicable.

## Runtime Configuration

Most important environment variables:

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

## Troubleshooting

`First startup requires ZERTAN_BOOTSTRAP_ADMIN_PASSWORD`

- You started with `ZERTAN_SEED_DEMO_CONTENT=0` on an empty database.
- Set `ZERTAN_BOOTSTRAP_ADMIN_PASSWORD` or run in debug/demo mode for local development.

`Production startup requires SECRET_KEY`

- `SECRET_KEY` is missing or still uses the known insecure production placeholder.
- Set a long random value before non-debug deployment.

`Port 5050 is already in use`

- Change `PORT` for local runs or `HOST_PORT` in Docker.

`Database or uploads are not where I expect`

- Inspect `ZERTAN_DATA_DIR`, `ZERTAN_DB_PATH`, and `ZERTAN_MEDIA_ROOT`.
- In Docker, operational state is stored under `/data` inside the container.
