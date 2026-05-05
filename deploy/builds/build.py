import argparse
import shutil
import sys
from pathlib import Path

from common import build_directory_name, normalize_platform, platform_files_root, run


BUILDS_ROOT = Path(__file__).resolve().parent
COMPONENT_ARTIFACT_PREFIXES = {
    "client": "zertan-client-",
    "server": "zertan-server-",
    "lite": "zertan-lite-",
}


def component_script_path(platform_name, component):
    return BUILDS_ROOT / build_directory_name(platform_name) / f"build_{component}.py"


def remove_path(path):
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def prepare_files_root(platform_name, components):
    files_root = platform_files_root(platform_name)
    if len(components) > 1:
        if files_root.exists():
            shutil.rmtree(files_root)
        files_root.mkdir(parents=True, exist_ok=True)
        return files_root

    files_root.mkdir(parents=True, exist_ok=True)
    artifact_prefix = COMPONENT_ARTIFACT_PREFIXES[components[0]]
    for candidate in files_root.iterdir():
        if candidate.name.startswith(artifact_prefix):
            remove_path(candidate)
    return files_root


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build Zertan native packages for the current operating system."
    )
    parser.add_argument("--version", required=True, help="Version label used in the release artifact names.")
    parser.add_argument(
        "--target",
        choices=("all", "client", "server", "lite"),
        default="all",
        help="Choose whether to build the client, the server, Lite, or every supported package for the current platform.",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip npm install for the client build and assume deploy/src/client/node_modules already exists.",
    )
    args = parser.parse_args(argv)

    platform_name = normalize_platform()
    components = ("client", "server", "lite") if args.target == "all" else (args.target,)
    prepare_files_root(platform_name, components)

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
