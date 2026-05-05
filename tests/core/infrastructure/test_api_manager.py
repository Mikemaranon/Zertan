import sys
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask


ROOT = Path(__file__).resolve().parents[3]
WEB_SERVER_ROOT = ROOT / "app" / "web_server"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WEB_SERVER_ROOT))

from app.web_server.api_m.api_manager import ApiManager
from app.web_server.api_m.utils.domain_registry import discover_domain_api_classes


class _FakeUserManager:
    pass


class _FakeDbManager:
    pass


class _FakeServiceManager(SimpleNamespace):
    def __init__(self):
        super().__init__(exam_policy=object())


class ApiManagerTests(unittest.TestCase):
    def test_discover_domain_api_classes_excludes_base_api_and_finds_known_domains(self):
        discovered_names = {api_class.__name__ for api_class in discover_domain_api_classes()}

        self.assertIn("AuthAPI", discovered_names)
        self.assertIn("QuestionsAPI", discovered_names)
        self.assertIn("SystemAPI", discovered_names)
        self.assertNotIn("BaseAPI", discovered_names)

    def test_api_manager_registers_core_and_domain_routes(self):
        app = Flask(__name__)
        manager = ApiManager(
            app,
            _FakeUserManager(),
            _FakeDbManager(),
            _FakeServiceManager(),
        )

        rules = {rule.rule for rule in app.url_map.iter_rules()}

        self.assertIn("/api/check", rules)
        self.assertIn("/api/auth/login", rules)
        self.assertIn("/api/log-registry", rules)
        self.assertIn("/api/questions/<int:question_id>", rules)
        self.assertIn("/api/system/connection-info", rules)
        self.assertIn("AuthAPI", manager.registered_domains)
        self.assertIn("SystemAPI", manager.registered_domains)

    def test_api_manager_logs_registered_domains_and_api_check_exposes_instance_id(self):
        app = Flask(__name__)
        app.config["INSTANCE_ID"] = "instance-xyz"

        with patch("app.web_server.api_m.api_manager.register_domain_apis", return_value=["AuthAPI", "SystemAPI"]), patch.object(
            app.logger,
            "info",
        ) as logger_info:
            manager = ApiManager(
                app,
                _FakeUserManager(),
                _FakeDbManager(),
                _FakeServiceManager(),
            )

        self.assertEqual(manager.registered_domains, ["AuthAPI", "SystemAPI"])
        logger_info.assert_any_call("Loaded API: %s", "AuthAPI")
        logger_info.assert_any_call("Loaded API: %s", "SystemAPI")

        with app.test_client() as client:
            response = client.get("/api/check")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "status": "ok",
                "service": "zertan",
                "instance_id": "instance-xyz",
            },
        )


if __name__ == "__main__":
    unittest.main()
