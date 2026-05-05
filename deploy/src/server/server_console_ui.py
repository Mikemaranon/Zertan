try:
    from .console_ui import ApiRequestConsoleLog, ServerConsoleBridge, build_server_console_html
except ImportError:
    import sys
    from pathlib import Path

    MODULE_ROOT = Path(__file__).resolve().parent
    if str(MODULE_ROOT) not in sys.path:
        sys.path.insert(0, str(MODULE_ROOT))

    from console_ui import ApiRequestConsoleLog, ServerConsoleBridge, build_server_console_html

__all__ = [
    "ApiRequestConsoleLog",
    "ServerConsoleBridge",
    "build_server_console_html",
]
