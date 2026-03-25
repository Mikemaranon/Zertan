import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy.client import build_release


class ClientBuildReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="zertan-client-build-")
        self.addCleanup(self.temp_dir.cleanup)
        self.workspace = Path(self.temp_dir.name)
        self.client_root = self.workspace / "client"
        self.src_tauri_root = self.client_root / "src-tauri"
        self.build_root = self.client_root / "build"
        self.release_root = self.client_root / "release"
        self.bundle_root = self.src_tauri_root / "target" / "release" / "bundle"
        self.package_json_path = self.client_root / "package.json"
        self.tauri_config_path = self.src_tauri_root / "tauri.conf.json"
        self.cargo_toml_path = self.src_tauri_root / "Cargo.toml"

        self.bundle_root.mkdir(parents=True, exist_ok=True)
        self.release_root.mkdir(parents=True, exist_ok=True)
        self.package_json_path.parent.mkdir(parents=True, exist_ok=True)
        self.src_tauri_root.mkdir(parents=True, exist_ok=True)
        self.package_json_path.write_text('{"name":"zertan-client","version":"0.1.0"}\n', encoding="utf-8")
        self.tauri_config_path.write_text('{"productName":"Zertan Client","version":"0.1.0"}\n', encoding="utf-8")
        self.cargo_toml_path.write_text('[package]\nname = "zertan-client"\nversion = "0.1.0"\n', encoding="utf-8")

    def patch_paths(self):
        return patch.multiple(
            build_release,
            CLIENT_ROOT=self.client_root,
            SRC_TAURI_ROOT=self.src_tauri_root,
            BUILD_ROOT=self.build_root,
            RELEASE_ROOT=self.release_root,
            PACKAGE_JSON_PATH=self.package_json_path,
            TAURI_CONFIG_PATH=self.tauri_config_path,
            CARGO_TOML_PATH=self.cargo_toml_path,
        )

    def test_package_release_copies_windows_installer_to_normalized_name(self):
        artifact_source = self.bundle_root / "nsis" / "Zertan Client_1.2.3_x64-setup.exe"
        artifact_source.parent.mkdir(parents=True, exist_ok=True)
        artifact_source.write_bytes(b"client-exe")

        with self.patch_paths(), patch.object(build_release, "normalize_platform", return_value="windows"), patch.object(
            build_release,
            "normalize_arch",
            return_value="x64",
        ):
            artifact = build_release.package_release("1.2.3")

        self.assertEqual(artifact, self.release_root / "zertan-client-1.2.3-windows-x64.exe")
        self.assertEqual(artifact.read_bytes(), b"client-exe")

    def test_package_release_copies_linux_deb_to_normalized_name(self):
        artifact_source = self.bundle_root / "deb" / "zertan-client_1.2.3_amd64.deb"
        artifact_source.parent.mkdir(parents=True, exist_ok=True)
        artifact_source.write_bytes(b"client-deb")

        with self.patch_paths(), patch.object(build_release, "normalize_platform", return_value="linux"), patch.object(
            build_release,
            "normalize_arch",
            return_value="x64",
        ):
            artifact = build_release.package_release("1.2.3")

        self.assertEqual(artifact, self.release_root / "zertan-client_1.2.3_amd64.deb")
        self.assertEqual(artifact.read_bytes(), b"client-deb")

    def test_package_release_builds_macos_dmg_from_app_bundle(self):
        artifact_source = self.bundle_root / "macos" / "Zertan Client.app"
        executable = artifact_source / "Contents" / "MacOS" / "Zertan Client"
        executable.parent.mkdir(parents=True, exist_ok=True)
        executable.write_text("binary", encoding="utf-8")

        expected_artifact = self.release_root / "zertan-client-1.2.3-macos-arm64.dmg"
        commands = []

        def fake_run(command, check):
            self.assertTrue(check)
            commands.append(command)
            if command[0] == "codesign":
                self.assertEqual(command[-1], str(self.build_root / "dmg-staging" / "Zertan Client.app"))
                return
            self.assertEqual(command[0], "hdiutil")
            self.assertEqual(Path(command[-1]), expected_artifact)
            expected_artifact.write_bytes(b"dmg")

        with (
            self.patch_paths(),
            patch.object(build_release, "normalize_platform", return_value="macos"),
            patch.object(build_release, "normalize_arch", return_value="arm64"),
            patch.object(build_release.subprocess, "run", side_effect=fake_run),
        ):
            artifact = build_release.package_release("1.2.3")

        self.assertEqual(artifact, expected_artifact)
        self.assertTrue((self.build_root / "dmg-staging" / "Zertan Client.app").exists())
        self.assertTrue((self.build_root / "dmg-staging" / "Applications").is_symlink())
        self.assertEqual(
            (self.build_root / "dmg-staging" / "Applications").resolve(),
            Path("/Applications"),
        )
        self.assertEqual(commands[0][:5], ["codesign", "--force", "--deep", "--sign", "-"])
        self.assertEqual(commands[1][0], "hdiutil")

    def test_versioned_build_updates_and_restores_versions(self):
        with self.patch_paths():
            with build_release.versioned_build("2.4.0"):
                package_payload = json.loads(self.package_json_path.read_text(encoding="utf-8"))
                tauri_payload = json.loads(self.tauri_config_path.read_text(encoding="utf-8"))
                cargo_contents = self.cargo_toml_path.read_text(encoding="utf-8")

                self.assertEqual(package_payload["version"], "2.4.0")
                self.assertEqual(tauri_payload["version"], "2.4.0")
                self.assertIn('version = "2.4.0"', cargo_contents)

            restored_package = json.loads(self.package_json_path.read_text(encoding="utf-8"))
            restored_tauri = json.loads(self.tauri_config_path.read_text(encoding="utf-8"))
            restored_cargo = self.cargo_toml_path.read_text(encoding="utf-8")

        self.assertEqual(restored_package["version"], "0.1.0")
        self.assertEqual(restored_tauri["version"], "0.1.0")
        self.assertIn('version = "0.1.0"', restored_cargo)

    def test_build_tauri_bundle_uses_npm_cmd_on_windows(self):
        commands = []

        def fake_run(command, *, cwd):
            commands.append((command, cwd))

        with (
            self.patch_paths(),
            patch.object(build_release, "run_command", side_effect=fake_run),
            patch.object(build_release, "normalize_platform", return_value="windows"),
        ):
            build_release.build_tauri_bundle("2.4.0")

        self.assertEqual(
            commands[0][0],
            ["npm.cmd", "run", "tauri", "build", "--", "--bundles", "nsis"],
        )

    def test_resolve_macos_codesign_configuration_uses_defaults(self):
        with patch.dict(os.environ, {}, clear=False):
            identity, entitlements_path = build_release.resolve_macos_codesign_configuration()

        self.assertEqual(identity, "-")
        self.assertIsNone(entitlements_path)
