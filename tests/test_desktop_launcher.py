import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy.desktop import desktop_launcher


class DesktopLauncherTests(unittest.TestCase):
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

        self.assertTrue(str(windows_dir).endswith("Zertan"))
        self.assertEqual(mac_dir, Path("/Users/tester/Library/Application Support/Zertan"))
        self.assertEqual(linux_dir, Path("/tmp/data-home/Zertan"))

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


if __name__ == "__main__":
    unittest.main()
