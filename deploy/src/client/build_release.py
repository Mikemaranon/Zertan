import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


APP_NAME = "Zertan Client"
PACKAGE_NAME = "zertan-client"
CLIENT_ROOT = Path(__file__).resolve().parent
ROOT = CLIENT_ROOT.parents[2]
SRC_TAURI_ROOT = CLIENT_ROOT / "src-tauri"
BUILD_ROOT = CLIENT_ROOT / "build"
RELEASE_ROOT = CLIENT_ROOT / "release"
PACKAGE_JSON_PATH = CLIENT_ROOT / "package.json"
TAURI_CONFIG_PATH = SRC_TAURI_ROOT / "tauri.conf.json"
CARGO_TOML_PATH = SRC_TAURI_ROOT / "Cargo.toml"
SOURCE_ICON_PATH = ROOT / "app" / "web_app" / "static" / "assets" / "Zertan.png"
MACOS_CODESIGN_IDENTITY_ENV = "ZERTAN_MACOS_CODESIGN_IDENTITY"
MACOS_ENTITLEMENTS_PATH_ENV = "ZERTAN_MACOS_ENTITLEMENTS_PATH"


def configure_output_roots(*, build_root="", release_root=""):
    global BUILD_ROOT, RELEASE_ROOT

    if build_root:
        BUILD_ROOT = Path(build_root).resolve()
    if release_root:
        RELEASE_ROOT = Path(release_root).resolve()


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
    for root in (BUILD_ROOT, RELEASE_ROOT):
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)


def load_pillow_image():
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Client icon generation requires Pillow. Install deploy/src/client/requirements.txt first."
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

    return target


def generate_platform_icons():
    if not SOURCE_ICON_PATH.exists():
        raise FileNotFoundError(f"Missing application icon source: {SOURCE_ICON_PATH}")

    icon_root = SRC_TAURI_ROOT / "icons"
    ensure_clean_path(icon_root)
    icon_root.mkdir(parents=True, exist_ok=True)

    square_png = create_square_icon_png(SOURCE_ICON_PATH, icon_root / "icon.png")
    create_square_icon_png(SOURCE_ICON_PATH, icon_root / "128x128.png", canvas_size=128)
    create_square_icon_png(SOURCE_ICON_PATH, icon_root / "32x32.png", canvas_size=32)
    create_windows_icon(square_png, icon_root / "icon.ico")
    create_macos_icon(square_png, icon_root / "icon.icns")


def update_json_version(path, version):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    payload["version"] = version
    Path(path).write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


def update_cargo_version(path, version):
    cargo = Path(path).read_text(encoding="utf-8")
    lines = []
    inside_package = False
    version_replaced = False
    for line in cargo.splitlines():
        stripped = line.strip()
        if stripped == "[package]":
            inside_package = True
        elif stripped.startswith("[") and stripped != "[package]":
            inside_package = False

        if inside_package and stripped.startswith("version = "):
            lines.append(f'version = "{version}"')
            version_replaced = True
        else:
            lines.append(line)

    if not version_replaced:
        raise RuntimeError(f"Could not replace Cargo version in {path}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_command(command, *, cwd):
    subprocess.run(command, check=True, cwd=str(cwd))


def node_executable(command_name):
    if normalize_platform() == "windows":
        return f"{command_name}.cmd"
    return command_name


def install_node_dependencies():
    run_command([node_executable("npm"), "install"], cwd=CLIENT_ROOT)


def require_existing_path(path, description):
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"Missing {description}: {target}")
    return target


class versioned_build:
    def __init__(self, version):
        self.version = version

    def __enter__(self):
        self.package_backup = PACKAGE_JSON_PATH.read_text(encoding="utf-8")
        self.tauri_backup = TAURI_CONFIG_PATH.read_text(encoding="utf-8")
        self.cargo_backup = CARGO_TOML_PATH.read_text(encoding="utf-8")
        update_json_version(PACKAGE_JSON_PATH, self.version)
        update_json_version(TAURI_CONFIG_PATH, self.version)
        update_cargo_version(CARGO_TOML_PATH, self.version)
        return self

    def __exit__(self, exc_type, exc, tb):
        PACKAGE_JSON_PATH.write_text(self.package_backup, encoding="utf-8")
        TAURI_CONFIG_PATH.write_text(self.tauri_backup, encoding="utf-8")
        CARGO_TOML_PATH.write_text(self.cargo_backup, encoding="utf-8")
        return False


def bundle_target():
    platform_name = normalize_platform()
    if platform_name == "windows":
        return "nsis"
    if platform_name == "macos":
        return "app"
    return "deb"


def build_tauri_bundle(version):
    with versioned_build(version):
        run_command(
            [node_executable("npm"), "run", "tauri", "build", "--", "--bundles", bundle_target()],
            cwd=CLIENT_ROOT,
        )


def release_source_glob():
    platform_name = normalize_platform()
    bundle_root = SRC_TAURI_ROOT / "target" / "release" / "bundle"
    if platform_name == "windows":
        return bundle_root / "nsis" / "*.exe"
    if platform_name == "macos":
        return bundle_root / "macos" / "*.app"
    return bundle_root / "deb" / "*.deb"


def locate_single_artifact():
    matches = sorted(release_source_glob().parent.glob(release_source_glob().name))
    if not matches:
        raise FileNotFoundError(f"No Tauri release artifacts found in {release_source_glob().parent}")
    return matches[-1]


def stage_macos_disk_image_layout(stage_root):
    applications_link = stage_root / "Applications"
    if applications_link.exists() or applications_link.is_symlink():
        applications_link.unlink()
    applications_link.symlink_to("/Applications")
    return applications_link


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


def package_macos(version, source):
    app_bundle = require_existing_path(source, "macOS app bundle")
    target = RELEASE_ROOT / f"{release_basename(version, platform_name='macos')}.dmg"
    stage_root = BUILD_ROOT / "dmg-staging"
    staged_app = stage_root / app_bundle.name

    ensure_clean_path(stage_root)
    ensure_clean_path(target)
    stage_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(app_bundle, staged_app, symlinks=True)
    sign_macos_app_bundle(staged_app)
    stage_macos_disk_image_layout(stage_root)

    subprocess.run(
        [
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
        ],
        check=True,
    )
    return require_existing_path(target, "macOS disk image")


def package_release(version):
    source = locate_single_artifact()
    platform_name = normalize_platform()
    arch_name = normalize_arch()
    if platform_name == "macos":
        return package_macos(version, source)

    suffix = source.suffix
    if platform_name == "linux":
        arch_name = normalize_debian_arch()
        target = RELEASE_ROOT / f"{PACKAGE_NAME}_{version}_{arch_name}{suffix}"
    else:
        target = RELEASE_ROOT / f"{release_basename(version, platform_name=platform_name, arch_name=arch_name)}{suffix}"
    ensure_clean_path(target)
    shutil.copy2(source, target)
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the native Tauri client release for Zertan.")
    parser.add_argument("--version", required=True, help="Version label used in the release artifact name.")
    parser.add_argument("--build-root", default="", help="Optional directory for intermediate build files.")
    parser.add_argument("--release-root", default="", help="Optional directory for the final release artifact.")
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip npm install and assume node_modules already exists.",
    )
    args = parser.parse_args(argv)

    configure_output_roots(
        build_root=args.build_root,
        release_root=args.release_root,
    )
    prepare_output_directories()
    generate_platform_icons()
    if not args.skip_install:
        install_node_dependencies()
    build_tauri_bundle(args.version)
    artifact = package_release(args.version)
    print(f"Client release created: {artifact}")


if __name__ == "__main__":
    main()
