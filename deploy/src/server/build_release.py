import argparse
import os
import platform
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path


APP_NAME = "Zertan Server"
PACKAGE_NAME = "zertan-server"
DEPLOY_ROOT = Path(__file__).resolve().parent
ROOT = DEPLOY_ROOT.parents[2]
SPEC_PATH = DEPLOY_ROOT / "zertan.spec"
SOURCE_ICON_PATH = ROOT / "app" / "web_app" / "static" / "assets" / "Zertan.png"
BUILD_ROOT = DEPLOY_ROOT / "build"
DIST_ROOT = DEPLOY_ROOT / "dist"
RELEASE_ROOT = DEPLOY_ROOT / "release"
MACOS_CODESIGN_IDENTITY_ENV = "ZERTAN_MACOS_CODESIGN_IDENTITY"
MACOS_ENTITLEMENTS_PATH_ENV = "ZERTAN_MACOS_ENTITLEMENTS_PATH"
SERVER_VERSION_ENV = "ZERTAN_SERVER_VERSION"
PRESERVE_RELEASE_ROOT = False


def configure_output_roots(*, build_root="", dist_root="", release_root="", preserve_release_root=False):
    global BUILD_ROOT, DIST_ROOT, RELEASE_ROOT, PRESERVE_RELEASE_ROOT

    if build_root:
        BUILD_ROOT = Path(build_root).resolve()
    if dist_root:
        DIST_ROOT = Path(dist_root).resolve()
    if release_root:
        RELEASE_ROOT = Path(release_root).resolve()
    PRESERVE_RELEASE_ROOT = preserve_release_root


def normalize_arch():
    machine = platform.machine().lower()
    aliases = {
        "amd64": "x64",
        "x86_64": "x64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }
    return aliases.get(machine, machine or "unknown")


def normalize_platform():
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def normalize_debian_arch():
    arch_name = normalize_arch()
    aliases = {
        "x64": "amd64",
        "arm64": "arm64",
    }
    return aliases.get(arch_name, arch_name)


def release_basename(version, *, platform_name=None, arch_name=None):
    platform_name = platform_name or normalize_platform()
    arch_name = arch_name or normalize_arch()
    return f"{PACKAGE_NAME}-{version}-{platform_name}-{arch_name}"


def ensure_clean_path(path):
    target = Path(path)
    if target.is_dir():
        shutil.rmtree(target)
    elif target.exists():
        target.unlink()


def prepare_output_directories():
    for root in (BUILD_ROOT, DIST_ROOT):
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)

    if RELEASE_ROOT.exists() and not PRESERVE_RELEASE_ROOT:
        shutil.rmtree(RELEASE_ROOT)
    RELEASE_ROOT.mkdir(parents=True, exist_ok=True)


def icon_output_paths():
    icon_root = BUILD_ROOT / "icons"
    return {
        "root": icon_root,
        "png": icon_root / f"{PACKAGE_NAME}.png",
        "ico": icon_root / f"{PACKAGE_NAME}.ico",
        "icns": icon_root / f"{PACKAGE_NAME}.icns",
    }


def load_pillow_image():
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Server icon generation requires Pillow. Install deploy/src/server/requirements.txt first."
        ) from exc
    return Image


def create_square_icon_png(source_path, target_path, *, canvas_size=1024):
    Image = load_pillow_image()
    source = Path(source_path)
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(source) as image:
        rgba = image.convert("RGBA")
        scale = min(canvas_size / rgba.width, canvas_size / rgba.height)
        resized = rgba.resize(
            (max(1, round(rgba.width * scale)), max(1, round(rgba.height * scale))),
            Image.Resampling.LANCZOS,
        )

    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    offset = (
        (canvas_size - resized.width) // 2,
        (canvas_size - resized.height) // 2,
    )
    canvas.paste(resized, offset, resized)
    canvas.save(target, format="PNG")
    return target


def create_windows_icon(square_png_path, ico_path):
    Image = load_pillow_image()
    with Image.open(square_png_path) as image:
        image.save(
            ico_path,
            format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )
    return ico_path


def create_macos_icon(square_png_path, icns_path):
    Image = load_pillow_image()
    target = Path(icns_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(square_png_path) as image:
        image.save(target, format="ICNS")

    return icns_path


def generate_platform_icons():
    if not SOURCE_ICON_PATH.exists():
        raise FileNotFoundError(f"Missing application icon source: {SOURCE_ICON_PATH}")

    paths = icon_output_paths()
    ensure_clean_path(paths["root"])
    paths["root"].mkdir(parents=True, exist_ok=True)

    square_png = create_square_icon_png(SOURCE_ICON_PATH, paths["png"])
    os.environ["ZERTAN_SERVER_ICON_PNG"] = str(square_png)

    platform_name = normalize_platform()
    if platform_name == "windows":
        os.environ["ZERTAN_SERVER_ICON_ICO"] = str(create_windows_icon(square_png, paths["ico"]))
    elif platform_name == "macos":
        os.environ["ZERTAN_SERVER_ICON_ICNS"] = str(create_macos_icon(square_png, paths["icns"]))

    return paths


def build_with_pyinstaller(version):
    env = dict(os.environ)
    env["PYINSTALLER_CONFIG_DIR"] = str(BUILD_ROOT / ".pyinstaller-cache")
    env[SERVER_VERSION_ENV] = version
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--workpath",
        str(BUILD_ROOT),
        "--distpath",
        str(DIST_ROOT),
        str(SPEC_PATH),
    ]
    subprocess.run(command, check=True, cwd=str(ROOT), env=env)


def require_existing_path(path, description):
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"Missing {description}: {target}")
    return target


def resolve_macos_codesign_configuration():
    identity = os.environ.get(MACOS_CODESIGN_IDENTITY_ENV, "").strip() or "-"
    entitlements_value = os.environ.get(MACOS_ENTITLEMENTS_PATH_ENV, "").strip()
    entitlements_path = Path(entitlements_value) if entitlements_value else None
    if entitlements_path is not None:
        entitlements_path = require_existing_path(entitlements_path, "macOS entitlements file")
    return identity, entitlements_path


def sign_macos_app_bundle(app_bundle_path):
    app_bundle = require_existing_path(app_bundle_path, "macOS app bundle")
    identity, entitlements_path = resolve_macos_codesign_configuration()
    command = [
        "codesign",
        "--force",
        "--deep",
        "--sign",
        identity,
    ]

    if identity != "-":
        command.extend(["--options", "runtime", "--timestamp"])
    if entitlements_path is not None:
        command.extend(["--entitlements", str(entitlements_path)])

    command.append(str(app_bundle))
    subprocess.run(command, check=True)
    return app_bundle


def stage_macos_disk_image_layout(stage_root):
    applications_link = stage_root / "Applications"
    if applications_link.exists() or applications_link.is_symlink():
        applications_link.unlink()
    applications_link.symlink_to("/Applications")
    return applications_link


def package_windows(version):
    source = require_existing_path(DIST_ROOT / f"{APP_NAME}.exe", "Windows executable")
    target = RELEASE_ROOT / f"{release_basename(version, platform_name='windows')}.exe"
    ensure_clean_path(target)
    shutil.copy2(source, target)
    return target


def package_macos(version):
    source = require_existing_path(DIST_ROOT / f"{APP_NAME}.app", "macOS app bundle")
    target = RELEASE_ROOT / f"{release_basename(version, platform_name='macos')}.dmg"
    stage_root = BUILD_ROOT / "dmg-staging"
    staged_app = stage_root / source.name

    ensure_clean_path(stage_root)
    ensure_clean_path(target)
    stage_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, staged_app, symlinks=True)
    sign_macos_app_bundle(staged_app)
    stage_macos_disk_image_layout(stage_root)

    command = [
        "hdiutil",
        "create",
        "-volname",
        APP_NAME,
        "-srcfolder",
        str(stage_root),
        "-ov",
        "-format",
        "UDZO",
        str(target),
    ]
    subprocess.run(command, check=True)
    return require_existing_path(target, "macOS disk image")


def linux_control_contents(version, architecture):
    return textwrap.dedent(
        f"""\
        Package: {PACKAGE_NAME}
        Version: {version}
        Section: education
        Priority: optional
        Architecture: {architecture}
        Maintainer: Zertan Release Automation <noreply@zertan.local>
        Depends: libgtk-3-0, libwebkit2gtk-4.1-0
        Description: Zertan web server for browser-based study and exam sessions.
        """
    )


def linux_desktop_entry():
    return textwrap.dedent(
        f"""\
        [Desktop Entry]
        Version=1.0
        Type=Application
        Name={APP_NAME}
        Comment=Zertan web server
        Exec=/usr/bin/{PACKAGE_NAME} %U
        Icon={PACKAGE_NAME}
        Terminal=false
        Categories=Education;
        """
    )


def linux_launcher_script():
    return textwrap.dedent(
        f"""\
        #!/bin/sh
        exec "/opt/{APP_NAME}/{APP_NAME}" "$@"
        """
    )


def package_linux(version):
    architecture = normalize_debian_arch()
    source = require_existing_path(DIST_ROOT / APP_NAME, "Linux application bundle")
    package_root = BUILD_ROOT / "deb-root"
    install_root = package_root / "opt" / APP_NAME
    control_dir = package_root / "DEBIAN"
    desktop_entry_path = package_root / "usr" / "share" / "applications" / f"{PACKAGE_NAME}.desktop"
    launcher_path = package_root / "usr" / "bin" / PACKAGE_NAME
    icon_path = package_root / "usr" / "share" / "icons" / "hicolor" / "512x512" / "apps" / f"{PACKAGE_NAME}.png"
    target = RELEASE_ROOT / f"{PACKAGE_NAME}_{version}_{architecture}.deb"

    ensure_clean_path(package_root)
    ensure_clean_path(target)

    shutil.copytree(source, install_root)
    control_dir.mkdir(parents=True, exist_ok=True)
    desktop_entry_path.parent.mkdir(parents=True, exist_ok=True)
    launcher_path.parent.mkdir(parents=True, exist_ok=True)
    icon_path.parent.mkdir(parents=True, exist_ok=True)

    (control_dir / "control").write_text(
        linux_control_contents(version, architecture),
        encoding="utf-8",
    )
    desktop_entry_path.write_text(linux_desktop_entry(), encoding="utf-8")
    launcher_path.write_text(linux_launcher_script(), encoding="utf-8")
    launcher_path.chmod(0o755)
    desktop_entry_path.chmod(0o644)
    (control_dir / "control").chmod(0o644)

    generated_icon = icon_output_paths()["png"]
    bundled_icon = install_root / "app" / "web_app" / "static" / "assets" / "Zertan.png"
    if generated_icon.exists():
        shutil.copy2(generated_icon, icon_path)
    elif bundled_icon.exists():
        shutil.copy2(bundled_icon, icon_path)

    command = [
        "dpkg-deb",
        "--build",
        "--root-owner-group",
        str(package_root),
        str(target),
    ]
    subprocess.run(command, check=True)
    return require_existing_path(target, "Debian package")


def package_release(version):
    platform_name = normalize_platform()
    if platform_name == "macos":
        return package_macos(version)
    if platform_name == "windows":
        return package_windows(version)
    return package_linux(version)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the native server release package for Zertan.")
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
    prepare_output_directories()
    generate_platform_icons()
    build_with_pyinstaller(args.version)
    artifact = package_release(args.version)
    print(f"Server release created: {artifact}")


if __name__ == "__main__":
    main()
