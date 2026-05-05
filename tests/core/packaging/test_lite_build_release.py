import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy.src.lite import build_release


class LiteBuildReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="zertan-lite-build-release-")
        self.workspace = Path(self.temp_dir.name)
        self.build_root = self.workspace / "build"
        self.dist_root = self.workspace / "dist"
        self.release_root = self.workspace / "release"
        self.dist_root.mkdir(parents=True, exist_ok=True)
        self.release_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def patch_paths(self):
        return patch.multiple(
            build_release,
            BUILD_ROOT=self.build_root,
            DIST_ROOT=self.dist_root,
            RELEASE_ROOT=self.release_root,
        )

    def test_build_with_pyinstaller_exports_lite_version(self):
        commands = []

        def fake_run(command, check, cwd, env):
            self.assertTrue(check)
            commands.append((command, Path(cwd), env))

        with self.patch_paths(), patch.object(build_release.subprocess, "run", side_effect=fake_run):
            build_release.run_builder_step(build_release.build_with_pyinstaller, "2.4.0")

        command, cwd, env = commands[0]
        self.assertIn("PyInstaller", command)
        self.assertEqual(cwd, build_release.ROOT)
        self.assertEqual(env[build_release.SERVER_VERSION_ENV], "2.4.0")

    def test_package_macos_builds_lite_dmg_from_app_bundle(self):
        source_app = self.dist_root / "Zertan Lite.app"
        app_dir = source_app / "Contents" / "MacOS"
        app_dir.mkdir(parents=True, exist_ok=True)
        (app_dir / "Zertan Lite").write_text("binary", encoding="utf-8")

        expected_artifact = self.release_root / "zertan-lite-1.2.3-macos-arm64.dmg"
        commands = []

        def fake_run(command, check):
            self.assertTrue(check)
            commands.append(command)
            if command[0] == "codesign":
                self.assertEqual(command[-1], str(self.build_root / "dmg-staging" / "Zertan Lite.app"))
                return
            self.assertEqual(command[0], "hdiutil")
            self.assertEqual(Path(command[-1]), expected_artifact)
            expected_artifact.write_bytes(b"dmg")

        with (
            self.patch_paths(),
            patch.object(build_release, "normalize_arch", return_value="arm64"),
            patch.object(build_release.subprocess, "run", side_effect=fake_run),
        ):
            artifact = build_release.run_builder_step(build_release.package_macos, "1.2.3")

        self.assertEqual(artifact, expected_artifact)
        self.assertTrue((self.build_root / "dmg-staging" / "Zertan Lite.app").exists())
        self.assertTrue((self.build_root / "dmg-staging" / "Applications").is_symlink())
        self.assertEqual(commands[0][:5], ["codesign", "--force", "--deep", "--sign", "-"])
        self.assertEqual(commands[1][0], "hdiutil")


if __name__ == "__main__":
    unittest.main()
