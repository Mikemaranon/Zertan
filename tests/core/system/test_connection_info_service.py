import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.data_m import DBManager
from app.web_server.services_m.connection_info_service import ConnectionInfoService


class _FakeHttpResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        import json

        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class ConnectionInfoServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="zertan-connection-info-")
        self.addCleanup(self.temp_dir.cleanup)
        self._set_env("ZERTAN_DATA_DIR", self.temp_dir.name)
        self._set_env("ZERTAN_DB_PATH", str(Path(self.temp_dir.name) / "runtime" / "test.db"))
        self._set_env("ZERTAN_MEDIA_ROOT", str(Path(self.temp_dir.name) / "assets"))
        self._set_env("ZERTAN_SEED_DEMO_CONTENT", "0")
        self._set_env("ZERTAN_BOOTSTRAP_ADMIN_PASSWORD", "runtime-admin-password")
        self.addCleanup(self._restore_env)

        self.runtime_config = {
            "app_root": ROOT / "app" / "web_server",
            "data_root": Path(self.temp_dir.name),
            "db_path": Path(self.temp_dir.name) / "runtime" / "test.db",
            "media_root": Path(self.temp_dir.name) / "assets",
            "secret_key": "test-secret",
            "instance_id": "instance-abc123",
            "host": "0.0.0.0",
            "port": 5050,
            "debug": False,
            "cookie_secure": False,
            "cookie_samesite": "Lax",
            "jwt_lifetime_hours": 8,
            "seed_demo_content": False,
            "bootstrap_admin_username": "admin",
            "bootstrap_admin_password": "runtime-admin-password",
            "bootstrap_admin_email": "admin@zertan.local",
        }
        self.db_manager = DBManager(runtime_config=self.runtime_config)
        self.service = ConnectionInfoService(self.db_manager, runtime_config=self.runtime_config)

    def test_create_alias_persists_verified_metadata(self):
        with patch.object(
            self.service,
            "_verify_endpoint",
            return_value={
                "status": "verified",
                "message": "Confirmed",
                "resolved_ips": ["100.64.0.10"],
            },
        ):
            alias = self.service.create_alias(host="zertan.tailnet.ts.net", label="Tailscale", port=5050)

        self.assertEqual(alias["label"], "Tailscale")
        self.assertEqual(alias["host"], "zertan.tailnet.ts.net")
        self.assertEqual(alias["host_type"], "dns")
        self.assertEqual(alias["verification_status"], "verified")
        self.assertEqual(alias["resolved_ips"], ["100.64.0.10"])

    def test_verify_endpoint_accepts_matching_instance_signature(self):
        with patch.object(self.service, "_resolve_ipv4_candidates", return_value=["192.168.1.131"]), patch(
            "urllib.request.urlopen",
            return_value=_FakeHttpResponse(
                {
                    "status": "ok",
                    "service": "zertan",
                    "instance_id": self.runtime_config["instance_id"],
                }
            ),
        ):
            result = self.service._verify_endpoint("192.168.1.131", 5050)

        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["resolved_ips"], ["192.168.1.131"])

    def test_verify_endpoint_detects_other_zertan_instance(self):
        with patch.object(self.service, "_resolve_ipv4_candidates", return_value=["192.168.1.131"]), patch(
            "urllib.request.urlopen",
            return_value=_FakeHttpResponse(
                {
                    "status": "ok",
                    "service": "zertan",
                    "instance_id": "other-instance",
                }
            ),
        ):
            result = self.service._verify_endpoint("192.168.1.131", 5050)

        self.assertEqual(result["status"], "mismatch")
        self.assertIn("different Zertan instance", result["message"])

    def test_get_connection_info_refreshes_aliases_and_reports_primary_endpoint(self):
        alias = self.db_manager.server_aliases.create("tailnet.example", label="Tailnet", port=6060)
        self.db_manager.server_aliases.update_verification(
            alias["id"],
            status="pending",
            message="Pending verification",
            resolved_ips=[],
        )

        with patch.object(self.service, "list_detected_ipv4_addresses", return_value=["10.0.0.8"]), patch.object(
            self.service,
            "_verify_endpoint",
            side_effect=[
                {
                    "status": "verified",
                    "message": "Confirmed primary",
                    "resolved_ips": ["10.0.0.8"],
                },
                {
                    "status": "verified",
                    "message": "Confirmed alias",
                    "resolved_ips": ["100.64.0.15"],
                },
            ],
        ):
            payload = self.service.get_connection_info(refresh_aliases=True)

        self.assertEqual(payload["connection"]["listen_scope"], "all_interfaces")
        self.assertEqual(payload["connection"]["primary_lan_ip"], "10.0.0.8")
        self.assertEqual(payload["primary_endpoint"]["verification_status"], "verified")
        self.assertEqual(payload["primary_endpoint"]["host"], "10.0.0.8")
        self.assertEqual(len(payload["aliases"]), 1)
        self.assertEqual(payload["aliases"][0]["verification_status"], "verified")
        self.assertEqual(payload["aliases"][0]["source"], "saved")

    def test_build_primary_endpoint_without_detected_lan_ip_returns_error_payload(self):
        endpoint = self.service._build_primary_endpoint("")

        self.assertEqual(endpoint["verification_status"], "error")
        self.assertEqual(endpoint["url"], "")
        self.assertEqual(endpoint["resolved_ips"], [])
        self.assertIn("No LAN-capable IPv4 address", endpoint["verification_message"])

    def test_list_detected_ipv4_addresses_filters_invalid_and_sorts_private_before_cgnat(self):
        with patch("socket.gethostname", return_value="zertan-host"), patch(
            "socket.getfqdn",
            return_value="zertan-host.local",
        ), patch.object(
            self.service,
            "_resolve_ipv4_candidates",
            side_effect=[
                ["127.0.0.1", "10.0.0.8", "100.64.0.15"],
                ["10.0.0.8", "invalid-value"],
            ],
        ), patch.object(
            self.service,
            "_detect_source_ip",
            side_effect=["100.64.0.15", "10.0.0.9", ""],
        ):
            addresses = self.service.list_detected_ipv4_addresses()

        self.assertEqual(addresses, ["10.0.0.8", "10.0.0.9", "100.64.0.15"])

    def test_select_primary_lan_ip_prefers_explicit_bind_address(self):
        scoped_service = ConnectionInfoService(
            self.db_manager,
            runtime_config={**self.runtime_config, "host": "192.168.1.50"},
        )

        selected = scoped_service._select_primary_lan_ip(["10.0.0.8", "10.0.0.9"])

        self.assertEqual(selected, "192.168.1.50")

    def test_verify_endpoint_marks_non_zertan_payload_and_unreachable_hosts(self):
        with patch.object(self.service, "_resolve_ipv4_candidates", return_value=["192.168.1.131"]), patch(
            "urllib.request.urlopen",
            return_value=_FakeHttpResponse(
                {
                    "status": "ok",
                    "service": "other-service",
                    "instance_id": self.runtime_config["instance_id"],
                }
            ),
        ):
            mismatch = self.service._verify_endpoint("192.168.1.131", 5050)

        self.assertEqual(mismatch["status"], "mismatch")
        self.assertIn("service signature does not match", mismatch["message"])

        with patch.object(self.service, "_resolve_ipv4_candidates", return_value=[]), patch(
            "urllib.request.urlopen",
            side_effect=OSError("connection refused"),
        ):
            unreachable = self.service._verify_endpoint("bad-host", 5050)

        self.assertEqual(unreachable["status"], "unreachable")
        self.assertIn("connection refused", unreachable["message"])

    def _set_env(self, key, value):
        marker = f"_orig_{key}"
        if not hasattr(self, marker):
            setattr(self, marker, os.environ.get(key))
        os.environ[key] = value

    def _restore_env(self):
        for key in (
            "ZERTAN_DATA_DIR",
            "ZERTAN_DB_PATH",
            "ZERTAN_MEDIA_ROOT",
            "ZERTAN_SEED_DEMO_CONTENT",
            "ZERTAN_BOOTSTRAP_ADMIN_PASSWORD",
        ):
            original = getattr(self, f"_orig_{key}", None)
            if original is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original


if __name__ == "__main__":
    unittest.main()
