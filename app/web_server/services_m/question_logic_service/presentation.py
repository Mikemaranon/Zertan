from .common import normalize_drag_drop_config


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
        public_question["config"] = build_public_hotspot_config(question, include_solution)
    elif question["type"] == "drag_drop":
        config = normalize_drag_drop_config(question.get("config", {}))
        public_question["config"] = {
            "mode": config["mode"],
            "items": config["items"],
            "destinations": config["destinations"],
        }
        if include_solution:
            public_question["config"]["mappings"] = config["mappings"]

    return public_question


def build_public_hotspot_config(question, include_solution):
    config = question.get("config", {})
    dropdowns = config.get("dropdowns") or []
    if dropdowns:
        public_dropdowns = []
        for dropdown in dropdowns:
            item = {
                "id": dropdown["id"],
                "order": dropdown["order"],
                "label": dropdown.get("label") or f"Dropdown {dropdown['order']}",
                "options": dropdown.get("options", []),
            }
            if include_solution:
                item["correct_option"] = dropdown["correct_option"]
            public_dropdowns.append(item)
        return {"dropdowns": public_dropdowns}
    if include_solution:
        return {"regions": config.get("regions", [])}
    return {}
