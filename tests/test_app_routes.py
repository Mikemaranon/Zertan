import sys
import unittest
from pathlib import Path

from flask import Flask


ROOT = Path(__file__).resolve().parents[1]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
TEMPLATE_ROOT = ROOT / "app" / "web_app"
STATIC_ROOT = TEMPLATE_ROOT / "static"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.app_routes import AppRoutes


class _FakeSiteFeatures:
    def __init__(self, enabled_map):
        self._enabled_map = dict(enabled_map)

    def enabled_map(self):
        return dict(self._enabled_map)


class _FakeDbManager:
    def __init__(self, enabled_map):
        self.site_features = _FakeSiteFeatures(enabled_map)


class _FakeUserManager:
    ROLE_ORDER = {
        "user": 0,
        "reviewer": 1,
        "examiner": 2,
        "administrator": 3,
    }

    def __init__(self, user):
        self._user = user
        self.logged_out_token = None

    def check_user(self, request):
        return self._user

    def get_token_from_cookie(self, request):
        return "token-from-cookie"

    def logout(self, token):
        self.logged_out_token = token

    def user_has_role(self, user, required_role):
        if not user:
            return False
        user_role = user.get("role", "user")
        return self.ROLE_ORDER.get(user_role, -1) >= self.ROLE_ORDER.get(required_role, -1)


class AppRoutesTests(unittest.TestCase):
    def _build_app(self, *, user, enabled_map=None):
        app = Flask(
            __name__,
            template_folder=str(TEMPLATE_ROOT),
            static_folder=str(STATIC_ROOT),
        )
        app.secret_key = "test-secret"
        app.config["MEDIA_ROOT"] = str(ROOT / "app" / "web_server" / "data_m" / "assets")
        app.config["COOKIE_SECURE"] = False
        app.config["COOKIE_SAMESITE"] = "Lax"
        routes = AppRoutes(
            app,
            _FakeUserManager(user),
            _FakeDbManager(enabled_map or {"global_stats_page": True, "live_exams_page": True}),
        )
        return app, routes

    def test_catalog_redirects_to_login_when_user_is_missing(self):
        app, _ = self._build_app(user=None)

        with app.test_client() as client:
            response = client.get("/catalog")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/login"))

    def test_disabled_feature_returns_unavailable_page(self):
        app, _ = self._build_app(
            user={
                "id": 3,
                "display_name": "Reviewer",
                "role": "reviewer",
                "avatar_path": None,
            },
            enabled_map={"global_stats_page": False, "live_exams_page": True},
        )

        with app.test_client() as client:
            response = client.get("/global-stats")

        self.assertEqual(response.status_code, 403)
        self.assertIn(b"Workspace unavailable", response.data)

    def test_management_route_forbids_regular_user(self):
        app, _ = self._build_app(
            user={
                "id": 4,
                "display_name": "Regular User",
                "role": "user",
                "avatar_path": None,
            }
        )

        with app.test_client() as client:
            response = client.get("/management/exams")

        self.assertEqual(response.status_code, 403)
        self.assertIn(b"Access denied", response.data)

    def test_safe_return_to_accepts_internal_paths_only(self):
        app, routes = self._build_app(
            user={
                "id": 5,
                "display_name": "Reviewer",
                "role": "reviewer",
                "avatar_path": None,
            }
        )

        with app.test_request_context("/questions/9/edit?return_to=/management/exams"):
            self.assertEqual(routes._get_safe_return_to(), "/management/exams")

        with app.test_request_context("/questions/9/edit?return_to=//evil.example"):
            self.assertEqual(routes._get_safe_return_to(), "")


if __name__ == "__main__":
    unittest.main()
