import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
BUILDS_ROOT = ROOT / "deploy" / "builds"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(BUILDS_ROOT) not in sys.path:
    sys.path.insert(0, str(BUILDS_ROOT))

import build as builds_entrypoint
import common as common_builds


class CommonBuildTests(unittest.TestCase):
    def test_source_builder_path_supports_lite(self):
        self.assertEqual(
            common_builds.source_builder_path("lite"),
            ROOT / "deploy" / "src" / "lite" / "build_release.py",
        )

    def test_build_component_routes_lite_through_python_packager(self):
        commands = []

        def fake_run(command):
            commands.append(command)

        with patch.object(common_builds, "run", side_effect=fake_run):
            common_builds.build_component("macos", "lite", "2.5.0")

        self.assertEqual(commands[0][0], sys.executable)
        self.assertIn(str(ROOT / "deploy" / "src" / "lite" / "build_release.py"), commands[0])
        self.assertIn("--dist-root", commands[0])
        self.assertNotIn("--target-root", commands[0])
        self.assertNotIn("--skip-install", commands[0])

    def test_build_entrypoint_includes_lite_in_all_target(self):
        commands = []

        def fake_run(command):
            commands.append(command)

        with tempfile.TemporaryDirectory(prefix="zertan-builds-files-") as temp_dir, patch.object(
            builds_entrypoint,
            "normalize_platform",
            return_value="macos",
        ), patch.object(
            builds_entrypoint,
            "platform_files_root",
            return_value=Path(temp_dir),
        ), patch.object(
            builds_entrypoint,
            "run",
            side_effect=fake_run,
        ):
            builds_entrypoint.main(["--version", "1.2.3", "--target", "all"])

        self.assertEqual(len(commands), 3)
        self.assertTrue(str(commands[0][1]).endswith("build_client.py"))
        self.assertTrue(str(commands[1][1]).endswith("build_server.py"))
        self.assertTrue(str(commands[2][1]).endswith("build_lite.py"))

    def test_build_entrypoint_lite_target_only_cleans_lite_artifacts(self):
        commands = []

        def fake_run(command):
            commands.append(command)

        with tempfile.TemporaryDirectory(prefix="zertan-builds-files-") as temp_dir:
            files_root = Path(temp_dir)
            client_artifact = files_root / "zertan-client-2.0.0-macos-arm64.dmg"
            server_artifact = files_root / "zertan-server-2.0.0-macos-arm64.dmg"
            lite_artifact = files_root / "zertan-lite-2.0.0-macos-arm64.dmg"
            client_artifact.write_text("client", encoding="utf-8")
            server_artifact.write_text("server", encoding="utf-8")
            lite_artifact.write_text("lite", encoding="utf-8")

            with patch.object(
                builds_entrypoint,
                "normalize_platform",
                return_value="macos",
            ), patch.object(
                builds_entrypoint,
                "platform_files_root",
                return_value=files_root,
            ), patch.object(
                builds_entrypoint,
                "run",
                side_effect=fake_run,
            ):
                builds_entrypoint.main(["--version", "1.2.3", "--target", "lite"])

            self.assertTrue(client_artifact.exists())
            self.assertTrue(server_artifact.exists())
            self.assertFalse(lite_artifact.exists())

        self.assertEqual(len(commands), 1)
        self.assertTrue(str(commands[0][1]).endswith("build_lite.py"))


if __name__ == "__main__":
    unittest.main()
