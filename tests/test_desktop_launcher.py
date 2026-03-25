import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy.desktop import desktop_launcher


class DesktopLauncherTests(unittest.TestCase):
    def test_frozen_resource_root_prefers_meipass_when_available(self):
        root = desktop_launcher.frozen_resource_root(meipass="/tmp/zertan-meipass")
        self.assertEqual(root, Path("/tmp/zertan-meipass").resolve())

    def test_frozen_resource_root_uses_internal_directory_for_linux_bundle(self):
        with tempfile.TemporaryDirectory(prefix="zertan-linux-bundle-") as temp_dir:
            bundle_root = Path(temp_dir) / "dist" / "Zertan"
            executable = bundle_root / "Zertan"
            internal_app = bundle_root / "_internal" / "app"
            internal_app.mkdir(parents=True, exist_ok=True)
            executable.write_text("binary", encoding="utf-8")

            root = desktop_launcher.frozen_resource_root(
                executable_path=executable,
                platform_name="linux",
            )

        self.assertEqual(root, (bundle_root / "_internal").resolve())

    def test_frozen_resource_root_uses_macos_resources_directory(self):
        with tempfile.TemporaryDirectory(prefix="zertan-macos-bundle-") as temp_dir:
            app_root = Path(temp_dir) / "Zertan.app"
            executable = app_root / "Contents" / "MacOS" / "Zertan"
            resources_app = app_root / "Contents" / "Resources" / "app"
            executable.parent.mkdir(parents=True, exist_ok=True)
            resources_app.mkdir(parents=True, exist_ok=True)
            executable.write_text("binary", encoding="utf-8")

            root = desktop_launcher.frozen_resource_root(
                executable_path=executable,
                platform_name="darwin",
            )

        self.assertEqual(root, (app_root / "Contents" / "Resources").resolve())

    def test_default_data_dir_uses_platform_specific_base_paths(self):
        windows_dir = desktop_launcher.default_data_dir(
            platform_name="win32",
            env={"APPDATA": r"C:\Users\Test\AppData\Roaming"},
            home=Path("/unused"),
        )
        mac_dir = desktop_launcher.default_data_dir(
            platform_name="darwin",
            env={},
            home=Path("/Users/tester"),
        )
        linux_dir = desktop_launcher.default_data_dir(
            platform_name="linux",
            env={"XDG_DATA_HOME": "/tmp/data-home"},
            home=Path("/home/tester"),
        )

        self.assertTrue(str(windows_dir).endswith("Zertan Server"))
        self.assertEqual(mac_dir, Path("/Users/tester/Library/Application Support/Zertan Server"))
        self.assertEqual(linux_dir, Path("/tmp/data-home/Zertan Server"))

    def test_apply_desktop_environment_sets_local_defaults(self):
        with tempfile.TemporaryDirectory(prefix="zertan-desktop-env-") as temp_dir:
            snapshot = os.environ.copy()
            try:
                for key in (
                    "ZERTAN_DATA_DIR",
                    "HOST",
                    "PORT",
                    "ZERTAN_SEED_DEMO_CONTENT",
                    "ZERTAN_BOOTSTRAP_ADMIN_USERNAME",
                    "ZERTAN_BOOTSTRAP_ADMIN_PASSWORD",
                    "ZERTAN_BOOTSTRAP_ADMIN_EMAIL",
                    "SECRET_KEY",
                ):
                    os.environ.pop(key, None)

                data_dir = desktop_launcher.apply_desktop_environment(
                    data_dir=temp_dir,
                    host="127.0.0.1",
                    port=5050,
                )

                self.assertEqual(data_dir, Path(temp_dir).resolve())
                self.assertEqual(os.environ["ZERTAN_DATA_DIR"], str(Path(temp_dir).resolve()))
                self.assertEqual(os.environ["HOST"], "127.0.0.1")
                self.assertEqual(os.environ["PORT"], "5050")
                self.assertEqual(os.environ["ZERTAN_SEED_DEMO_CONTENT"], "1")
                self.assertEqual(os.environ["ZERTAN_BOOTSTRAP_ADMIN_USERNAME"], "admin")
                self.assertEqual(os.environ["ZERTAN_BOOTSTRAP_ADMIN_PASSWORD"], "admin123")
                self.assertTrue((Path(temp_dir) / "config" / "secret_key.txt").exists())
            finally:
                os.environ.clear()
                os.environ.update(snapshot)

    def test_choose_port_returns_requested_port_when_available(self):
        port = desktop_launcher.choose_port("127.0.0.1", 5050)
        self.assertGreater(port, 0)

    def test_resolve_bundle_root_uses_frozen_resource_root_when_frozen(self):
        with patch.object(desktop_launcher.sys, "frozen", True, create=True), patch.object(
            desktop_launcher.sys,
            "_MEIPASS",
            "/tmp/zertan-packed",
            create=True,
        ):
            root = desktop_launcher.resolve_bundle_root()

        self.assertEqual(root, Path("/tmp/zertan-packed").resolve())

    def test_fallback_display_host_prefers_loopback_for_wildcard_bind(self):
        self.assertEqual(desktop_launcher.fallback_display_host("0.0.0.0"), "127.0.0.1")
        self.assertEqual(desktop_launcher.fallback_display_host("::"), "127.0.0.1")
        self.assertEqual(desktop_launcher.fallback_display_host("192.168.1.50"), "192.168.1.50")

    def test_detect_primary_lan_host_uses_connection_service(self):
        fake_service = SimpleNamespace(
            list_detected_ipv4_addresses=lambda: ["192.168.1.24", "10.0.0.15"],
            _select_primary_lan_ip=lambda addresses: addresses[0],
        )
        with patch("deploy.desktop.server_launcher.build_connection_info_service", return_value=fake_service):
            host = desktop_launcher.detect_primary_lan_host(
                db_manager=object(),
                runtime_config={"host": "0.0.0.0", "port": 5050},
                bind_host="0.0.0.0",
            )

        self.assertEqual(host, "192.168.1.24")

    def test_detect_primary_lan_host_falls_back_when_no_lan_ip_exists(self):
        fake_service = SimpleNamespace(
            list_detected_ipv4_addresses=lambda: [],
            _select_primary_lan_ip=lambda addresses: "",
        )
        with patch("deploy.desktop.server_launcher.build_connection_info_service", return_value=fake_service):
            host = desktop_launcher.detect_primary_lan_host(
                db_manager=object(),
                runtime_config={"host": "0.0.0.0", "port": 5050},
                bind_host="0.0.0.0",
            )

        self.assertEqual(host, "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
