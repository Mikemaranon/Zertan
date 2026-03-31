import importlib.util
import sys
import unittest
from pathlib import Path

from flask import Flask, jsonify


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "deploy" / "src" / "server" / "server_console_ui.py"
SERVER_ROOT = ROOT / "deploy" / "src" / "server"
APP_ROOT = ROOT / "app"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from console_ui.formatting import format_uptime


def load_server_console_ui():
    spec = importlib.util.spec_from_file_location("server_console_ui", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DummyUserManager:
    def check_user(self, request):
        if request.headers.get("X-User") == "admin":
            return {
                "display_name": "Admin User",
                "login_name": "admin",
                "role": "administrator",
            }
        return None


class ApiRequestConsoleLogTests(unittest.TestCase):
    def setUp(self):
        self.module = load_server_console_ui()
        self.logger = self.module.ApiRequestConsoleLog(max_entries=20)
        self.app = Flask(__name__)
        self.logger.install(self.app, DummyUserManager())

        @self.app.get("/api/admin/users")
        def noisy_users_get():
            return jsonify({"users": []})

        @self.app.post("/api/admin/users")
        def important_users_post():
            return jsonify({"status": "created"}), 201

        @self.app.get("/api/check")
        def api_check():
            return jsonify({"status": "ok"})

        @self.app.get("/api/import-export/exams/5/export")
        def export_exam():
            return jsonify({"status": "ok"})

        self.client = self.app.test_client()

    def test_should_skip_noisy_bulk_gets(self):
        self.client.get("/api/admin/users")
        self.assertEqual(self.logger.list_entries(), [])

    def test_should_log_mutating_requests(self):
        self.client.post("/api/admin/users", json={"name": "example"}, headers={"X-User": "admin"})
        entries = self.logger.list_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["method"], "POST")
        self.assertEqual(entries[0]["path"], "/api/admin/users")
        self.assertEqual(entries[0]["status_code"], 201)
        self.assertEqual(entries[0]["user_label"], "Admin User")

    def test_should_skip_health_signature_request(self):
        self.client.get("/api/check")
        self.assertEqual(self.logger.list_entries(), [])

    def test_should_keep_export_get_requests(self):
        self.client.get("/api/import-export/exams/5/export")
        entries = self.logger.list_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["method"], "GET")
        self.assertEqual(entries[0]["path"], "/api/import-export/exams/5/export")

    def test_build_server_console_html_uses_one_second_refresh_loop(self):
        html = self.module.build_server_console_html(
            app_root=APP_ROOT,
            initial_snapshot={"server": {}, "stats": {}, "users": [], "groups": [], "features": [], "activity": []},
        )
        self.assertIn("window.setInterval(App.refreshSnapshot, 1000);", html)
        self.assertIn("App.refreshLiveRegions();", html)
        self.assertIn('data-scroll-key="activity-list"', html)
        self.assertIn('id="nav-toggle"', html)
        self.assertIn('id="nav-menu"', html)
        self.assertIn('data-server-console-theme-select', html)
        self.assertIn('zertan.server_console.theme', html)

    def test_format_uptime_uses_hours_and_minutes(self):
        self.assertEqual(format_uptime(59), "00h 00m")
        self.assertEqual(format_uptime(3661), "01h 01m")


if __name__ == "__main__":
    unittest.main()
