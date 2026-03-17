# AGENTS.md

## Project identity

Build a serious, minimal, and maintainable certification exam preparation platform on top of the existing Flask server template.

VERY IMPORTANT: YOU CAN NOT MANIPULATE BASE ARCHITECTURE OF BACKEND, FOLLOW THE PROPOSED MODULE-BASED STRUCTURE.

This is not a generic quiz app.
This is a structured study and exam platform for professional certification preparation.

The system must support:
- authenticated users
- role-based permissions
- study mode
- exam mode
- editable question banks
- exam package import/export
- persistent statistics and KPI collection
- multiple question types

The project must prioritize:
- clarity
- maintainability
- modularity
- serious UX, for desktop, laptop, tablet and phone (responsive with good layouts)
- low distraction
- strong backend structure
- simple frontend architecture

---

## Strict stack constraints

### Backend
Use only:
- Python
- Flask
- SQLite
- JWT
- standard Python libraries and lightweight dependencies compatible with this stack

### Frontend
Use only:
- Vanilla JavaScript
- HTML
- CSS

### Forbidden
Do NOT introduce:
- React
- Vue
- Angular
- Svelte
- Next.js
- Nuxt
- TypeScript
- Tailwind
- SPA rewrites
- heavy frontend build tooling
- unnecessary framework migrations
- a different backend stack
- a different database engine unless explicitly requested later

The project must remain:
- Flask backend
- SQLite core
- JWT auth
- plain HTML/CSS/JS frontend

Do not change the nature of the stack. module based architecture with the provided files must stay intact, content of the files can be updated but its nature cant be changed.

---

## Design goals

The UI must feel:
- serious
- professional
- minimal
- clean
- distraction-free

### Visual style
Use:
- light blue as primary accent
- gray for secondary text, borders, and soft surfaces
- white as the main background/base

### UX principles
- clean typography
- generous spacing
- very limited visual noise
- clear hierarchy
- subtle states
- no unnecessary animations
- no gamification style
- no flashy effects

The application should feel like a professional study workspace.

### Responsive priority
- desktop-first
- responsive for smaller screens
- but optimized primarily for desktop workflows

---

## Core product model

The platform must support two distinct operational modes inside each exam or question bank:

### 1. Study mode
This is the default entry mode when opening an exam.

Purpose:
- fast review
- dynamic practice
- content exploration
- maintenance of question content by authorized roles

Rules:
- questions are listed for study and review
- official performance statistics are NOT stored from study mode
- it does NOT count as an official exam attempt
- each question has its own correction/check button
- the user can verify answers immediately
- filters are available in the client UI

Study mode filters must include:
- tags
- topics
- question type

Study mode should be fast and flexible.

### 2. Exam mode
This is the formal evaluation flow.

Rules:
- no per-question correction during the attempt
- no live feedback after each question
- no filter changes during the attempt
- results and statistics ARE stored
- the exam is assembled before starting
- the selected questions remain fixed for that attempt

Exam mode is stricter and intended to simulate a real certification session.

---

## Supported question types

The system must support these question types:

### single_select
- one correct answer
- radio-button style interaction

### multiple_choice
- multiple correct answers
- checkbox-style interaction
- validation must compare the full selected set

### hot_spot
- the user selects a region on an image
- valid answer areas must be defined by coordinates or regions
- backend and frontend must support asset storage and answer validation

### drag_drop
- draggable items
- destination zones
- validation based on correct mapping of origin items to targets

Question editing forms must adapt dynamically to the selected question type.

---

## Exam navigation rules

Exam mode must NOT show extremely long pages.

### Mandatory pagination rule
Questions must be shown in groups of 5 per page.

### Requirements
- maximum 5 questions per page
- visible pagination controls
- controls must appear at both the top and bottom of the exam page
- include:
  - previous
  - page numbers
  - next
  - total page count

The pagination behavior should resemble classic search engine result pagination.

### Navigation rules
- users can move back and forth between pages
- answers must persist while navigating
- page state must be preserved correctly
- the current page must be clearly indicated
- total page count must be visible

---

## Exam builder flow

Exam mode must be created from a dedicated builder/configuration step.

### Expected flow
1. user opens an exam
2. system lands in study mode first
3. user clicks to start an exam
4. exam builder form appears
5. user selects conditions
6. server assembles the exam from those conditions
7. server creates a fixed attempt
8. user completes the exam in paginated mode
9. results and statistics are stored

### Exam builder filters
The exam builder must support at least:
- topics
- tags
- one or more question types
- number of questions

Optional advanced filters may include:
- difficulty
- random order
- time limit

### Important rule
The server is responsible for assembling the final exam.
The client only sends the criteria.

Once an attempt is created, its question set becomes fixed.

---

## Question bank and exam management

The platform must support multiple certification collections or question groups, for example:
- AI-102
- AZ-900
- DP-100

These can represent:
- certification exams
- structured banks
- thematic collections

### Create or import
The system must provide a clear "Create or Import" entry point.

From there, authorized users must be able to:

#### Create a clean exam
Using a form with metadata such as:
- title
- code
- provider
- description
- difficulty
- tags
- status

#### Import an exam package
Upload a structured `.zip` package containing a full exam/question bank.

#### Export an exam package
Download an existing exam as a structured `.zip` package.

---

## Import/export rules

The system must support structured exam package import/export.

### Package contents
A package should include:
- exam metadata
- one JSON file per question
- related assets

### Critical editorial rule
Do NOT group many questions into one giant JSON file.

At most:
- one JSON file per question

This is mandatory for maintainability.

### Recommended package structure
Use a structure similar to:

```text
exam-package/
  exam.json
  questions/
    q_0001.json
    q_0002.json
    q_0003.json
  assets/
    images/
    hotspot/
    dragdrop/
```

### Recommended persistence model
Use a hybrid model:
- SQLite as the operational source of truth for the running app
- one JSON file per question as portable editable/importable source format

The app may import JSON question packages into SQLite and export them back out.

---

## Study mode editing capabilities

Inside study mode, authorized users must be able to maintain content.

### Allowed capabilities for authorized roles
- create new questions
- edit existing questions
- disable/archive questions
- delete questions if role permits
- update tags
- update topics
- update explanations
- update difficulty
- update assets
- change answer structure
- correct mistakes in content

### Editing UX
Question editing must happen through forms.
The forms must adapt to the question type.

#### single_select form
- statement
- options
- single correct answer
- explanation
- tags/topics
- difficulty

#### multiple_choice form
- statement
- options
- multiple correct answers
- explanation
- tags/topics
- difficulty

#### hot_spot form
- statement
- image upload/association
- valid region definitions
- explanation
- tags/topics
- difficulty

#### drag_drop form
- statement
- source items
- destination zones
- valid mappings
- explanation
- tags/topics
- difficulty

---

## Roles and permissions

Use a hierarchical role system from highest control to lowest control:

1. administrator
2. examiner
3. reviewer
4. user

Each higher role inherits the permissions of the lower roles.

### administrator
Full control over the system:
- manage users
- assign roles
- create/edit/delete exams
- import/export exams
- create/edit/delete questions
- access global statistics
- full administrative control

### examiner
Can:
- create exams/question banks
- supervise exams
- import exams
- export exams
- manage exam-level structures
- do everything reviewer and user can do

### reviewer
Can:
- create questions
- edit questions
- maintain question content
- update existing questions
- do everything user can do

### user
Can:
- use study mode
- build and run exams
- view results
- view personal statistics
- use the application normally

Cannot:
- modify database content
- create exams
- import/export content
- edit questions
- manage users

---

## Core screens

The application should include at least these pages/views:

1. Login
2. Dashboard / Home
3. Exam catalog
4. Exam detail / entry page
5. Study mode page
6. Exam builder page
7. Exam runner page
8. Results page
9. User statistics/profile page
10. Exam management page
11. Question editor page
12. Admin panel

---

## Data model expectations

At minimum, design a solid structure for these entities:

### users
- id
- username
- email if used
- password_hash
- role
- created_at
- last_login_at
- status

### exams
- id
- code
- title
- provider
- description
- difficulty
- status
- created_at
- updated_at

### questions
- id
- exam_id
- type
- title if needed
- statement
- explanation
- difficulty
- status
- created_at
- updated_at
- source_json_path if needed

### question options
For single_select and multiple_choice answers.

### question assets
For images and supporting resources.

### tags
### topics
### relation tables
For many-to-many linking where needed.

### exam_attempts
A fixed assembled attempt for a user.

### exam_attempt_questions
The frozen set/order of questions inside a specific attempt.

### exam_answers
The user responses for each question in an attempt.

### user statistics
Persistent KPI-friendly stats.

### global statistics
Optional aggregated metrics if useful.

Keep the schema normalized enough to remain maintainable.

---

## Statistics and KPIs

### Study mode
Study mode must NOT generate official exam KPIs.

### Exam mode
Exam mode must store evaluative statistics.

### User KPIs
At minimum track:
- exams completed
- questions answered
- total correct
- total incorrect
- total omitted
- global success rate
- success rate by exam
- success rate by question type
- success rate by tag/topic
- average completion time if timing is implemented

### Platform/global KPIs
Consider supporting:
- most failed questions
- hardest exams
- hardest topics
- hardest tags
- question type difficulty trends
- completion rates

---

## Architectural expectations

Build on top of the existing Flask server template.
Respect its modular philosophy where reasonable.

Recommended API domains:
- auth
- users
- exams
- questions
- attempts
- statistics
- admin
- import_export

Keep responsibilities clearly separated:
- content management
- exam execution
- statistics
- authentication/authorization

Avoid giant files.
Prefer modular code.
Keep naming consistent.
Use English for code, comments, identifiers, and technical docs.

---

## Authorization rules

Implement backend role checks explicitly.
Use decorators, middleware, or equivalent clean mechanisms.

Never rely only on frontend hiding of UI.
All sensitive operations must be enforced server-side.

---

## Frontend rules

Use only:
- HTML
- CSS
- vanilla JavaScript

Do not convert the application into a SPA framework architecture.
Do not replace the site with React/Vue/etc.
Do not introduce unnecessary build tooling.

Frontend should:
- remain understandable
- use modular JS where possible
- preserve a simple structure
- connect cleanly to Flask endpoints

---

## Backend rules

Use:
- Flask
- SQLite
- JWT
- simple maintainable services/repositories/managers as appropriate

Do not overengineer.
Do not introduce a complex distributed architecture.
Do not introduce technologies unrelated to the required stack.

Keep the backend practical, explicit, and maintainable.

---

## Final working expectations

A successful implementation should result in:
- a runnable Flask application
- working login/auth flow
- role-based UI and backend authorization
- study mode with filters and per-question correction
- exam builder flow
- exam mode with server-built attempts
- paginated exam runner with 5-question pages
- results and statistics persistence
- exam import/export
- question creation/editing forms
- maintainable database structure
- clean, minimal, serious UI

---

## Working behavior for the coding agent

When working on this repository:

1. Audit first.
2. Summarize what exists and what is missing.
3. Implement in functional phases.
4. Preserve the stack and design direction.
5. Prefer incremental rescue over unnecessary rewrites.
6. Keep code modular.
7. Update all dependent layers when changing data contracts.
8. Do not leave placeholder TODOs if the feature can be implemented.
9. Run available checks after major changes.
10. Provide a clear summary of what was changed and how to run the project.

This document is the contract for the project direction.
