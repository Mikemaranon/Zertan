import ipaddress
import json
import re


HOST_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class ServerAliasesTable:
    def __init__(self, db):
        self.db = db

    def list_all(self):
        _, rows = self.db.execute(
            """
            SELECT
                id,
                label,
                host,
                host_type,
                port,
                verification_status,
                verification_message,
                resolved_ips_json,
                last_verified_at,
                created_at,
                updated_at
            FROM server_aliases
            ORDER BY lower(COALESCE(label, '')), lower(host), id
            """,
            fetchall=True,
        )
        return [self._row_to_alias(row) for row in rows]

    def get(self, alias_id):
        _, row = self.db.execute(
            """
            SELECT
                id,
                label,
                host,
                host_type,
                port,
                verification_status,
                verification_message,
                resolved_ips_json,
                last_verified_at,
                created_at,
                updated_at
            FROM server_aliases
            WHERE id = ?
            """,
            (alias_id,),
            fetchone=True,
        )
        return self._row_to_alias(row)

    def create(self, host, *, label="", port=None):
        normalized_host, host_type = self._normalize_host(host)
        normalized_label = self._normalize_label(label)
        normalized_port = self._normalize_port(port)

        alias_id = self.db.execute_insert(
            """
            INSERT INTO server_aliases (
                label,
                host,
                host_type,
                port,
                verification_status,
                verification_message,
                resolved_ips_json
            )
            VALUES (?, ?, ?, ?, 'pending', '', '[]')
            """,
            (normalized_label, normalized_host, host_type, normalized_port),
        )
        return self.get(alias_id)

    def delete(self, alias_id):
        self.db.execute("DELETE FROM server_aliases WHERE id = ?", (alias_id,))

    def update_verification(self, alias_id, *, status, message="", resolved_ips=None):
        payload = json.dumps(sorted(set(resolved_ips or [])))
        self.db.execute(
            """
            UPDATE server_aliases
            SET
                verification_status = ?,
                verification_message = ?,
                resolved_ips_json = ?,
                last_verified_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, message.strip(), payload, alias_id),
        )
        return self.get(alias_id)

    def _normalize_host(self, host):
        value = str(host or "").strip().lower()
        if not value:
            raise ValueError("Host is required.")
        if "://" in value or "/" in value or ":" in value:
            try:
                parsed_ip = ipaddress.ip_address(value)
                if parsed_ip.version != 4:
                    raise ValueError("Only IPv4 addresses are supported for manual aliases.")
                return str(parsed_ip), "ip"
            except ValueError:
                raise ValueError("Host must be a bare IPv4 address or DNS name without protocol or path.")

        try:
            parsed_ip = ipaddress.ip_address(value)
        except ValueError:
            parsed_ip = None

        if parsed_ip is not None:
            if parsed_ip.version != 4:
                raise ValueError("Only IPv4 addresses are supported for manual aliases.")
            return str(parsed_ip), "ip"

        labels = value.split(".")
        if any(not label for label in labels):
            raise ValueError("DNS names must not contain empty labels.")
        if any(not HOST_LABEL_RE.match(label) for label in labels):
            raise ValueError("DNS names may only contain letters, numbers, and hyphens.")
        if len(value) > 253:
            raise ValueError("DNS names must be 253 characters or fewer.")
        return value, "dns"

    def _normalize_label(self, label):
        value = str(label or "").strip()
        return value[:120]

    def _normalize_port(self, port):
        if port in (None, ""):
            return None
        try:
            normalized = int(port)
        except (TypeError, ValueError):
            raise ValueError("Port must be a valid integer.")
        if normalized < 1 or normalized > 65535:
            raise ValueError("Port must be between 1 and 65535.")
        return normalized

    def _row_to_alias(self, row):
        if not row:
            return None
        try:
            resolved_ips = json.loads(row["resolved_ips_json"] or "[]")
        except json.JSONDecodeError:
            resolved_ips = []
        return {
            "id": row["id"],
            "label": row["label"] or "",
            "host": row["host"],
            "host_type": row["host_type"],
            "port": row["port"],
            "verification_status": row["verification_status"] or "pending",
            "verification_message": row["verification_message"] or "",
            "resolved_ips": [str(value) for value in resolved_ips if str(value).strip()],
            "last_verified_at": row["last_verified_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
