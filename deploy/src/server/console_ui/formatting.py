from datetime import datetime


def format_uptime(seconds):
    total_seconds = max(0, int(seconds))
    total_minutes = total_seconds // 60
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours:02d}h {minutes:02d}m"


def parse_timestamp(value):
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def format_timestamp(value):
    if not value:
        return "Not available"
    return value.strftime("%d %b %Y %H:%M:%S")
