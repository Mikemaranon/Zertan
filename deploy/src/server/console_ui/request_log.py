import threading
import time
from collections import deque
from datetime import datetime

from .formatting import format_timestamp


class ApiRequestConsoleLog:
    NOISY_GET_PREFIXES = (
        "/api/auth/me",
        "/api/users/me",
        "/api/users/recent-attempts",
        "/api/exams",
        "/api/questions",
        "/api/attempts",
        "/api/statistics",
        "/api/live-exams",
        "/api/system/connection-info",
        "/api/admin/users",
        "/api/admin/user-groups",
        "/api/admin/features",
        "/api/log-registry",
    )

    def __init__(self, *, max_entries=300):
        self._entries = deque(maxlen=max_entries)
        self._lock = threading.Lock()
        self._next_id = 1

    def install(self, app, user_manager):
        from flask import g, request

        if app.config.get("ZERTAN_SERVER_CONSOLE_LOGGER_INSTALLED"):
            return
        app.config["ZERTAN_SERVER_CONSOLE_LOGGER_INSTALLED"] = True

        @app.before_request
        def _mark_console_request_start():
            if request.path.startswith("/api/"):
                g.server_console_request_started_at = time.perf_counter()

        @app.after_request
        def _capture_console_request(response):
            path = request.path or ""
            if not path.startswith("/api/"):
                return response

            duration_ms = int(
                (time.perf_counter() - getattr(g, "server_console_request_started_at", time.perf_counter())) * 1000
            )
            if not self.should_capture(method=request.method, path=path, status_code=response.status_code):
                return response

            user = user_manager.check_user(request)
            entry = {
                "id": self._next_entry_id(),
                "timestamp": format_timestamp(datetime.now()),
                "method": request.method,
                "path": path,
                "query_string": request.query_string.decode("utf-8", errors="replace") if request.query_string else "",
                "status_code": int(response.status_code),
                "status_family": self.status_family(response.status_code),
                "duration_ms": duration_ms,
                "user_label": (user or {}).get("display_name") or (user or {}).get("login_name") or "Anonymous",
                "user_role": (user or {}).get("role") or "",
                "remote_addr": (request.headers.get("X-Forwarded-For") or request.remote_addr or "").strip(),
                "endpoint": request.endpoint or "",
                "request_body_preview": self._request_body_preview(request),
            }
            with self._lock:
                self._entries.appendleft(entry)
            return response

    def list_entries(self):
        with self._lock:
            return list(self._entries)

    def _next_entry_id(self):
        with self._lock:
            value = self._next_id
            self._next_id += 1
            return value

    def should_capture(self, *, method, path, status_code):
        normalized_method = str(method or "").upper()
        normalized_path = str(path or "").strip()
        if normalized_method == "OPTIONS" or normalized_path in {"/api/check"}:
            return False
        if normalized_method != "GET":
            return True
        if status_code >= 400 or normalized_path.endswith("/export"):
            return True
        return not any(
            normalized_path == prefix or normalized_path.startswith(f"{prefix}/")
            for prefix in self.NOISY_GET_PREFIXES
        )

    def status_family(self, status_code):
        code = int(status_code or 0)
        if 200 <= code < 300:
            return "success"
        if 300 <= code < 400:
            return "redirect"
        if 400 <= code < 500:
            return "client_error"
        if code >= 500:
            return "server_error"
        return "unknown"

    def _request_body_preview(self, request):
        method = str(request.method or "").upper()
        if method == "GET":
            return ""
        if (request.mimetype or "").startswith("multipart/"):
            return "[multipart form payload omitted]"
        raw = request.get_data(cache=True, as_text=True) or ""
        normalized = raw.strip()
        if not normalized:
            return ""
        if len(normalized) > 2000:
            return f"{normalized[:2000]}..."
        return normalized
