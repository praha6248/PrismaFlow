"""PrismaFlow desktop entry point: starts the local API and opens a native web view window."""

from __future__ import annotations

import argparse
import os
import sys

GUI = "gtk" if sys.platform.startswith("linux") else None
if GUI == "gtk":
    os.environ.setdefault("WEBKIT_DISABLE_COMPOSITING_MODE", "1")
    os.environ.setdefault("PYWEBVIEW_GUI", "gtk")
if getattr(sys, "frozen", False):
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(prog="prismaflow", description="Local-first product discovery studio.")
    parser.add_argument("--port", type=int, default=None, help="serve the API on a fixed port")
    parser.add_argument("--server-only", action="store_true", help="run the backend without opening a window")
    parser.add_argument("--dev", metavar="URL", help="load the UI from a Vite dev server instead of the bundle")
    parser.add_argument("--debug", action="store_true", help="enable WebKit developer tools")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the application."""
    args = parse_args(sys.argv[1:] if argv is None else argv)

    from backend.server import BackgroundServer

    server = BackgroundServer(port=args.port)

    if args.server_only:
        print(f"PrismaFlow API listening on http://{server.host}:{server.port}", flush=True)
        server.run_blocking()
        return 0

    url = server.start()

    import webview

    window_url = args.dev or url
    webview.create_window(
        "PrismaFlow",
        window_url,
        width=1344,
        height=954,
        min_size=(960, 680),
        background_color="#F3EEFF",
        text_select=False,
    )
    try:
        webview.start(gui=GUI, debug=args.debug, private_mode=False)
    finally:
        server.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
