import sys
import tempfile
import unittest
from pathlib import Path

from flask import Flask


ROOT = Path(__file__).resolve().parents[2]
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
    def _build_app(self, *, user, enabled_map=None, media_root=None):
        app = Flask(
            __name__,
            template_folder=str(TEMPLATE_ROOT),
            static_folder=str(STATIC_ROOT),
        )
        app.secret_key = "test-secret"
        app.config["MEDIA_ROOT"] = str(media_root or (ROOT / "app" / "web_server" / "data_m" / "assets"))
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

    def test_home_and_login_redirect_authenticated_user_to_home_page(self):
        app, _ = self._build_app(
            user={
                "id": 2,
                "display_name": "Authenticated",
                "role": "user",
                "avatar_path": None,
            }
        )

        with app.test_client() as client:
            home_response = client.get("/")
            login_response = client.get("/login")

        self.assertEqual(home_response.status_code, 302)
        self.assertTrue(home_response.headers["Location"].endswith("/home"))
        self.assertEqual(login_response.status_code, 302)
        self.assertTrue(login_response.headers["Location"].endswith("/home"))

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

    def test_exam_management_shows_modal_actions_for_examiner(self):
        app, _ = self._build_app(
            user={
                "id": 5,
                "display_name": "Examiner",
                "role": "examiner",
                "avatar_path": None,
            }
        )

        with app.test_client() as client:
            response = client.get("/management/exams")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Managed exams", response.data)
        self.assertIn(b'id="open-exam-form-modal"', response.data)
        self.assertIn(b'id="open-import-form-modal"', response.data)
        self.assertIn(b'id="exam-form-modal"', response.data)
        self.assertIn(b'id="import-form-modal"', response.data)
        self.assertNotIn(b"Create or edit", response.data)

    def test_exam_management_hides_modal_actions_for_reviewer(self):
        app, _ = self._build_app(
            user={
                "id": 13,
                "display_name": "Reviewer",
                "role": "reviewer",
                "avatar_path": None,
            }
        )

        with app.test_client() as client:
            response = client.get("/management/exams")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Managed exams", response.data)
        self.assertNotIn(b'id="open-exam-form-modal"', response.data)
        self.assertNotIn(b'id="open-import-form-modal"', response.data)
        self.assertNotIn(b'id="exam-form-modal"', response.data)
        self.assertNotIn(b'id="import-form-modal"', response.data)

    def test_admin_route_requires_administrator_role(self):
        examiner_app, _ = self._build_app(
            user={
                "id": 10,
                "display_name": "Examiner",
                "role": "examiner",
                "avatar_path": None,
            }
        )
        admin_app, _ = self._build_app(
            user={
                "id": 11,
                "display_name": "Administrator",
                "role": "administrator",
                "avatar_path": None,
            }
        )

        with examiner_app.test_client() as client:
            forbidden_response = client.get("/admin")
        with admin_app.test_client() as client:
            allowed_response = client.get("/admin")

        self.assertEqual(forbidden_response.status_code, 403)
        self.assertIn(b"Access denied", forbidden_response.data)
        self.assertEqual(allowed_response.status_code, 200)
        self.assertIn(b"Admin Panel", allowed_response.data)

    def test_log_registry_requires_examiner_role(self):
        app, _ = self._build_app(
            user={
                "id": 6,
                "display_name": "Reviewer",
                "role": "reviewer",
                "avatar_path": None,
            }
        )

        with app.test_client() as client:
            response = client.get("/log-registry")

        self.assertEqual(response.status_code, 403)
        self.assertIn(b"Access denied", response.data)

    def test_log_registry_is_visible_for_examiner(self):
        app, _ = self._build_app(
            user={
                "id": 7,
                "display_name": "Examiner",
                "role": "examiner",
                "avatar_path": None,
            }
        )

        with app.test_client() as client:
            response = client.get("/log-registry")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Log Registry", response.data)

    def test_access_info_is_visible_for_regular_user(self):
        app, _ = self._build_app(
            user={
                "id": 8,
                "display_name": "Regular User",
                "role": "user",
                "avatar_path": None,
            }
        )

        with app.test_client() as client:
            response = client.get("/access-info")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Shared aliases", response.data)

    def test_login_page_bootstraps_theme_from_storage(self):
        app, _ = self._build_app(user=None)

        with app.test_client() as client:
            response = client.get("/login")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"zertan.theme", response.data)
        self.assertIn(b"document.documentElement.dataset.theme", response.data)

    def test_home_page_includes_profile_theme_selector(self):
        app, _ = self._build_app(
            user={
                "id": 9,
                "display_name": "Candidate",
                "role": "user",
                "avatar_path": None,
            }
        )

        with app.test_client() as client:
            response = client.get("/home")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"profile-theme-select", response.data)
        self.assertIn(b"zertan.theme", response.data)

    def test_logout_clears_cookie_and_sets_no_cache_headers(self):
        app, routes = self._build_app(
            user={
                "id": 12,
                "display_name": "Candidate",
                "role": "user",
                "avatar_path": None,
            }
        )

        with app.test_client() as client:
            response = client.get("/logout")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/login"))
        self.assertEqual(routes.user_manager.logged_out_token, "token-from-cookie")
        self.assertIn("token=;", response.headers.get("Set-Cookie", ""))
        self.assertEqual(response.headers["Cache-Control"], "no-cache, no-store, must-revalidate")
        self.assertEqual(response.headers["Pragma"], "no-cache")
        self.assertEqual(response.headers["Expires"], "0")

    def test_media_route_requires_auth_and_serves_private_assets(self):
        with tempfile.TemporaryDirectory(prefix="zertan-routes-media-") as temp_dir:
            media_root = Path(temp_dir)
            (media_root / "profiles").mkdir(parents=True, exist_ok=True)
            asset_path = media_root / "profiles" / "avatar.txt"
            asset_path.write_text("private-asset", encoding="utf-8")

            anonymous_app, _ = self._build_app(user=None, media_root=media_root)
            with anonymous_app.test_client() as client:
                unauthorized_response = client.get("/media/profiles/avatar.txt")

            user_app, _ = self._build_app(
                user={
                    "id": 13,
                    "display_name": "Candidate",
                    "role": "user",
                    "avatar_path": None,
                },
                media_root=media_root,
            )
            with user_app.test_client() as client:
                authorized_response = client.get("/media/profiles/avatar.txt")
                authorized_payload = authorized_response.data
                authorized_cache_control = authorized_response.headers["Cache-Control"]
                authorized_response.close()

        self.assertEqual(unauthorized_response.status_code, 401)
        self.assertEqual(authorized_response.status_code, 200)
        self.assertEqual(authorized_payload, b"private-asset")
        self.assertEqual(authorized_cache_control, "private, max-age=3600")

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
