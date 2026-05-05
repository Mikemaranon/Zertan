import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lite.web_server.server import create_app


def main():
    print("============================")
    print("    Starting Zertan Lite    ")
    print("============================")
    create_app(run_server=True)


if __name__ == "__main__":
    main()
