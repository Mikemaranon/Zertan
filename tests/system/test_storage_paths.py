import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.support_m.storage_paths import (
    build_media_path,
    normalize_media_path,
    resolve_stored_path,
)


class StoragePathsTests(unittest.TestCase):
    def test_normalize_media_path_handles_legacy_prefix_leading_slash_and_backslashes(self):
        self.assertEqual(
            normalize_media_path("web_server/data_m/assets/questions\\7\\image.png"),
            "questions/7/image.png",
        )
        self.assertEqual(normalize_media_path("/profiles/5/avatar.png"), "profiles/5/avatar.png")
        self.assertEqual(normalize_media_path(""), "")

    def test_build_media_path_joins_clean_parts_and_skips_empty_values(self):
        built = build_media_path(" profiles ", "/7/", " avatar.png ", None, "")

        self.assertEqual(built, "profiles/7/avatar.png")

    def test_resolve_stored_path_uses_media_root_for_uploaded_assets(self):
        with tempfile.TemporaryDirectory(prefix="zertan-storage-paths-") as temp_dir:
            media_root = Path(temp_dir) / "assets"
            app_root = Path(temp_dir) / "app"

            resolved = resolve_stored_path(
                "questions/12/diagram.png",
                media_root=media_root,
                app_root=app_root,
            )

        self.assertEqual(resolved, (media_root / "questions/12/diagram.png").resolve())

    def test_resolve_stored_path_routes_static_prefix_to_app_root(self):
        with tempfile.TemporaryDirectory(prefix="zertan-storage-paths-") as temp_dir:
            media_root = Path(temp_dir) / "assets"
            app_root = Path(temp_dir) / "app"

            resolved = resolve_stored_path(
                "web_app/static/img/logo.svg",
                media_root=media_root,
                app_root=app_root,
            )

        self.assertEqual(resolved, (app_root / "web_app/static/img/logo.svg").resolve())

    def test_resolve_stored_path_returns_none_for_empty_values(self):
        with tempfile.TemporaryDirectory(prefix="zertan-storage-paths-") as temp_dir:
            media_root = Path(temp_dir) / "assets"
            app_root = Path(temp_dir) / "app"

            resolved = resolve_stored_path(
                "   ",
                media_root=media_root,
                app_root=app_root,
            )

        self.assertIsNone(resolved)


if __name__ == "__main__":
    unittest.main()
