from urllib.parse import urlparse


def normalize_exam_group_ids(values):
    if values is None:
        values = []
    elif not isinstance(values, (list, tuple, set)):
        values = [values]

    normalized = []
    seen = set()
    for value in values:
        try:
            group_id = int(value)
        except (TypeError, ValueError):
            continue
        if group_id < 1 or group_id in seen:
            continue
        seen.add(group_id)
        normalized.append(group_id)
    return normalized


def validate_exam_scope_group_ids(db, values, *, allowed_group_ids=None, allow_global=True):
    normalized_group_ids = normalize_exam_group_ids(values)
    if not normalized_group_ids:
        if allow_global:
            return []
        raise ValueError("Select at least one group for this exam.")

    groups = _groups_repository(db)
    existing_group_ids = set(groups.list_existing_ids(normalized_group_ids))
    if len(existing_group_ids) != len(normalized_group_ids):
        raise ValueError("One or more selected groups do not exist.")

    if allowed_group_ids is not None:
        allowed = set(normalize_exam_group_ids(allowed_group_ids))
        if any(group_id not in allowed for group_id in normalized_group_ids):
            raise ValueError("One or more selected groups are outside your allowed scope.")

    return normalized_group_ids


def normalize_exam_payload(payload, *, group_ids=None):
    official_url = str(payload.get("official_url", "") or "").strip()
    if official_url:
        parsed = urlparse(official_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Official exam URL must be a valid http or https address.")

    normalized_group_ids = normalize_exam_group_ids(payload.get("group_ids", []) if group_ids is None else group_ids)

    return {
        "code": str(payload["code"]).strip(),
        "title": str(payload["title"]).strip(),
        "provider": str(payload["provider"]).strip(),
        "description": str(payload.get("description", "") or "").strip(),
        "official_url": official_url,
        "difficulty": str(payload.get("difficulty", "intermediate") or "intermediate").strip(),
        "status": str(payload.get("status", "draft") or "draft").strip(),
        "tags": [str(tag).strip() for tag in payload.get("tags", []) if str(tag).strip()],
        "group_ids": normalized_group_ids,
    }


def _groups_repository(db):
    groups = getattr(db, "groups", None)
    if groups is not None:
        return groups

    manager = getattr(db, "manager", None)
    groups = getattr(manager, "groups", None)
    if groups is not None:
        return groups

    from ..db_methods.t_groups import GroupsTable

    return GroupsTable(db)
