# Zertan Lite

`Zertan Lite` is a separate single-user app target that lives under `lite/` and reuses the existing Zertan backend modules through explicit imports.

Current scope of this first Lite foundation:

- separate Flask app factory under `lite/web_server`
- separate Lite data directory under `lite/data`
- no login page as the user-facing entry point
- automatic local user provisioning for a single-user workspace
- desktop launcher opens the embedded client window directly
- embedded backend stays packaged with the frontend while browser access remains optional
- Lite navigation includes exam management for creating, importing, exporting, and editing exam banks
- Lite does not expose user administration, group administration, global stats, live exams, connection info, or log registry surfaces
- exam management is simplified for the local workspace, without group-scope controls
- downstream study, builder, runner, and question-management pages reuse the existing templates and APIs

Important repository boundary:

- Lite-specific runtime and launch code stays under `lite/` and `deploy/src/lite/`
- shared templates and frontend assets under `app/` may receive small compatibility adjustments when Lite needs to reuse them cleanly

## Run Lite

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r app/requirements.txt
.venv/bin/python lite/web_server/main.py
```

Build a native Lite package for the current platform:

```bash
.venv/bin/python deploy/builds/build.py --version 1.0.0 --target lite
```

Lite defaults:

- host: `0.0.0.0`
- port: `5051`
- data root: `lite/data`
- local user login: `lite`
- local user display name: `Local User`
- local user role: `administrator`

Optional environment variables:

- `ZERTAN_LITE_HOST`
- `ZERTAN_LITE_PORT`
- `ZERTAN_LITE_DEBUG`
- `ZERTAN_LITE_DATA_DIR`
- `ZERTAN_LITE_DB_PATH`
- `ZERTAN_LITE_MEDIA_ROOT`
- `ZERTAN_LITE_SECRET_KEY`
- `ZERTAN_LITE_SEED_DEMO_CONTENT`
- `ZERTAN_LITE_USER_LOGIN`
- `ZERTAN_LITE_USER_NAME`
- `ZERTAN_LITE_USER_ROLE`

## Current design choice

This implementation keeps the main Zertan services, templates, and APIs as the shared foundation, while wrapping them with Lite-specific runtime configuration, auth behavior, routes, and desktop-launch behavior.

That gives us an incremental starting point for Lite without mixing Lite logic into the main app.
