import os
import tempfile
import unittest
from unittest.mock import patch

from lite.web_server.server import create_app


class LiteAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="zertan-lite-tests-")
        env = {
            "ZERTAN_LITE_DATA_DIR": self.temp_dir.name,
            "ZERTAN_LITE_MEDIA_ROOT": os.path.join(self.temp_dir.name, "assets"),
            "ZERTAN_LITE_DB_PATH": os.path.join(self.temp_dir.name, "database", "zertan-lite.db"),
            "ZERTAN_LITE_SEED_DEMO_CONTENT": "1",
            "ZERTAN_LITE_USER_LOGIN": "lite",
            "ZERTAN_LITE_USER_NAME": "Lite User",
            "ZERTAN_LITE_USER_ROLE": "administrator",
        }
        self.env_patcher = patch.dict(os.environ, env, clear=False)
        self.env_patcher.start()
        self.app = create_app(run_server=False)
        self.client = self.app.test_client()
        self.server = self.app.extensions["lite_server"]

    def tearDown(self):
        self.env_patcher.stop()
        self.temp_dir.cleanup()

    def test_root_redirects_to_home(self):
        response = self.client.get("/", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/home"))

    def test_login_redirects_to_home(self):
        response = self.client.get("/login", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/home"))

    def test_home_renders_lite_shell(self):
        with (
            patch.object(self.server.service_manager.connection_info, "list_detected_ipv4_addresses", return_value=["192.168.1.40"]),
            patch.object(self.server.service_manager.connection_info, "_select_primary_lan_ip", return_value="192.168.1.40"),
            patch.object(
                self.server.service_manager.connection_info,
                "_share_hint",
                return_value="This instance is listening beyond loopback and can be shared if the network path and firewall allow the configured port.",
            ),
        ):
            response = self.client.get("/home")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Zertan Lite", body)
        self.assertIn("Dashboard", body)
        self.assertIn("Exam Catalog", body)
        self.assertIn("Exam Management", body)
        self.assertIn("Connect from other devices", body)
        self.assertIn("192.168.1.40", body)
        self.assertIn("5051", body)
        self.assertNotIn("Global Stats", body)
        self.assertNotIn("Live Exams", body)
        self.assertNotIn("Admin Panel", body)

    def test_core_pages_render(self):
        exam = self.server.DBManager.exams.list_all()[0]
        question = self.server.DBManager.questions.list_for_exam(exam["id"], include_answers=True, include_archived=True)[0]
        for path in (
            "/dashboard",
            "/catalog",
            "/management/exams",
            f"/management/exams/{exam['id']}/questions",
            f"/exams/{exam['id']}/questions/new",
            f"/questions/{question['id']}/edit",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)

    def test_exam_management_uses_local_workspace_scope_only(self):
        response = self.client.get("/management/exams")
        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Import package", body)
        self.assertNotIn("Entire domain", body)
        self.assertNotIn("Specific groups", body)
        self.assertNotIn("Imported exam availability", body)

    def test_auth_me_uses_local_user(self):
        response = self.client.get("/api/auth/me")
        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["user"]["login_name"], "lite")
        self.assertEqual(payload["user"]["display_name"], "Lite User")
        self.assertEqual(payload["user"]["role"], "administrator")

    def test_removed_non_lite_pages_return_not_found(self):
        for path in ("/global-stats", "/live-exams", "/admin", "/access-info", "/log-registry"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)

    def test_removed_non_lite_api_surfaces_return_not_found(self):
        for path in (
            "/api/admin/users",
            "/api/live-exams",
            "/api/log-registry",
            "/api/system/connection-info",
            "/api/statistics/platform",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
