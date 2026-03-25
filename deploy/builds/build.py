import argparse
import shutil
import sys
from pathlib import Path

from common import build_directory_name, normalize_platform, platform_files_root, run


BUILDS_ROOT = Path(__file__).resolve().parent


def component_script_path(platform_name, component):
    return BUILDS_ROOT / build_directory_name(platform_name) / f"build_{component}.py"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build Zertan native packages for the current operating system."
    )
    parser.add_argument("--version", required=True, help="Version label used in the release artifact names.")
    parser.add_argument(
        "--target",
        choices=("all", "client", "server"),
        default="all",
        help="Choose whether to build the client, the server, or both for the current platform.",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip npm install for the client build and assume deploy/src/client/node_modules already exists.",
    )
    args = parser.parse_args(argv)

    platform_name = normalize_platform()
    components = ("client", "server") if args.target == "all" else (args.target,)
    files_root = platform_files_root(platform_name)

    if files_root.exists():
        shutil.rmtree(files_root)
    files_root.mkdir(parents=True, exist_ok=True)

    for component in components:
        command = [
            sys.executable,
            str(component_script_path(platform_name, component)),
            "--version",
            args.version,
        ]
        if component == "client" and args.skip_install:
            command.append("--skip-install")
        run(command)


if __name__ == "__main__":
    main()
