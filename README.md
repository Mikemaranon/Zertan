# Zertan

Zertan is a certification exam preparation platform built on top of the original Flask server template in this repository.

The implementation preserves the template's core composition pattern:
- `web_server/main.py` remains the entrypoint
- `web_server/server.py` remains the composition root
- `web_server/app_routes.py` handles page routing
- `web_server/api_m` autoloads modular API domains
- `web_server/data_m` remains the database layer
- `web_server/user_m` remains the authentication and authorization layer

The product is now a structured study and formal exam workspace with:
- JWT-backed authentication
- hierarchical role enforcement
- study mode
- exam builder and formal exam mode
- paginated exam runner with 5 questions per page
- persistent result storage and KPI reporting
- editable question banks
- zip import and export of exam packages
- support for `single_select`, `multiple_choice`, `hot_spot`, and `drag_drop`

## Stack

- Python
- Flask
- SQLite
- PyJWT
- HTML
- CSS
- Vanilla JavaScript

No SPA framework or alternate backend stack was introduced.

## Project structure

### Backend

- `web_server/main.py`
  Creates the Flask app and starts the server.

- `web_server/server.py`
  Wires `DBManager`, `UserManager`, `AppRoutes`, and `ApiManager`.

- `web_server/app_routes.py`
  Registers the page routes for login, dashboard, catalog, study mode, builder, runner, results, management, profile, and admin.

- `web_server/api_m/domains/`
  Domain APIs:
  - `auth_api.py`
  - `user_api.py`
  - `exams_api.py`
  - `questions_api.py`
  - `attempts_api.py`
  - `statistics_api.py`
  - `admin_api.py`
  - `import_export_api.py`

- `web_server/data_m/`
  SQLite data layer with table/domain managers:
  - `t_users.py`
  - `t_sessions.py`
  - `t_exams.py`
  - `t_questions.py`
  - `t_attempts.py`
  - `t_statistics.py`

- `web_server/services_m/`
  Shared application logic for:
  - question normalization and validation
  - attempt assembly and scoring
  - exam package import and export

### Frontend

- `web_app/base.html`
  Shared shell for authenticated pages.

- `web_app/*.html`
  Server-rendered pages for:
  - login
  - dashboard
  - catalog
  - exam detail / study mode
  - exam builder
  - exam runner
  - results
  - profile
  - exam management
  - question editor
  - admin

- `web_app/static/JS/`
  Modular vanilla JS:
  - `core/`
  - `components/`
  - `pages/`

- `web_app/static/CSS/`
  Minimal serious UI using white, gray, and light blue.

## Schema highlights

The SQLite database lives at:

- `web_server/data_m/utils/zertan.db`

Core tables:

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

Notes:
- study mode does not write official attempt records
- exam mode creates fixed attempts on the server
- attempt question snapshots preserve exam integrity after edits
- statistics are computed from submitted attempts

## Seeded data

On first boot the app seeds:

- four users
- two exams
- sample questions covering all required question types

Seeded credentials:

- `admin` / `admin123`
- `examiner` / `examiner123`
- `reviewer` / `reviewer123`
- `candidate` / `candidate123`

## Main flows

### Study mode

- open an exam from the catalog
- land in study mode first
- filter questions by tag, topic, and type in the client
- answer and check each question individually
- edit questions from inside the study workspace if the role allows it

### Exam mode

- open the exam builder
- choose topics, tags, question types, count, and optional time limit
- let the server assemble a fixed attempt
- run the exam in pages of 5 questions
- navigate between pages without losing answers
- submit once to store official results and KPIs

### Import/export

- import a `.zip` package from exam management
- export an existing exam as a `.zip`
- package format uses:
  - `exam.json`
  - one JSON file per question
  - an `assets/` directory

## Run locally

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cd web_server
../.venv/bin/python main.py
```

The app will start on:

- `http://127.0.0.1:5000`

## Important endpoints

Auth:
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`

Exams:
- `GET /api/exams`
- `POST /api/exams`
- `GET /api/exams/<id>`
- `PUT /api/exams/<id>`
- `GET /api/exams/<id>/study`
- `GET /api/exams/<id>/builder-meta`
- `POST /api/exams/<id>/builder`

Questions:
- `GET /api/questions/<id>`
- `POST /api/exams/<id>/questions`
- `PUT /api/questions/<id>`
- `POST /api/questions/<id>/archive`
- `DELETE /api/questions/<id>`
- `POST /api/questions/<id>/check`

Attempts and results:
- `GET /api/attempts/<id>`
- `POST /api/attempts/<id>/answers`
- `POST /api/attempts/<id>/submit`
- `GET /api/attempts/<id>/result`

Statistics:
- `GET /api/statistics/overview`
- `GET /api/statistics/me`
- `GET /api/statistics/exams/<id>`
- `GET /api/statistics/platform`

Admin and package management:
- `GET /api/admin/users`
- `POST /api/admin/users`
- `PUT /api/admin/users/<id>`
- `DELETE /api/admin/users/<id>`
- `POST /api/import-export/exams/import`
- `GET /api/import-export/exams/<id>/export`

## Verification performed

The following smoke checks were run locally with Flask's test client:

- app boot
- login
- exam catalog fetch
- study mode fetch
- exam builder attempt creation
- attempt retrieval
- attempt submission
- statistics fetch
- question checking
- exam zip export
- multipart question creation

## Current limitations

- no automated browser test suite is included yet
- hot spot questions use numbered dropdowns associated with an image instead of coordinate-click regions
- drag and drop authoring is form-based while runtime interaction is true drag and drop
