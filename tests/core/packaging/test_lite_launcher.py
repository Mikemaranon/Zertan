import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy.src.lite import lite_launcher


class LiteLauncherTests(unittest.TestCase):
    def test_apply_desktop_environment_sets_management_defaults(self):
        with tempfile.TemporaryDirectory(prefix="zertan-lite-env-") as temp_dir:
            snapshot = os.environ.copy()
            try:
                for key in (
                    "ZERTAN_LITE_DATA_DIR",
                    "HOST",
                    "PORT",
                    "ZERTAN_LITE_SEED_DEMO_CONTENT",
                    "ZERTAN_LITE_USER_LOGIN",
                    "ZERTAN_LITE_USER_NAME",
                    "ZERTAN_LITE_USER_ROLE",
                    "SECRET_KEY",
                ):
                    os.environ.pop(key, None)

                data_dir = lite_launcher.apply_desktop_environment(
                    data_dir=temp_dir,
                    host="127.0.0.1",
                    port=5051,
                )

                self.assertEqual(data_dir, Path(temp_dir).resolve())
                self.assertEqual(os.environ["ZERTAN_LITE_DATA_DIR"], str(Path(temp_dir).resolve()))
                self.assertEqual(os.environ["HOST"], "127.0.0.1")
                self.assertEqual(os.environ["PORT"], "5051")
                self.assertEqual(os.environ["ZERTAN_LITE_USER_LOGIN"], "lite")
                self.assertEqual(os.environ["ZERTAN_LITE_USER_NAME"], "Local User")
                self.assertEqual(os.environ["ZERTAN_LITE_USER_ROLE"], "administrator")
                self.assertEqual(os.environ["ZERTAN_LITE_SEED_DEMO_CONTENT"], "1")
                self.assertTrue((Path(temp_dir) / "config" / "secret_key.txt").exists())
            finally:
                os.environ.clear()
                os.environ.update(snapshot)

    def test_show_client_window_opens_embedded_home_page(self):
        created = {}
        closed_callbacks = []

        class EventList:
            def __iadd__(self, callback):
                closed_callbacks.append(callback)
                return self

        fake_window = SimpleNamespace(events=SimpleNamespace(closed=EventList()))
        
        def fake_create_window(*args, **kwargs):
            created["window"] = (args, kwargs)
            return fake_window

        fake_webview = SimpleNamespace(
            create_window=fake_create_window,
            start=lambda: created.setdefault("started", True),
        )

        with patch.dict(sys.modules, {"webview": fake_webview}):
            lite_launcher.show_client_window(port=5051, server_thread="thread")

        args, kwargs = created["window"]
        self.assertEqual(args[0], lite_launcher.APP_NAME)
        self.assertEqual(kwargs["url"], "http://127.0.0.1:5051/home")
        self.assertEqual(kwargs["width"], 1480)
        self.assertEqual(kwargs["height"], 960)
        self.assertTrue(created["started"])
        self.assertEqual(len(closed_callbacks), 1)


if __name__ == "__main__":
    unittest.main()
