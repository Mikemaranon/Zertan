import threading
import time
import webbrowser
from pathlib import Path

from .snapshot_builder import ConsoleSnapshotBuilder


class ServerConsoleBridge:
    def __init__(
        self,
        *,
        backend,
        api_request_log,
        runtime_config,
        display_host,
        port,
        base_url,
        data_dir,
        server_thread,
        stop_server_callback,
    ):
        self.backend = backend
        self.db = backend.DBManager
        self.api_request_log = api_request_log
        self.runtime_config = dict(runtime_config)
        self.display_host = display_host
        self.port = int(port)
        self.base_url = str(base_url)
        self.data_dir = Path(data_dir).resolve()
        self.server_thread = server_thread
        self.stop_server_callback = stop_server_callback
        self.snapshot_builder = ConsoleSnapshotBuilder(
            backend=backend,
            api_request_log=api_request_log,
            runtime_config=runtime_config,
            display_host=display_host,
            port=port,
            base_url=base_url,
            data_dir=data_dir,
            server_thread=server_thread,
        )
        self.started_at = time.time()
        self._lock = threading.Lock()
        self._stopping = False

    def get_console_snapshot(self):
        with self._lock:
            return self._build_snapshot()

    def refresh_console(self):
        return self.get_console_snapshot()

    def open_browser(self, path=""):
        normalized = self._normalize_browser_path(path)
        opened = webbrowser.open(f"{self.base_url}{normalized}")
        return {"status": "ok" if opened else "failed", "url": f"{self.base_url}{normalized}"}

    def toggle_feature(self, feature_key, enabled):
        with self._lock:
            existing = self.db.site_features.get(feature_key)
            if not existing:
                return {"status": "error", "message": "Feature not found."}
            updated = self.db.site_features.set_enabled(feature_key, bool(enabled))
            return {
                "status": "ok",
                "feature": updated,
                "snapshot": self._build_snapshot(),
            }

    def request_shutdown(self):
        if self._stopping:
            return {"status": "stopping"}
        self._stopping = True
        worker = threading.Thread(target=self.stop_server_callback, daemon=True)
        worker.start()
        return {"status": "stopping"}

    def _build_snapshot(self):
        return self.snapshot_builder.build(started_at=self.started_at, stopping=self._stopping)

    def _normalize_browser_path(self, path):
        raw = str(path or "").strip()
        if not raw:
            return "/"
        if not raw.startswith("/") or raw.startswith("//"):
            return "/"
        return raw
