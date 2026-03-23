from .common import (
    QUESTION_TYPES,
    normalize_drag_drop_config,
    normalize_drag_drop_entities,
    normalize_drag_drop_mappings,
    normalize_drag_drop_mode,
    normalize_string_list,
)


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
    payload["tags"] = normalize_string_list(payload.get("tags", []))
    payload["topics"] = normalize_string_list(payload.get("topics", []))
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
        dropdowns = payload["config"].get("dropdowns") or []
        clean_dropdowns = []
        used_orders = set()
        for index, dropdown in enumerate(dropdowns, start=1):
            order = int(dropdown.get("order") or index)
            if order < 1:
                raise ValueError("Hot spot dropdown order must be greater than zero.")
            if order in used_orders:
                raise ValueError("Hot spot dropdown order values must be unique.")
            used_orders.add(order)

            options = normalize_string_list(dropdown.get("options", []))
            if len(options) < 2:
                raise ValueError("Each hot spot dropdown requires at least two options.")

            correct_option = (dropdown.get("correct_option") or "").strip()
            if correct_option not in options:
                raise ValueError("Each hot spot dropdown must define a correct option from its option list.")

            clean_dropdowns.append(
                {
                    "id": (dropdown.get("id") or f"dropdown-{order}").strip(),
                    "order": order,
                    "label": (dropdown.get("label") or f"Dropdown {order}").strip(),
                    "options": options,
                    "correct_option": correct_option,
                }
            )
        if not clean_dropdowns:
            raise ValueError("Hot spot questions require at least one dropdown definition.")
        if not payload["assets"]:
            raise ValueError("Hot spot questions require an image asset.")
        payload["config"] = {"dropdowns": sorted(clean_dropdowns, key=lambda item: item["order"])}

    if payload["type"] == "drag_drop":
        payload["options"] = []
        items = normalize_drag_drop_entities(payload["config"].get("items") or [], "item")
        destinations = normalize_drag_drop_entities(payload["config"].get("destinations") or [], "destination")
        mappings_raw = payload["config"].get("mappings") or {}
        mode = normalize_drag_drop_mode(payload["config"].get("mode"))
        mappings = normalize_drag_drop_mappings(mappings_raw, items, destinations)
        if not items or not destinations or not mappings:
            raise ValueError("Drag and drop questions require items, destinations, and mappings.")
        missing_destinations = [destination["id"] for destination in destinations if destination["id"] not in mappings]
        if missing_destinations:
            raise ValueError("Drag and drop questions require a mapped item for every destination.")
        if mode == "U" and len(set(mappings.values())) != len(mappings.values()):
            raise ValueError("Unique drag and drop questions cannot reuse the same item across multiple destinations.")
        payload["config"] = normalize_drag_drop_config(
            {
                "mode": mode,
                "items": items,
                "destinations": destinations,
                "mappings": mappings,
            }
        )

    return payload
