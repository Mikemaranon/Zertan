import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


DEPLOY_ROOT = Path(__file__).resolve().parent
ROOT = DEPLOY_ROOT.parents[1]
SPEC_PATH = DEPLOY_ROOT / "zertan.spec"
BUILD_ROOT = DEPLOY_ROOT / "build"
DIST_ROOT = DEPLOY_ROOT / "dist"


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


def build_with_pyinstaller():
    env = dict(os.environ)
    env["PYINSTALLER_CONFIG_DIR"] = str(BUILD_ROOT / ".pyinstaller-cache")
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


def archive_dist(version):
    platform_name = normalize_platform()
    arch_name = normalize_arch()
    bundle_dir = DIST_ROOT / "Zertan"
    artifact_name = f"zertan-desktop-{version}-{platform_name}-{arch_name}"
    archive_base = DIST_ROOT / artifact_name

    if not bundle_dir.exists():
        raise FileNotFoundError(f"Missing bundle directory: {bundle_dir}")

    archive_path = shutil.make_archive(str(archive_base), "zip", root_dir=str(DIST_ROOT), base_dir="Zertan")
    final_path = Path(archive_path)
    target_path = final_path.with_name(f"{artifact_name}.zip")
    if final_path != target_path:
        if target_path.exists():
            target_path.unlink()
        final_path.replace(target_path)
    return target_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build a desktop release bundle for Zertan.")
    parser.add_argument("--version", required=True, help="Version label used in the release archive name.")
    args = parser.parse_args(argv)

    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    DIST_ROOT.mkdir(parents=True, exist_ok=True)
    build_with_pyinstaller()
    artifact = archive_dist(args.version)
    print(f"Desktop release created: {artifact}")


if __name__ == "__main__":
    main()
