import ipaddress
import json
import socket
import urllib.error
import urllib.request

from support_m import get_runtime_config


class ConnectionInfoService:
    def __init__(self, db_manager, *, runtime_config=None):
        self.db = db_manager
        self.runtime_config = dict(runtime_config or get_runtime_config())
        self.bind_host = str(self.runtime_config["host"]).strip() or "0.0.0.0"
        self.port = int(self.runtime_config["port"])
        self.instance_id = self.runtime_config["instance_id"]

    def get_connection_info(self, *, refresh_aliases=False):
        detected_ipv4s = self.list_detected_ipv4_addresses()
        primary_lan_ip = self._select_primary_lan_ip(detected_ipv4s)
        aliases = self.db.server_aliases.list_all()
        if refresh_aliases:
            aliases = [self.refresh_alias(alias["id"]) for alias in aliases]

        return {
            "connection": {
                "listen_host": self.bind_host,
                "listen_port": self.port,
                "listen_scope": self._listen_scope(),
                "share_hint": self._share_hint(primary_lan_ip),
                "primary_lan_ip": primary_lan_ip,
                "detected_ipv4_addresses": detected_ipv4s,
            },
            "primary_endpoint": self._build_primary_endpoint(primary_lan_ip),
            "aliases": [self._serialize_alias(alias) for alias in aliases if alias],
        }

    def create_alias(self, *, host, label="", port=None):
        alias = self.db.server_aliases.create(host, label=label, port=port)
        return self.refresh_alias(alias["id"])

    def delete_alias(self, alias_id):
        self.db.server_aliases.delete(alias_id)

    def refresh_alias(self, alias_id):
        alias = self.db.server_aliases.get(alias_id)
        if not alias:
            return None
        verification = self._verify_endpoint(alias["host"], alias["port"] or self.port)
        return self.db.server_aliases.update_verification(
            alias_id,
            status=verification["status"],
            message=verification["message"],
            resolved_ips=verification["resolved_ips"],
        )

    def list_detected_ipv4_addresses(self):
        addresses = set()

        bind_candidate = self.bind_host.lower()
        if bind_candidate not in {"", "0.0.0.0", "::", "localhost"}:
            addresses.update(self._resolve_ipv4_candidates(self.bind_host))

        for host_name in {socket.gethostname(), socket.getfqdn()}:
            if not host_name:
                continue
            addresses.update(self._resolve_ipv4_candidates(host_name))

        for remote_host in ("8.8.8.8", "1.1.1.1", "192.0.2.1"):
            detected = self._detect_source_ip(remote_host)
            if detected:
                addresses.add(detected)

        normalized = []
        seen = set()
        for address in addresses:
            try:
                parsed = ipaddress.ip_address(address)
            except ValueError:
                continue
            if parsed.version != 4 or parsed.is_loopback or parsed.is_unspecified:
                continue
            rendered = str(parsed)
            if rendered in seen:
                continue
            seen.add(rendered)
            normalized.append(rendered)

        return sorted(normalized, key=self._address_sort_key)

    def _build_primary_endpoint(self, primary_lan_ip):
        if not primary_lan_ip:
            return {
                "label": "Primary LAN address",
                "host": "",
                "port": self.port,
                "url": "",
                "verification_status": "error",
                "verification_message": "No LAN-capable IPv4 address could be detected on this server.",
                "resolved_ips": [],
                "source": "detected",
            }

        verification = self._verify_endpoint(primary_lan_ip, self.port)
        return {
            "label": "Primary LAN address",
            "host": primary_lan_ip,
            "port": self.port,
            "url": self._build_url(primary_lan_ip, self.port),
            "verification_status": verification["status"],
            "verification_message": verification["message"],
            "resolved_ips": verification["resolved_ips"],
            "source": "detected",
        }

    def _serialize_alias(self, alias):
        effective_port = alias["port"] or self.port
        return {
            **alias,
            "effective_port": effective_port,
            "url": self._build_url(alias["host"], effective_port),
            "source": "saved",
        }

    def _verify_endpoint(self, host, port):
        resolved_ips = self._resolve_ipv4_candidates(host)
        url = self._build_url(host, port)
        try:
            request = urllib.request.Request(url=f"{url}/api/check", headers={"Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=2) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            return {
                "status": "unreachable",
                "message": f"Endpoint did not answer Zertan on {host}:{port}: {self._clean_error(exc)}",
                "resolved_ips": resolved_ips,
            }

        if payload.get("status") != "ok" or payload.get("service") != "zertan":
            return {
                "status": "mismatch",
                "message": f"{host}:{port} responded, but the service signature does not match Zertan.",
                "resolved_ips": resolved_ips,
            }

        if payload.get("instance_id") != self.instance_id:
            return {
                "status": "mismatch",
                "message": f"{host}:{port} resolves and answers, but it points to a different Zertan instance.",
                "resolved_ips": resolved_ips,
            }

        resolved_suffix = ""
        if resolved_ips:
            resolved_suffix = f" Resolved IPv4: {', '.join(resolved_ips)}."
        return {
            "status": "verified",
            "message": f"Confirmed this host answers as the current Zertan instance on port {port}.{resolved_suffix}",
            "resolved_ips": resolved_ips,
        }

    def _build_url(self, host, port):
        return f"http://{host}:{port}"

    def _listen_scope(self):
        host = self.bind_host.lower()
        if host in {"127.0.0.1", "localhost", "::1"}:
            return "loopback"
        if host in {"0.0.0.0", "::"}:
            return "all_interfaces"
        return "single_interface"

    def _share_hint(self, primary_lan_ip):
        scope = self._listen_scope()
        if scope == "loopback":
            return "This instance is bound to loopback only. Other devices will not reach it until the bind host changes."
        if primary_lan_ip:
            return "This instance is listening beyond loopback and can be shared if the network path and firewall allow the configured port."
        return "No LAN address was detected. The service may still be reachable through a custom interface or VPN alias."

    def _select_primary_lan_ip(self, addresses):
        host = self.bind_host.lower()
        if host not in {"", "0.0.0.0", "::", "127.0.0.1", "::1", "localhost"}:
            try:
                parsed = ipaddress.ip_address(host)
            except ValueError:
                parsed = None
            if parsed is not None and parsed.version == 4 and not parsed.is_loopback and not parsed.is_unspecified:
                return str(parsed)
        return addresses[0] if addresses else ""

    def _resolve_ipv4_candidates(self, host):
        try:
            infos = socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_STREAM)
        except socket.gaierror:
            return []
        resolved = sorted({info[4][0] for info in infos if info and info[4] and info[4][0]})
        return [value for value in resolved if value not in {"0.0.0.0", "127.0.0.1"}]

    def _detect_source_ip(self, remote_host):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect((remote_host, 80))
                return sock.getsockname()[0]
        except OSError:
            return ""

    def _address_sort_key(self, value):
        ip = ipaddress.ip_address(value)
        if ip.is_private:
            return (0, tuple(int(part) for part in value.split(".")))
        if ip in ipaddress.ip_network("100.64.0.0/10"):
            return (1, tuple(int(part) for part in value.split(".")))
        if ip.is_global:
            return (2, tuple(int(part) for part in value.split(".")))
        return (3, tuple(int(part) for part in value.split(".")))

    def _clean_error(self, error):
        message = str(error).strip()
        return message or error.__class__.__name__
