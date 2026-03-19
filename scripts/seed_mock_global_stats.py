from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

from werkzeug.security import generate_password_hash


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_SERVER_ROOT = PROJECT_ROOT / "app" / "web_server"

if str(WEB_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_SERVER_ROOT))

from data_m.db_manager import DBManager  # noqa: E402
from services_m.attempt_service import AttemptService  # noqa: E402


MOCK_PASSWORD = "zertan-mock-2026"

GROUPS = [
    {
        "code": "grp-cloud-core",
        "name": "Cloud Core Cohort",
        "description": "Mock cloud fundamentals group for chart validation.",
        "members": ["alice.reed", "bruno.silva", "gabriel.cho"],
    },
    {
        "code": "grp-security-lab",
        "name": "Security Lab",
        "description": "Mock security-focused group for chart validation.",
        "members": ["carla.mendez", "diego.rossi", "helen.ives"],
    },
    {
        "code": "grp-data-track",
        "name": "Data Track",
        "description": "Mock data and analytics group for chart validation.",
        "members": ["elena.kovacs", "farah.noor", "alice.reed", "diego.rossi"],
    },
]

USERS = [
    {"login_name": "alice.reed", "display_name": "Alice Reed", "role": "user"},
    {"login_name": "bruno.silva", "display_name": "Bruno Silva", "role": "user"},
    {"login_name": "carla.mendez", "display_name": "Carla Mendez", "role": "reviewer"},
    {"login_name": "diego.rossi", "display_name": "Diego Rossi", "role": "user"},
    {"login_name": "elena.kovacs", "display_name": "Elena Kovacs", "role": "examiner"},
    {"login_name": "farah.noor", "display_name": "Farah Noor", "role": "user"},
    {"login_name": "gabriel.cho", "display_name": "Gabriel Cho", "role": "user"},
    {"login_name": "helen.ives", "display_name": "Helen Ives", "role": "user"},
]

ATTEMPT_TEMPLATES = {
    "perfect": ["correct", "correct", "correct", "correct", "correct", "correct", "correct"],
    "strong": ["correct", "correct", "correct", "correct", "incorrect", "correct", "correct"],
    "solid": ["correct", "correct", "correct", "incorrect", "correct", "omitted", "correct"],
    "mixed": ["correct", "incorrect", "incorrect", "correct", "omitted", "correct", "incorrect"],
    "careful": ["correct", "correct", "omitted", "correct", "correct", "omitted", "correct"],
    "rough": ["incorrect", "incorrect", "correct", "omitted", "incorrect", "correct", "omitted"],
    "struggling": ["omitted", "incorrect", "incorrect", "omitted", "correct", "incorrect", "omitted"],
    "recovery": ["correct", "correct", "incorrect", "correct", "correct", "correct", "incorrect"],
}

ATTEMPTS = [
    {"login_name": "alice.reed", "submitted_at": "2026-03-18T09:35:00", "duration_seconds": 780, "template": "perfect"},
    {"login_name": "alice.reed", "submitted_at": "2026-03-11T10:20:00", "duration_seconds": 860, "template": "strong"},
    {"login_name": "alice.reed", "submitted_at": "2026-02-25T15:40:00", "duration_seconds": 740, "template": "recovery"},
    {"login_name": "bruno.silva", "submitted_at": "2026-03-17T13:05:00", "duration_seconds": 1280, "template": "mixed"},
    {"login_name": "bruno.silva", "submitted_at": "2026-03-04T11:50:00", "duration_seconds": 1190, "template": "solid"},
    {"login_name": "carla.mendez", "submitted_at": "2026-03-14T16:25:00", "duration_seconds": 980, "template": "strong"},
    {"login_name": "carla.mendez", "submitted_at": "2026-02-21T09:15:00", "duration_seconds": 1040, "template": "perfect"},
    {"login_name": "carla.mendez", "submitted_at": "2026-02-07T12:10:00", "duration_seconds": 1110, "template": "solid"},
    {"login_name": "diego.rossi", "submitted_at": "2026-03-12T18:10:00", "duration_seconds": 1670, "template": "rough"},
    {"login_name": "diego.rossi", "submitted_at": "2026-02-14T17:30:00", "duration_seconds": 1540, "template": "struggling"},
    {"login_name": "elena.kovacs", "submitted_at": "2026-03-09T08:55:00", "duration_seconds": 1420, "template": "strong"},
    {"login_name": "elena.kovacs", "submitted_at": "2026-02-27T10:45:00", "duration_seconds": 1360, "template": "perfect"},
    {"login_name": "elena.kovacs", "submitted_at": "2026-02-06T14:05:00", "duration_seconds": 1490, "template": "careful"},
    {"login_name": "farah.noor", "submitted_at": "2026-03-08T15:15:00", "duration_seconds": 1730, "template": "careful"},
    {"login_name": "farah.noor", "submitted_at": "2026-02-19T16:50:00", "duration_seconds": 1810, "template": "struggling"},
    {"login_name": "gabriel.cho", "submitted_at": "2026-03-06T09:40:00", "duration_seconds": 940, "template": "recovery"},
    {"login_name": "gabriel.cho", "submitted_at": "2026-02-12T10:10:00", "duration_seconds": 1220, "template": "mixed"},
    {"login_name": "helen.ives", "submitted_at": "2026-03-03T14:35:00", "duration_seconds": 1320, "template": "solid"},
    {"login_name": "helen.ives", "submitted_at": "2026-02-18T11:25:00", "duration_seconds": 1450, "template": "rough"},
    {"login_name": "helen.ives", "submitted_at": "2026-02-04T13:55:00", "duration_seconds": 1180, "template": "mixed"},
]


def main():
    db_manager = DBManager()
    database = db_manager.db
    attempt_service = AttemptService(db_manager)

    ensure_group_tables(database)
    exam_id = get_exam_id(database, "ZT-100")
    upsert_groups(database)
    user_ids = upsert_users(db_manager)
    sync_group_memberships(database, user_ids)
    clear_existing_mock_attempts(database, user_ids.values())
    create_mock_attempts(database, attempt_service, exam_id, user_ids)
    print_summary(database, user_ids)


def ensure_group_tables(database):
    database.execute_script(
        """
        CREATE TABLE IF NOT EXISTS user_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_group_memberships (
            group_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (group_id, user_id),
            FOREIGN KEY (group_id) REFERENCES user_groups(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_user_group_memberships_user_id
        ON user_group_memberships(user_id);
        """
    )


def get_exam_id(database, exam_code):
    _, row = database.execute(
        "SELECT id FROM exams WHERE code = ?",
        (exam_code,),
        fetchone=True,
    )
    if not row:
        raise RuntimeError(f"Exam {exam_code} was not found.")
    return row["id"]


def upsert_groups(database):
    for group in GROUPS:
        database.execute(
            """
            INSERT OR IGNORE INTO user_groups (code, name, description, status)
            VALUES (?, ?, ?, 'active')
            """,
            (group["code"], group["name"], group["description"]),
        )
        database.execute(
            """
            UPDATE user_groups
            SET name = ?, description = ?, status = 'active', updated_at = CURRENT_TIMESTAMP
            WHERE code = ?
            """,
            (group["name"], group["description"], group["code"]),
        )


def upsert_users(db_manager):
    user_ids = {}
    password_hash = generate_password_hash(MOCK_PASSWORD)
    for user in USERS:
        existing = db_manager.users.get_by_login_name(user["login_name"])
        if existing:
            db_manager.users.update(
                existing["id"],
                user["display_name"],
                user["login_name"],
                user["role"],
                "active",
            )
            db_manager.users.update_password(existing["id"], password_hash)
            user_ids[user["login_name"]] = existing["id"]
            continue

        db_manager.users.create(
            login_name=user["login_name"],
            display_name=user["display_name"],
            password_hash=password_hash,
            role=user["role"],
            status="active",
        )
        created = db_manager.users.get_by_login_name(user["login_name"])
        user_ids[user["login_name"]] = created["id"]
    return user_ids


def sync_group_memberships(database, user_ids):
    group_ids = {}
    for group in GROUPS:
        _, row = database.execute(
            "SELECT id FROM user_groups WHERE code = ?",
            (group["code"],),
            fetchone=True,
        )
        group_ids[group["code"]] = row["id"]

    if group_ids:
        placeholders = ",".join("?" for _ in group_ids)
        database.execute(
            f"DELETE FROM user_group_memberships WHERE group_id IN ({placeholders})",
            tuple(group_ids.values()),
        )

    membership_rows = []
    for group in GROUPS:
        group_id = group_ids[group["code"]]
        for login_name in group["members"]:
            membership_rows.append((group_id, user_ids[login_name]))

    database.executemany(
        """
        INSERT OR IGNORE INTO user_group_memberships (group_id, user_id)
        VALUES (?, ?)
        """,
        membership_rows,
    )


def clear_existing_mock_attempts(database, user_ids):
    user_ids = list(user_ids)
    if not user_ids:
        return
    placeholders = ",".join("?" for _ in user_ids)
    database.execute(
        f"DELETE FROM exam_attempts WHERE user_id IN ({placeholders})",
        tuple(user_ids),
    )


def create_mock_attempts(database, attempt_service, exam_id, user_ids):
    criteria = {
        "question_count": 7,
        "random_order": False,
        "question_types": {"include": [], "exclude": []},
        "tags": {"include": [], "exclude": []},
        "topics": {"include": [], "exclude": []},
    }

    for attempt_spec in ATTEMPTS:
        user_id = user_ids[attempt_spec["login_name"]]
        attempt_id = attempt_service.create_attempt(exam_id, user_id, criteria)
        stored_questions = attempt_service.db.attempts.get_attempt_questions(attempt_id)
        answers = build_answers(stored_questions, ATTEMPT_TEMPLATES[attempt_spec["template"]])
        attempt_service.save_answers(attempt_id, answers)
        attempt_service.submit_attempt(attempt_id)
        override_attempt_timing(database, attempt_id, attempt_spec["submitted_at"], attempt_spec["duration_seconds"])


def build_answers(questions, outcome_template):
    answers = []
    for question_entry, outcome in zip(questions, outcome_template, strict=True):
        response = build_response(question_entry["snapshot"], outcome)
        answers.append(
            {
                "attempt_question_id": question_entry["attempt_question_id"],
                "response": response,
            }
        )
    return answers


def build_response(question, outcome):
    if outcome == "omitted":
        return None
    if outcome == "correct":
        return build_correct_response(question)
    if outcome == "incorrect":
        return build_incorrect_response(question)
    raise ValueError(f"Unsupported outcome: {outcome}")


def build_correct_response(question):
    question_type = question["type"]
    if question_type == "single_select":
        correct_key = next(option["key"] for option in question["options"] if option.get("is_correct"))
        return {"selected": correct_key}
    if question_type == "multiple_choice":
        correct_keys = [option["key"] for option in question["options"] if option.get("is_correct")]
        return {"selected": correct_keys}
    if question_type == "hot_spot":
        dropdowns = question.get("config", {}).get("dropdowns") or []
        if dropdowns:
            return {"selections": {dropdown["id"]: dropdown["correct_option"] for dropdown in dropdowns}}
        regions = question.get("config", {}).get("regions") or []
        region = regions[0]
        return {"x": region["x"] + 1, "y": region["y"] + 1}
    if question_type == "drag_drop":
        return {"mappings": dict(question.get("config", {}).get("mappings") or {})}
    raise ValueError(f"Unsupported question type: {question_type}")


def build_incorrect_response(question):
    question_type = question["type"]
    if question_type == "single_select":
        correct_key = next(option["key"] for option in question["options"] if option.get("is_correct"))
        wrong_key = next(option["key"] for option in question["options"] if option["key"] != correct_key)
        return {"selected": wrong_key}
    if question_type == "multiple_choice":
        correct_keys = [option["key"] for option in question["options"] if option.get("is_correct")]
        all_keys = [option["key"] for option in question["options"]]
        wrong_keys = [key for key in all_keys if key not in correct_keys]
        if wrong_keys:
            return {"selected": [correct_keys[0], wrong_keys[0]]}
        return {"selected": correct_keys[:-1]}
    if question_type == "hot_spot":
        dropdowns = question.get("config", {}).get("dropdowns") or []
        if dropdowns:
            selections = {}
            for index, dropdown in enumerate(dropdowns):
                if index == 0:
                    wrong_option = next(option for option in dropdown["options"] if option != dropdown["correct_option"])
                    selections[dropdown["id"]] = wrong_option
                else:
                    selections[dropdown["id"]] = dropdown["correct_option"]
            return {"selections": selections}
        return {"x": -1, "y": -1}
    if question_type == "drag_drop":
        config = question.get("config", {}) or {}
        destinations = config.get("destinations") or []
        items = config.get("items") or []
        mappings = dict(config.get("mappings") or {})
        item_ids = [item["id"] for item in items]
        wrong_mappings = {}
        for index, destination in enumerate(destinations):
            correct_item = mappings.get(destination["id"])
            alternatives = [item_id for item_id in item_ids if item_id != correct_item]
            if alternatives:
                wrong_mappings[destination["id"]] = alternatives[index % len(alternatives)]
            else:
                wrong_mappings[destination["id"]] = correct_item
        if wrong_mappings == mappings and destinations:
            first_destination = destinations[0]["id"]
            alternatives = [item_id for item_id in item_ids if item_id != mappings.get(first_destination)]
            if alternatives:
                wrong_mappings[first_destination] = alternatives[0]
        return {"mappings": wrong_mappings}
    raise ValueError(f"Unsupported question type: {question_type}")


def override_attempt_timing(database, attempt_id, submitted_at_raw, duration_seconds):
    submitted_at = datetime.fromisoformat(submitted_at_raw)
    started_at = submitted_at - timedelta(seconds=duration_seconds)
    started_at_sql = started_at.strftime("%Y-%m-%d %H:%M:%S")
    submitted_at_sql = submitted_at.strftime("%Y-%m-%d %H:%M:%S")

    database.execute(
        """
        UPDATE exam_attempts
        SET started_at = ?, submitted_at = ?, duration_seconds = ?
        WHERE id = ?
        """,
        (started_at_sql, submitted_at_sql, duration_seconds, attempt_id),
    )
    database.execute(
        """
        UPDATE exam_answers
        SET answered_at = ?
        WHERE attempt_id = ?
        """,
        (submitted_at_sql, attempt_id),
    )


def print_summary(database, user_ids):
    placeholders = ",".join("?" for _ in user_ids)

    _, groups_row = database.execute("SELECT COUNT(*) AS total FROM user_groups", fetchone=True)
    _, memberships_row = database.execute("SELECT COUNT(*) AS total FROM user_group_memberships", fetchone=True)
    _, attempts_row = database.execute(
        f"SELECT COUNT(*) AS total FROM exam_attempts WHERE user_id IN ({placeholders})",
        tuple(user_ids.values()),
        fetchone=True,
    )
    _, score_rows = database.execute(
        f"""
        SELECT
            u.login_name,
            COUNT(a.id) AS attempts,
            ROUND(AVG(a.score_percent), 2) AS avg_score,
            ROUND(AVG(a.duration_seconds), 0) AS avg_duration
        FROM users u
        LEFT JOIN exam_attempts a
            ON a.user_id = u.id
            AND a.status = 'submitted'
        WHERE u.id IN ({placeholders})
        GROUP BY u.id
        ORDER BY lower(u.login_name)
        """,
        tuple(user_ids.values()),
        fetchall=True,
    )

    print("Mock global stats seed completed.")
    print(f"Groups: {groups_row['total']}")
    print(f"Memberships: {memberships_row['total']}")
    print(f"Mock submitted attempts: {attempts_row['total']}")
    print(f"Mock user password: {MOCK_PASSWORD}")
    for row in score_rows:
        print(
            f"- {row['login_name']}: attempts={row['attempts']}, "
            f"avg_score={row['avg_score']}, avg_duration={row['avg_duration']}"
        )


if __name__ == "__main__":
    main()
