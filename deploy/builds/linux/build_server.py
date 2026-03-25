import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import build_wrapper_main


if __name__ == "__main__":
    build_wrapper_main("linux", "server")
