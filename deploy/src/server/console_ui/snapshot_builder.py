import time
from datetime import datetime
from pathlib import Path

from .formatting import format_timestamp, format_uptime, parse_timestamp


class ConsoleSnapshotBuilder:
    def __init__(
        self,
        *,
        backend,
        api_request_log,
        runtime_config,
        display_host,
        port,
        base_url,
        data_dir,
        server_thread,
    ):
        from app.web_server.services_m.connection_info_service import ConnectionInfoService

        self.backend = backend
        self.db = backend.DBManager
        self.api_request_log = api_request_log
        self.runtime_config = dict(runtime_config)
        self.display_host = display_host
        self.port = int(port)
        self.base_url = str(base_url)
        self.data_dir = Path(data_dir).resolve()
        self.server_thread = server_thread
        self.connection_info = ConnectionInfoService(self.db, runtime_config=self.runtime_config)

    def build(self, *, started_at, stopping=False):
        users = self._build_users()
        groups = self.db.groups.all()
        features = self.db.site_features.list_all()
        exams = self.db.exams.list_all(is_administrator=True)
        connection = self.connection_info.get_connection_info(refresh_aliases=True)
        activity = self._build_activity()

        active_sessions = self._count_active_sessions()
        question_count = self._count_questions()
        enabled_features = sum(1 for feature in features if feature.get("enabled"))
        loopback_url = f"http://127.0.0.1:{self.port}"
        primary_endpoint = connection.get("primary_endpoint") or {}
        primary_url = primary_endpoint.get("url") or loopback_url
        if stopping:
            health_label = "Stopping"
        elif self.server_thread.is_alive():
            health_label = "Healthy"
        else:
            health_label = "Stopped"

        return {
            "server": {
                "app_name": "Zertan Server",
                "health_label": health_label,
                "display_host": self.display_host,
                "port": self.port,
                "base_url": self.base_url,
                "loopback_url": loopback_url,
                "primary_url": primary_url,
                "primary_label": primary_endpoint.get("label", "Primary endpoint"),
                "primary_status": primary_endpoint.get("verification_status", ""),
                "primary_message": primary_endpoint.get("verification_message", ""),
                "listen_host": connection.get("connection", {}).get("listen_host", ""),
                "listen_scope": connection.get("connection", {}).get("listen_scope", ""),
                "share_hint": connection.get("connection", {}).get("share_hint", ""),
                "detected_ipv4_addresses": connection.get("connection", {}).get("detected_ipv4_addresses", []),
                "instance_id": self.runtime_config.get("instance_id", ""),
                "data_dir": str(self.data_dir),
                "db_path": str(Path(self.runtime_config.get("db_path", "")).resolve()),
                "media_root": str(Path(self.runtime_config.get("media_root", "")).resolve()),
                "service_mode": "Desktop embedded server",
                "refresh_label": format_timestamp(datetime.now()),
                "started_at_label": format_timestamp(datetime.fromtimestamp(started_at)),
                "uptime_label": format_uptime(time.time() - started_at),
                "aliases": connection.get("aliases", []),
            },
            "stats": {
                "users": len(users),
                "groups": len(groups),
                "exams": len(exams),
                "questions": question_count,
                "active_sessions": active_sessions,
                "enabled_features": enabled_features,
                "api_entries": len(activity),
            },
            "users": users,
            "groups": groups,
            "features": features,
            "activity": activity,
        }

    def _build_users(self):
        users = []
        for user in self.db.users.all():
            groups = self.db.groups.list_for_user(user["id"])
            users.append(
                {
                    **user,
                    "group_names": [group["name"] for group in groups],
                    "groups": [
                        {
                            "id": group["id"],
                            "code": group["code"],
                            "name": group["name"],
                        }
                        for group in groups
                    ],
                    "created_at_label": format_timestamp(parse_timestamp(user.get("created_at"))),
                    "last_login_label": format_timestamp(parse_timestamp(user.get("last_login_at"))),
                }
            )
        return users

    def _build_activity(self):
        return self.api_request_log.list_entries()[:80]

    def _count_active_sessions(self):
        row = self.db.execute(
            """
            SELECT COUNT(*) AS total
            FROM sessions
            WHERE datetime(expires_at) > datetime('now')
            """,
            fetchone=True,
        )
        return int(row["total"] or 0) if row else 0

    def _count_questions(self):
        row = self.db.execute(
            """
            SELECT COUNT(*) AS total
            FROM questions
            WHERE status != 'archived'
            """,
            fetchone=True,
        )
        return int(row["total"] or 0) if row else 0
