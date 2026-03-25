import sys
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy.desktop import build_release


class BuildReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="zertan-build-release-")
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

    def test_generate_platform_icons_sets_windows_icon_env(self):
        source_icon = self.workspace / "Zertan.png"
        source_icon.write_bytes(b"png")
        generated_png = self.build_root / "icons" / "zertan-server.png"
        generated_ico = self.build_root / "icons" / "zertan-server.ico"

        with (
            self.patch_paths(),
            patch.object(build_release, "SOURCE_ICON_PATH", source_icon),
            patch.object(build_release, "normalize_platform", return_value="windows"),
            patch.object(build_release, "create_square_icon_png", return_value=generated_png) as create_png,
            patch.object(build_release, "create_windows_icon", return_value=generated_ico) as create_ico,
            patch.dict(build_release.os.environ, {}, clear=False),
        ):
            paths = build_release.generate_platform_icons()
            png_env = build_release.os.environ["ZERTAN_SERVER_ICON_PNG"]
            ico_env = build_release.os.environ["ZERTAN_SERVER_ICON_ICO"]

        create_png.assert_called_once()
        create_ico.assert_called_once_with(generated_png, paths["ico"])
        self.assertEqual(png_env, str(generated_png))
        self.assertEqual(ico_env, str(generated_ico))

    def test_generate_platform_icons_sets_macos_icon_env(self):
        source_icon = self.workspace / "Zertan.png"
        source_icon.write_bytes(b"png")
        generated_png = self.build_root / "icons" / "zertan-server.png"
        generated_icns = self.build_root / "icons" / "zertan-server.icns"

        with (
            self.patch_paths(),
            patch.object(build_release, "SOURCE_ICON_PATH", source_icon),
            patch.object(build_release, "normalize_platform", return_value="macos"),
            patch.object(build_release, "create_square_icon_png", return_value=generated_png) as create_png,
            patch.object(build_release, "create_macos_icon", return_value=generated_icns) as create_icns,
            patch.dict(build_release.os.environ, {}, clear=False),
        ):
            paths = build_release.generate_platform_icons()
            png_env = build_release.os.environ["ZERTAN_SERVER_ICON_PNG"]
            icns_env = build_release.os.environ["ZERTAN_SERVER_ICON_ICNS"]

        create_png.assert_called_once()
        create_icns.assert_called_once_with(generated_png, paths["icns"])
        self.assertEqual(png_env, str(generated_png))
        self.assertEqual(icns_env, str(generated_icns))

    def test_package_windows_copies_onefile_executable(self):
        source = self.dist_root / "Zertan Server.exe"
        source.write_bytes(b"windows-binary")

        with self.patch_paths(), patch.object(build_release, "normalize_arch", return_value="x64"):
            artifact = build_release.package_windows("1.2.3")

        self.assertEqual(artifact, self.release_root / "zertan-server-1.2.3-windows-x64.exe")
        self.assertEqual(artifact.read_bytes(), b"windows-binary")

    def test_package_macos_builds_dmg_from_signed_app_bundle(self):
        source_app = self.dist_root / "Zertan Server.app"
        app_dir = source_app / "Contents" / "MacOS"
        app_dir.mkdir(parents=True, exist_ok=True)
        (app_dir / "Zertan Server").write_text("binary", encoding="utf-8")

        expected_artifact = self.release_root / "zertan-server-1.2.3-macos-arm64.dmg"
        commands = []
        copytree_calls = []

        def fake_run(command, check):
            self.assertTrue(check)
            commands.append(command)
            if command[0] == "codesign":
                self.assertEqual(command[-1], str(self.build_root / "dmg-staging" / "Zertan Server.app"))
                return
            self.assertEqual(command[0], "hdiutil")
            self.assertEqual(Path(command[-1]), expected_artifact)
            expected_artifact.write_bytes(b"dmg")

        real_copytree = shutil.copytree

        def fake_copytree(source, destination, *args, **kwargs):
            copytree_calls.append((Path(source), Path(destination), kwargs.get("symlinks")))
            return real_copytree(source, destination, *args, **kwargs)

        with (
            self.patch_paths(),
            patch.object(build_release, "normalize_arch", return_value="arm64"),
            patch.object(build_release.shutil, "copytree", side_effect=fake_copytree),
            patch.object(build_release.subprocess, "run", side_effect=fake_run),
        ):
            artifact = build_release.package_macos("1.2.3")

        self.assertEqual(artifact, expected_artifact)
        self.assertTrue((self.build_root / "dmg-staging" / "Zertan Server.app").exists())
        self.assertTrue((self.build_root / "dmg-staging" / "Applications").is_symlink())
        self.assertEqual(
            (self.build_root / "dmg-staging" / "Applications").resolve(),
            Path("/Applications"),
        )
        self.assertEqual(
            copytree_calls[0],
            (source_app, self.build_root / "dmg-staging" / "Zertan Server.app", True),
        )
        self.assertEqual(commands[0][:5], ["codesign", "--force", "--deep", "--sign", "-"])
        self.assertEqual(commands[1][0], "hdiutil")

    def test_build_with_pyinstaller_exports_server_version(self):
        commands = []

        def fake_run(command, check, cwd, env):
            self.assertTrue(check)
            commands.append((command, Path(cwd), env))

        with self.patch_paths(), patch.object(build_release.subprocess, "run", side_effect=fake_run):
            build_release.build_with_pyinstaller("2.4.0")

        command, cwd, env = commands[0]
        self.assertIn("PyInstaller", command)
        self.assertEqual(cwd, build_release.ROOT)
        self.assertEqual(env[build_release.SERVER_VERSION_ENV], "2.4.0")

    def test_package_linux_builds_debian_layout(self):
        bundle_root = self.dist_root / "Zertan Server"
        (bundle_root / "app" / "web_app" / "static" / "assets").mkdir(parents=True, exist_ok=True)
        (bundle_root / "Zertan Server").write_text("linux-binary", encoding="utf-8")
        (bundle_root / "app" / "web_app" / "static" / "assets" / "Zertan.png").write_bytes(b"png")

        expected_artifact = self.release_root / "zertan-server_1.2.3_amd64.deb"

        def fake_run(command, check):
            self.assertTrue(check)
            self.assertEqual(command[0], "dpkg-deb")
            self.assertEqual(Path(command[-1]), expected_artifact)
            expected_artifact.write_bytes(b"deb")

        with (
            self.patch_paths(),
            patch.object(build_release, "normalize_arch", return_value="x64"),
            patch.object(build_release.subprocess, "run", side_effect=fake_run),
        ):
            artifact = build_release.package_linux("1.2.3")

        self.assertEqual(artifact, expected_artifact)
        control = (self.build_root / "deb-root" / "DEBIAN" / "control").read_text(encoding="utf-8")
        desktop_entry = (
            self.build_root / "deb-root" / "usr" / "share" / "applications" / "zertan-server.desktop"
        ).read_text(encoding="utf-8")
        launcher = (self.build_root / "deb-root" / "usr" / "bin" / "zertan-server").read_text(encoding="utf-8")
        icon = self.build_root / "deb-root" / "usr" / "share" / "icons" / "hicolor" / "512x512" / "apps" / "zertan-server.png"

        self.assertIn("Package: zertan-server", control)
        self.assertIn("Architecture: amd64", control)
        self.assertIn("Depends: libgtk-3-0, libwebkit2gtk-4.1-0", control)
        self.assertIn("Exec=/usr/bin/zertan-server %U", desktop_entry)
        self.assertIn("Terminal=false", desktop_entry)
        self.assertEqual(launcher, '#!/bin/sh\nexec "/opt/Zertan Server/Zertan Server" "$@"\n')
        self.assertTrue(icon.exists())



if __name__ == "__main__":
    unittest.main()
