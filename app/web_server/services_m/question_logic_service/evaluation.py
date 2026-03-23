from .common import normalize_drag_drop_config, point_in_region


def evaluate_question_response(question, response):
    question_type = question["type"]
    response = response or {}
    omitted = is_omitted(question_type, response)

    if omitted:
        return {
            "is_correct": False,
            "score": 0,
            "omitted": True,
            "normalized_response": response,
            "correct_answer": correct_answer_summary(question),
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
        dropdowns = question.get("config", {}).get("dropdowns") or []
        if dropdowns:
            submitted = response.get("selections", {})
            is_correct = all(submitted.get(dropdown["id"]) == dropdown["correct_option"] for dropdown in dropdowns)
        else:
            x = float(response.get("x"))
            y = float(response.get("y"))
            is_correct = any(point_in_region(x, y, region) for region in question.get("config", {}).get("regions", []))
    elif question_type == "drag_drop":
        config = normalize_drag_drop_config(question.get("config", {}))
        submitted = normalize_drag_drop_config(
            {
                "mode": config["mode"],
                "items": config["items"],
                "destinations": config["destinations"],
                "mappings": response.get("mappings", {}),
            }
        )["mappings"]
        correct = config["mappings"]
        is_correct = submitted == correct
    else:
        raise ValueError("Unsupported question type.")

    return {
        "is_correct": is_correct,
        "score": 1 if is_correct else 0,
        "omitted": False,
        "normalized_response": response,
        "correct_answer": correct_answer_summary(question),
    }


def is_omitted(question_type, response):
    if question_type == "single_select":
        return not response.get("selected")
    if question_type == "multiple_choice":
        return not response.get("selected")
    if question_type == "hot_spot":
        selections = response.get("selections")
        if selections is not None:
            return not any(str(value).strip() for value in selections.values())
        return response.get("x") is None or response.get("y") is None
    if question_type == "drag_drop":
        return not response.get("mappings")
    return True


def correct_answer_summary(question):
    if question["type"] == "single_select":
        return next((option["key"] for option in question["options"] if option.get("is_correct")), None)
    if question["type"] == "multiple_choice":
        return sorted(option["key"] for option in question["options"] if option.get("is_correct"))
    if question["type"] == "hot_spot":
        dropdowns = question.get("config", {}).get("dropdowns") or []
        if dropdowns:
            return [
                {
                    "id": dropdown["id"],
                    "order": dropdown["order"],
                    "label": dropdown.get("label") or f"Dropdown {dropdown['order']}",
                    "correct_option": dropdown["correct_option"],
                }
                for dropdown in dropdowns
            ]
        return question.get("config", {}).get("regions", [])
    if question["type"] == "drag_drop":
        return normalize_drag_drop_config(question.get("config", {}))["mappings"]
    return None
