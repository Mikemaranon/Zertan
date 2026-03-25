#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import ROOT, build_component, ensure_platform


COMPONENT = "client"
EXECUTABLE_NAME = "zertan-client"
FILES_DIR = ROOT / "deploy" / "builds" / "linux" / "files"
REQUIREMENTS_PATH = ROOT / "deploy" / "src" / "requirements.txt"
SYSTEM_PACKAGES = [
    "build-essential",
    "pkg-config",
    "libglib2.0-dev",
    "libgtk-3-dev",
    "libwebkit2gtk-4.1-dev",
    "libxdo-dev",
    "libssl-dev",
    "libayatana-appindicator3-dev",
    "librsvg2-dev",
    "libsoup-3.0-dev",
    "python3-venv",
    "python3-pip",
    "python3-gi",
    "python3-gi-cairo",
    "gir1.2-gtk-3.0",
    "gir1.2-webkit2-4.1",
    "libgtk-3-0",
    "libwebkit2gtk-4.1-0",
    "nodejs",
    "npm",
    "dpkg-dev",
    "fakeroot",
    "curl",
]


def run(
    command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None, capture: bool = False
) -> subprocess.CompletedProcess[str] | None:
    if capture:
        return subprocess.run(
            command,
            check=True,
            cwd=str(cwd) if cwd else None,
            env=env,
            text=True,
            capture_output=True,
        )
    subprocess.run(command, check=True, cwd=str(cwd) if cwd else None, env=env)
    return None


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def sudo_prefix() -> list[str]:
    if os.geteuid() == 0:
        return []
    return ["sudo"]


def apt_install(packages: list[str]) -> None:
    prefix = sudo_prefix()
    run(prefix + ["apt-get", "update"])
    run(prefix + ["apt-get", "install", "-y", *packages])


def ensure_rust_toolchain() -> None:
    cargo_path = Path.home() / ".cargo" / "bin" / "cargo"
    rustup_path = Path.home() / ".cargo" / "bin" / "rustup"

    if not command_exists("cargo") and not cargo_path.exists():
        install_command = "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y"
        run(["bash", "-lc", install_command])

    rustup_executable = shutil.which("rustup") or str(rustup_path)
    env = dict(os.environ)
    env["PATH"] = f"{Path.home() / '.cargo' / 'bin'}:{env.get('PATH', '')}"
    run([rustup_executable, "update"], env=env)


def setup_virtualenv() -> None:
    venv_path = ROOT / ".venv"
    run(["python3", "-m", "venv", str(venv_path)], cwd=ROOT)
    pip_path = venv_path / "bin" / "pip"
    run([str(pip_path), "install", "--upgrade", "pip"], cwd=ROOT)
    run([str(pip_path), "install", "-r", str(REQUIREMENTS_PATH)], cwd=ROOT)


def prepare_debian12(skip_apt: bool) -> None:
    os.chdir(ROOT)
    if not skip_apt:
        apt_install(SYSTEM_PACKAGES)
    ensure_rust_toolchain()
    setup_virtualenv()
    print("Debian 12 environment is ready.")
    print("Activate virtualenv with: source .venv/bin/activate")


def deb_path(version: str) -> Path:
    return FILES_DIR / f"{EXECUTABLE_NAME}_{version}_amd64.deb"


def tar_path(version: str) -> Path:
    return FILES_DIR / f"{EXECUTABLE_NAME}_{version}_amd64.tar.gz"


def create_tar_from_deb(version: str) -> None:
    package_path = deb_path(version)
    if not package_path.exists():
        raise FileNotFoundError(f"Expected package not found: {package_path}")

    FILES_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"{EXECUTABLE_NAME}-") as temp_dir:
        stage_root = Path(temp_dir) / "root"
        run(["dpkg-deb", "-x", str(package_path), str(stage_root)])
        run(["tar", "-C", str(stage_root), "-czf", str(tar_path(version)), "."])


def build_release(version: str, *, skip_install: bool, package_format: str) -> None:
    ensure_platform("linux")
    build_component("linux", COMPONENT, version, skip_install=skip_install)
    if package_format == "tar":
        create_tar_from_deb(version)
        print(f"Portable tar.gz bundle generated in: {FILES_DIR}")
        return
    print(f"Debian package generated in: {FILES_DIR}")


def install_package(version: str, *, install_only: bool) -> None:
    package_path = deb_path(version)
    if not package_path.exists():
        raise FileNotFoundError(f"Required package not found: {package_path}")

    prefix = sudo_prefix()
    try:
        run(prefix + ["dpkg", "-i", str(package_path)])
    except subprocess.CalledProcessError:
        run(prefix + ["apt-get", "-f", "install", "-y"])

    if install_only:
        print("Package installed.")
        return

    executable = shutil.which(EXECUTABLE_NAME)
    if executable is None:
        print(f"{EXECUTABLE_NAME} executable not found in PATH.")
        return

    log_path = Path(f"/tmp/{EXECUTABLE_NAME}.log")
    with log_path.open("a", encoding="utf-8") as log_handle:
        subprocess.Popen([executable], stdout=log_handle, stderr=log_handle)
    print(f"Started {EXECUTABLE_NAME}. Log: {log_path}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the Zertan Linux client package.")
    parser.add_argument("--version", required=True, help="Version label used in the release artifact name.")
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip npm install and assume deploy/src/client/node_modules already exists.",
    )
    parser.add_argument(
        "--format",
        choices=("deb", "tar"),
        default="deb",
        help="Output package format. tar exports a .tar.gz from the generated .deb file.",
    )
    return parser


def command_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Linux client build and packaging helper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup_parser = subparsers.add_parser("setup", help="Prepare a Debian 12 build environment.")
    setup_parser.add_argument(
        "--skip-apt",
        action="store_true",
        help="Skip apt package installation and only set up Rust and Python environment.",
    )

    install_parser = subparsers.add_parser("install", help="Install the generated client package.")
    install_parser.add_argument("--version", required=True, help="Package version to install.")
    install_parser.add_argument(
        "--install-only",
        action="store_true",
        help="Install the package but do not attempt to launch the client.",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    args_list = list(argv if argv is not None else sys.argv[1:])
    if args_list[:1] == ["setup"] or args_list[:1] == ["install"]:
        args = command_arg_parser().parse_args(args_list)
        if args.command == "setup":
            prepare_debian12(args.skip_apt)
            return
        install_package(args.version, install_only=args.install_only)
        return

    args = build_arg_parser().parse_args(args_list)
    build_release(args.version, skip_install=args.skip_install, package_format=args.format)


if __name__ == "__main__":
    main()
