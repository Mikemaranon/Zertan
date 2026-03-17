# services_m/question_logic.py

import json


QUESTION_TYPES = {"single_select", "multiple_choice", "hot_spot", "drag_drop"}


def normalize_question_payload(raw_payload):
    payload = dict(raw_payload)
    payload["type"] = payload["type"].strip()
    if payload["type"] not in QUESTION_TYPES:
        raise ValueError("Unsupported question type.")

    payload["title"] = (payload.get("title") or "").strip()
    payload["statement"] = (payload.get("statement") or "").strip()
    payload["explanation"] = (payload.get("explanation") or "").strip()
    payload["difficulty"] = (payload.get("difficulty") or "intermediate").strip()
    payload["status"] = (payload.get("status") or "active").strip()
    payload["position"] = int(payload.get("position") or 0)
    payload["tags"] = _normalize_string_list(payload.get("tags", []))
    payload["topics"] = _normalize_string_list(payload.get("topics", []))
    payload["config"] = payload.get("config") or {}
    payload["options"] = payload.get("options") or []
    payload["assets"] = payload.get("assets") or []

    if not payload["statement"]:
        raise ValueError("Question statement is required.")

    if payload["type"] in {"single_select", "multiple_choice"}:
        options = []
        for option in payload["options"]:
            text = (option.get("text") or "").strip()
            key = (option.get("key") or "").strip()
            if not text or not key:
                continue
            options.append(
                {
                    "key": key,
                    "text": text,
                    "is_correct": bool(option.get("is_correct")),
                }
            )
        if len(options) < 2:
            raise ValueError("Choice questions require at least two options.")
        correct_count = sum(1 for option in options if option["is_correct"])
        if payload["type"] == "single_select" and correct_count != 1:
            raise ValueError("Single select questions require exactly one correct answer.")
        if payload["type"] == "multiple_choice" and correct_count < 1:
            raise ValueError("Multiple choice questions require at least one correct answer.")
        payload["options"] = options
        payload["config"] = {}

    if payload["type"] == "hot_spot":
        payload["options"] = []
        regions = payload["config"].get("regions") or []
        clean_regions = []
        for region in regions:
            clean_regions.append(
                {
                    "id": region.get("id") or f"region-{len(clean_regions) + 1}",
                    "x": float(region["x"]),
                    "y": float(region["y"]),
                    "width": float(region["width"]),
                    "height": float(region["height"]),
                }
            )
        if not clean_regions:
            raise ValueError("Hot spot questions require at least one valid region.")
        payload["config"] = {"regions": clean_regions}

    if payload["type"] == "drag_drop":
        payload["options"] = []
        items = payload["config"].get("items") or []
        destinations = payload["config"].get("destinations") or []
        mappings = payload["config"].get("mappings") or {}
        if not items or not destinations or not mappings:
            raise ValueError("Drag and drop questions require items, destinations, and mappings.")
        payload["config"] = {
            "items": [{"id": item["id"], "label": item["label"]} for item in items],
            "destinations": [{"id": destination["id"], "label": destination["label"]} for destination in destinations],
            "mappings": dict(mappings),
        }

    return payload


def build_public_question(question, include_solution=False):
    public_question = {
        "id": question["id"],
        "exam_id": question["exam_id"],
        "type": question["type"],
        "title": question.get("title") or "",
        "statement": question["statement"],
        "explanation": question.get("explanation") or "",
        "difficulty": question.get("difficulty") or "intermediate",
        "status": question.get("status") or "active",
        "position": question.get("position") or 0,
        "tags": question.get("tags", []),
        "topics": question.get("topics", []),
        "assets": question.get("assets", []),
        "options": [],
        "config": {},
    }

    if question["type"] in {"single_select", "multiple_choice"}:
        public_question["options"] = [
            {"key": option["key"], "text": option["text"], **({"is_correct": option["is_correct"]} if include_solution else {})}
            for option in question.get("options", [])
        ]
    elif question["type"] == "hot_spot":
        public_question["config"] = {}
        if include_solution:
            public_question["config"]["regions"] = question.get("config", {}).get("regions", [])
    elif question["type"] == "drag_drop":
        public_question["config"] = {
            "items": question.get("config", {}).get("items", []),
            "destinations": question.get("config", {}).get("destinations", []),
        }
        if include_solution:
            public_question["config"]["mappings"] = question.get("config", {}).get("mappings", {})

    return public_question


def evaluate_question_response(question, response):
    question_type = question["type"]
    response = response or {}
    omitted = _is_omitted(question_type, response)

    if omitted:
        return {
            "is_correct": False,
            "score": 0,
            "omitted": True,
            "normalized_response": response,
            "correct_answer": _correct_answer_summary(question),
        }

    if question_type == "single_select":
        selected = response.get("selected")
        correct = next((option["key"] for option in question["options"] if option.get("is_correct")), None)
        is_correct = selected == correct
    elif question_type == "multiple_choice":
        selected = sorted(set(response.get("selected", [])))
        correct = sorted(option["key"] for option in question["options"] if option.get("is_correct"))
        is_correct = selected == correct
    elif question_type == "hot_spot":
        x = float(response.get("x"))
        y = float(response.get("y"))
        is_correct = any(_point_in_region(x, y, region) for region in question.get("config", {}).get("regions", []))
    elif question_type == "drag_drop":
        submitted = response.get("mappings", {})
        correct = question.get("config", {}).get("mappings", {})
        is_correct = submitted == correct
    else:
        raise ValueError("Unsupported question type.")

    return {
        "is_correct": is_correct,
        "score": 1 if is_correct else 0,
        "omitted": False,
        "normalized_response": response,
        "correct_answer": _correct_answer_summary(question),
    }


def _normalize_string_list(values):
    if isinstance(values, str):
        values = [item.strip() for item in values.split(",")]
    return [value.strip() for value in values if str(value).strip()]


def _point_in_region(x, y, region):
    return (
        x >= region["x"]
        and x <= region["x"] + region["width"]
        and y >= region["y"]
        and y <= region["y"] + region["height"]
    )


def _is_omitted(question_type, response):
    if question_type == "single_select":
        return not response.get("selected")
    if question_type == "multiple_choice":
        return not response.get("selected")
    if question_type == "hot_spot":
        return response.get("x") is None or response.get("y") is None
    if question_type == "drag_drop":
        return not response.get("mappings")
    return True


def _correct_answer_summary(question):
    if question["type"] == "single_select":
        return next((option["key"] for option in question["options"] if option.get("is_correct")), None)
    if question["type"] == "multiple_choice":
        return sorted(option["key"] for option in question["options"] if option.get("is_correct"))
    if question["type"] == "hot_spot":
        return question.get("config", {}).get("regions", [])
    if question["type"] == "drag_drop":
        return question.get("config", {}).get("mappings", {})
    return None
