QUESTION_TYPES = {"single_select", "multiple_choice", "hot_spot", "drag_drop"}
DRAG_DROP_MODES = {"R", "U"}


def normalize_string_list(values):
    if isinstance(values, str):
        values = [item.strip() for item in values.replace("\n", ",").split(",")]
    return [value.strip() for value in values if str(value).strip()]


def point_in_region(x, y, region):
    return (
        x >= region["x"]
        and x <= region["x"] + region["width"]
        and y >= region["y"]
        and y <= region["y"] + region["height"]
    )


def normalize_drag_drop_mode(raw_mode):
    mode = (raw_mode or "U").strip().upper()
    if mode not in DRAG_DROP_MODES:
        raise ValueError("Drag and drop mode must be R or U.")
    return mode


def normalize_drag_drop_entities(entries, prefix):
    normalized = []
    seen_ids = set()
    for index, entry in enumerate(entries, start=1):
        identifier = (entry.get("id") or f"{prefix}-{index}").strip()
        label = (entry.get("label") or "").strip()
        if not identifier or not label:
            continue
        if identifier in seen_ids:
            raise ValueError(f"Duplicate {prefix} ids are not allowed in drag and drop questions.")
        seen_ids.add(identifier)
        normalized.append({"id": identifier, "label": label})
    return normalized


def normalize_drag_drop_mappings(mappings, items, destinations):
    if not isinstance(mappings, dict):
        return {}

    item_ids = {item["id"] for item in items}
    destination_ids = {destination["id"] for destination in destinations}
    if not item_ids or not destination_ids:
        return {}

    normalized = {}
    for left, right in mappings.items():
        left_id = str(left).strip()
        right_id = str(right).strip()
        if not left_id or not right_id:
            continue
        if left_id in destination_ids and right_id in item_ids:
            normalized[left_id] = right_id
        elif left_id in item_ids and right_id in destination_ids:
            normalized[right_id] = left_id
    return normalized


def normalize_drag_drop_config(config):
    config = config or {}
    items = normalize_drag_drop_entities(config.get("items") or [], "item")
    destinations = normalize_drag_drop_entities(config.get("destinations") or [], "destination")
    return {
        "mode": normalize_drag_drop_mode(config.get("mode")),
        "items": items,
        "destinations": destinations,
        "mappings": normalize_drag_drop_mappings(config.get("mappings") or {}, items, destinations),
    }
