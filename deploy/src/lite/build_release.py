import argparse
import os
import platform
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent
ROOT = MODULE_ROOT.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy.src.server import build_release as base_build_release


APP_NAME = "Zertan Lite"
PACKAGE_NAME = "zertan-lite"
DEPLOY_ROOT = MODULE_ROOT
SPEC_PATH = DEPLOY_ROOT / "zertan-lite.spec"
SOURCE_ICON_PATH = ROOT / "app" / "web_app" / "static" / "assets" / "Zertan.png"
BUILD_ROOT = DEPLOY_ROOT / "build"
DIST_ROOT = DEPLOY_ROOT / "dist"
RELEASE_ROOT = DEPLOY_ROOT / "release"
MACOS_CODESIGN_IDENTITY_ENV = base_build_release.MACOS_CODESIGN_IDENTITY_ENV
MACOS_ENTITLEMENTS_PATH_ENV = base_build_release.MACOS_ENTITLEMENTS_PATH_ENV
SERVER_VERSION_ENV = "ZERTAN_LITE_VERSION"
ICON_PNG_ENV = "ZERTAN_LITE_ICON_PNG"
ICON_ICO_ENV = "ZERTAN_LITE_ICON_ICO"
ICON_ICNS_ENV = "ZERTAN_LITE_ICON_ICNS"
PRESERVE_RELEASE_ROOT = False

normalize_arch = base_build_release.normalize_arch
normalize_platform = base_build_release.normalize_platform
normalize_debian_arch = base_build_release.normalize_debian_arch
release_basename = base_build_release.release_basename
ensure_clean_path = base_build_release.ensure_clean_path
prepare_output_directories = base_build_release.prepare_output_directories
icon_output_paths = base_build_release.icon_output_paths
load_pillow_image = base_build_release.load_pillow_image
create_square_icon_png = base_build_release.create_square_icon_png
create_windows_icon = base_build_release.create_windows_icon
create_macos_icon = base_build_release.create_macos_icon
generate_platform_icons = base_build_release.generate_platform_icons
build_with_pyinstaller = base_build_release.build_with_pyinstaller
require_existing_path = base_build_release.require_existing_path
resolve_macos_codesign_configuration = base_build_release.resolve_macos_codesign_configuration
sign_macos_app_bundle = base_build_release.sign_macos_app_bundle
stage_macos_disk_image_layout = base_build_release.stage_macos_disk_image_layout
package_windows = base_build_release.package_windows
package_macos = base_build_release.package_macos
linux_launcher_script = base_build_release.linux_launcher_script
package_linux = base_build_release.package_linux
package_release = base_build_release.package_release


def _sync_base_module():
    base_build_release.APP_NAME = APP_NAME
    base_build_release.PACKAGE_NAME = PACKAGE_NAME
    base_build_release.DEPLOY_ROOT = DEPLOY_ROOT
    base_build_release.ROOT = ROOT
    base_build_release.SPEC_PATH = SPEC_PATH
    base_build_release.SOURCE_ICON_PATH = SOURCE_ICON_PATH
    base_build_release.BUILD_ROOT = BUILD_ROOT
    base_build_release.DIST_ROOT = DIST_ROOT
    base_build_release.RELEASE_ROOT = RELEASE_ROOT
    base_build_release.MACOS_CODESIGN_IDENTITY_ENV = MACOS_CODESIGN_IDENTITY_ENV
    base_build_release.MACOS_ENTITLEMENTS_PATH_ENV = MACOS_ENTITLEMENTS_PATH_ENV
    base_build_release.SERVER_VERSION_ENV = SERVER_VERSION_ENV
    base_build_release.ICON_PNG_ENV = ICON_PNG_ENV
    base_build_release.ICON_ICO_ENV = ICON_ICO_ENV
    base_build_release.ICON_ICNS_ENV = ICON_ICNS_ENV
    base_build_release.PRESERVE_RELEASE_ROOT = PRESERVE_RELEASE_ROOT
    base_build_release.os = os
    base_build_release.platform = platform
    base_build_release.shutil = shutil
    base_build_release.subprocess = subprocess
    base_build_release.sys = sys
    base_build_release.normalize_arch = normalize_arch
    base_build_release.normalize_platform = normalize_platform
    base_build_release.normalize_debian_arch = normalize_debian_arch
    base_build_release.release_basename = release_basename
    base_build_release.ensure_clean_path = ensure_clean_path
    base_build_release.icon_output_paths = icon_output_paths
    base_build_release.load_pillow_image = load_pillow_image
    base_build_release.create_square_icon_png = create_square_icon_png
    base_build_release.create_windows_icon = create_windows_icon
    base_build_release.create_macos_icon = create_macos_icon
    base_build_release.require_existing_path = require_existing_path
    base_build_release.resolve_macos_codesign_configuration = resolve_macos_codesign_configuration
    base_build_release.sign_macos_app_bundle = sign_macos_app_bundle
    base_build_release.stage_macos_disk_image_layout = stage_macos_disk_image_layout
    base_build_release.linux_control_contents = linux_control_contents
    base_build_release.linux_desktop_entry = linux_desktop_entry
    base_build_release.linux_launcher_script = linux_launcher_script


def configure_output_roots(*, build_root="", dist_root="", release_root="", preserve_release_root=False):
    global BUILD_ROOT, DIST_ROOT, RELEASE_ROOT, PRESERVE_RELEASE_ROOT

    if build_root:
        BUILD_ROOT = Path(build_root).resolve()
    if dist_root:
        DIST_ROOT = Path(dist_root).resolve()
    if release_root:
        RELEASE_ROOT = Path(release_root).resolve()
    PRESERVE_RELEASE_ROOT = preserve_release_root


def linux_control_contents(version, architecture):
    return textwrap.dedent(
        f"""\
        Package: {PACKAGE_NAME}
        Version: {version}
        Section: education
        Priority: optional
        Architecture: {architecture}
        Maintainer: Zertan Release Automation <noreply@zertan.local>
        Depends: libgtk-3-0, libwebkit2gtk-4.1-0, python3-gi, python3-gi-cairo, gir1.2-gtk-3.0, gir1.2-webkit2-4.1
        Description: Zertan Lite single-user study workspace.
        """
    )


def linux_desktop_entry():
    return textwrap.dedent(
        f"""\
        [Desktop Entry]
        Version=1.0
        Type=Application
        Name={APP_NAME}
        Comment=Zertan Lite single-user app
        Exec=/usr/bin/{PACKAGE_NAME} %U
        Icon={PACKAGE_NAME}
        Terminal=false
        Categories=Education;
        """
    )


def run_builder_step(callback, *args, **kwargs):
    _sync_base_module()
    return callback(*args, **kwargs)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the native Lite release package for Zertan.")
    parser.add_argument("--version", required=True, help="Version label used in the release artifact name.")
    parser.add_argument("--build-root", default="", help="Optional directory for intermediate build files.")
    parser.add_argument("--dist-root", default="", help="Optional directory for raw packaged app bundles.")
    parser.add_argument("--release-root", default="", help="Optional directory for the final release artifact.")
    parser.add_argument(
        "--preserve-release-root",
        action="store_true",
        help="Keep any existing release directory contents instead of clearing the directory first.",
    )
    args = parser.parse_args(argv)

    configure_output_roots(
        build_root=args.build_root,
        dist_root=args.dist_root,
        release_root=args.release_root,
        preserve_release_root=args.preserve_release_root,
    )
    run_builder_step(prepare_output_directories)
    run_builder_step(generate_platform_icons)
    run_builder_step(build_with_pyinstaller, args.version)
    artifact = run_builder_step(package_release, args.version)
    print(f"Lite release created: {artifact}")


if __name__ == "__main__":
    main()
