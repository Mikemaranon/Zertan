import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEPLOY_ROOT = ROOT / "deploy"
SRC_ROOT = DEPLOY_ROOT / "src"
BUILDS_ROOT = DEPLOY_ROOT / "builds"
PLATFORM_TO_DIR = {
    "windows": "windows",
    "linux": "linux",
    "macos": "mac",
}
PLATFORM_LABELS = {
    "windows": "Windows",
    "linux": "Linux",
    "macos": "macOS",
}


def normalize_platform():
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def build_directory_name(platform_name=None):
    return PLATFORM_TO_DIR[platform_name or normalize_platform()]


def source_builder_path(component):
    if component == "client":
        return SRC_ROOT / "client" / "build_release.py"
    if component == "server":
        return SRC_ROOT / "server" / "build_release.py"
    raise ValueError(f"Unsupported component: {component}")


def component_output_root(platform_name, component):
    return BUILDS_ROOT / build_directory_name(platform_name) / component


def platform_files_root(platform_name):
    return BUILDS_ROOT / build_directory_name(platform_name) / "files"


def runtime_env():
    env = dict(os.environ)
    cargo_bin = Path.home() / ".cargo" / "bin"
    current_path = env.get("PATH", "")

    if cargo_bin.exists():
        path_entries = current_path.split(os.pathsep) if current_path else []
        cargo_entry = str(cargo_bin)
        if cargo_entry not in path_entries:
            env["PATH"] = os.pathsep.join([cargo_entry, *path_entries]) if path_entries else cargo_entry

    return env


def run(command):
    subprocess.run(command, check=True, cwd=str(ROOT), env=runtime_env())


def ensure_platform(expected_platform):
    current_platform = normalize_platform()
    if current_platform != expected_platform:
        expected_label = PLATFORM_LABELS[expected_platform]
        current_label = PLATFORM_LABELS[current_platform]
        raise SystemExit(
            f"This build entrypoint targets {expected_label} and must run on {expected_label}. "
            f"Current platform: {current_label}."
        )


def build_component(expected_platform, component, version, *, skip_install=False):
    output_root = component_output_root(expected_platform, component)
    command = [
        sys.executable,
        str(source_builder_path(component)),
        "--version",
        version,
        "--build-root",
        str(output_root / "build"),
        "--release-root",
        str(platform_files_root(expected_platform)),
        "--preserve-release-root",
    ]

    if component == "server":
        command.extend(["--dist-root", str(output_root / "dist")])
    elif skip_install:
        command.append("--skip-install")
        command.extend(["--target-root", str(output_root / "build" / "cargo-target")])
    elif component == "client":
        command.extend(["--target-root", str(output_root / "build" / "cargo-target")])

    run(command)


def build_wrapper_main(expected_platform, component, argv=None):
    parser = argparse.ArgumentParser(
        description=f"Build the Zertan {component} package for {PLATFORM_LABELS[expected_platform]}."
    )
    parser.add_argument("--version", required=True, help="Version label used in the release artifact name.")
    if component == "client":
        parser.add_argument(
            "--skip-install",
            action="store_true",
            help="Skip npm install and assume deploy/src/client/node_modules already exists.",
        )
    args = parser.parse_args(argv)

    ensure_platform(expected_platform)
    build_component(
        expected_platform,
        component,
        args.version,
        skip_install=getattr(args, "skip_install", False),
    )
