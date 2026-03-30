import os
import sys
from pathlib import Path


if sys.platform.startswith("linux"):
    os.environ.setdefault("WEBKIT_DMABUF_RENDERER_DISABLE_GBM", "1")

    versioned_dist = Path(f"/usr/lib/python{sys.version_info.major}.{sys.version_info.minor}/dist-packages")
    generic_dist = Path("/usr/lib/python3/dist-packages")

    extra_paths = []
    for candidate in (versioned_dist, generic_dist):
        if candidate.is_dir():
            extra_paths.append(str(candidate))

    for path in reversed(extra_paths):
        if path not in sys.path:
            sys.path.insert(0, path)

    typelib_root = Path("/usr/lib/x86_64-linux-gnu/girepository-1.0")
    if typelib_root.is_dir():
        current = os.environ.get("GI_TYPELIB_PATH", "")
        if current:
            os.environ["GI_TYPELIB_PATH"] = f"{typelib_root}:{current}"
        else:
            os.environ["GI_TYPELIB_PATH"] = str(typelib_root)
