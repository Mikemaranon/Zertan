import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.support_m import runtime_config


class RuntimeConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="zertan-runtime-config-")
        self.addCleanup(self.temp_dir.cleanup)
        self.original_env = os.environ.copy()
        for key in list(os.environ):
            if key.startswith("ZERTAN_") or key in {"SECRET_KEY", "HOST", "PORT"}:
                os.environ.pop(key, None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_get_runtime_config_parses_environment_and_uses_absolute_paths(self):
        data_root = Path(self.temp_dir.name) / "data-root"
        media_root = Path(self.temp_dir.name) / "custom-media"

        os.environ["ZERTAN_DATA_DIR"] = str(data_root)
        os.environ["ZERTAN_MEDIA_ROOT"] = str(media_root)
        os.environ["ZERTAN_DEBUG"] = "true"
        os.environ["ZERTAN_COOKIE_SECURE"] = "yes"
        os.environ["ZERTAN_COOKIE_SAMESITE"] = "Strict"
        os.environ["ZERTAN_JWT_HOURS"] = "12"
        os.environ["HOST"] = "127.0.0.1"
        os.environ["PORT"] = "6060"
        os.environ["ZERTAN_BOOTSTRAP_ADMIN_USERNAME"] = " admin "
        os.environ["ZERTAN_BOOTSTRAP_ADMIN_PASSWORD"] = "bootstrap-secret"
        os.environ["ZERTAN_BOOTSTRAP_ADMIN_EMAIL"] = " admin@zertan.local "
        os.environ["SECRET_KEY"] = "runtime-config-secret-key"

        config = runtime_config.get_runtime_config()

        self.assertEqual(config["data_root"], data_root.resolve())
        self.assertEqual(config["db_path"], (data_root / "database" / "zertan.db").resolve())
        self.assertEqual(config["media_root"], media_root.resolve())
        self.assertTrue(config["debug"])
        self.assertTrue(config["cookie_secure"])
        self.assertEqual(config["cookie_samesite"], "Strict")
        self.assertEqual(config["jwt_lifetime_hours"], 12)
        self.assertEqual(config["host"], "127.0.0.1")
        self.assertEqual(config["port"], 6060)
        self.assertEqual(config["bootstrap_admin_username"], "admin")
        self.assertEqual(config["bootstrap_admin_password"], "bootstrap-secret")
        self.assertEqual(config["bootstrap_admin_email"], "admin@zertan.local")
        self.assertTrue(config["db_path"].parent.exists())
        self.assertTrue(config["media_root"].exists())

    def test_get_runtime_config_rejects_insecure_secret_when_not_debugging(self):
        os.environ["SECRET_KEY"] = "change-this-before-production"
        os.environ["ZERTAN_DEBUG"] = "0"

        with self.assertRaisesRegex(RuntimeError, "requires SECRET_KEY"):
            runtime_config.get_runtime_config()

    def test_get_runtime_config_seed_demo_content_defaults_to_debug_value(self):
        os.environ["SECRET_KEY"] = "runtime-config-secret-key"
        os.environ["ZERTAN_DEBUG"] = "1"
        debug_config = runtime_config.get_runtime_config()

        os.environ["ZERTAN_DEBUG"] = "0"
        os.environ["ZERTAN_SEED_DEMO_CONTENT"] = "1"
        seeded_config = runtime_config.get_runtime_config()

        self.assertTrue(debug_config["seed_demo_content"])
        self.assertTrue(seeded_config["seed_demo_content"])

    def test_resolve_db_path_prefers_configured_path_and_migrates_legacy_location(self):
        data_root = Path(self.temp_dir.name) / "data"
        data_root.mkdir(parents=True, exist_ok=True)

        configured_db = Path(self.temp_dir.name) / "configured" / "custom.db"
        os.environ["ZERTAN_DB_PATH"] = str(configured_db)
        configured = runtime_config._resolve_db_path(data_root)
        self.assertEqual(configured, configured_db.resolve())

        os.environ.pop("ZERTAN_DB_PATH", None)
        legacy_db = data_root / "utils" / "zertan.db"
        legacy_db.parent.mkdir(parents=True, exist_ok=True)
        legacy_db.write_text("legacy-db", encoding="utf-8")
        legacy_lock = legacy_db.with_name("zertan.db.init.lock")
        legacy_lock.write_text("lock", encoding="utf-8")

        migrated = runtime_config._resolve_db_path(data_root)
        default_db = data_root / "database" / "zertan.db"

        self.assertEqual(migrated, default_db.resolve())
        self.assertTrue(default_db.exists())
        self.assertFalse(legacy_db.exists())
        self.assertTrue(default_db.with_name("zertan.db.init.lock").exists())

    def test_build_instance_id_is_stable_for_same_inputs(self):
        data_root = Path(self.temp_dir.name) / "data"
        db_path = data_root / "database" / "zertan.db"

        first = runtime_config._build_instance_id("secret-a", data_root, db_path)
        second = runtime_config._build_instance_id("secret-a", data_root, db_path)
        third = runtime_config._build_instance_id("secret-b", data_root, db_path)

        self.assertEqual(first, second)
        self.assertNotEqual(first, third)
        self.assertEqual(len(first), 16)


if __name__ == "__main__":
    unittest.main()
