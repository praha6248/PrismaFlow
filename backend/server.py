"""Background Uvicorn server bound to a random free loopback port."""

from __future__ import annotations

import socket
import threading
import time

import httpx
import uvicorn

from .api import create_app


def free_port(host: str = "127.0.0.1") -> int:
    """Ask the OS for an unused TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


class BackgroundServer:
    """Runs the FastAPI app in a daemon thread so the GUI owns the main thread."""

    def __init__(self, host: str = "127.0.0.1", port: int | None = None) -> None:
        self.host = host
        self.port = port or free_port(host)
        config = uvicorn.Config(
            create_app(),
            host=self.host,
            port=self.port,
            log_level="warning",
            access_log=False,
            lifespan="off",
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, name="prismflow-api", daemon=True)

    @property
    def url(self) -> str:
        """Base URL of the running server."""
        return f"http://{self.host}:{self.port}"

    def start(self, timeout: float = 15.0) -> str:
        """Start the server thread and block until it answers health checks."""
        self._thread.start()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._server.started:
                try:
                    if httpx.get(f"{self.url}/api/projects", timeout=1).status_code == 200:
                        return self.url
                except httpx.HTTPError:
                    pass
            time.sleep(0.05)
        raise RuntimeError("backend server did not start in time")

    def run_blocking(self) -> None:
        """Serve in the calling thread until interrupted."""
        self._server.run()

    def stop(self) -> None:
        """Ask Uvicorn to exit."""
        self._server.should_exit = True
