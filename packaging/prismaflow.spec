import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, get_package_paths

root = Path(SPECPATH).parent
dist = root / "frontend" / "dist"
if not (dist / "index.html").is_file():
    raise SystemExit("frontend/dist is missing: run `npm run build` in frontend/ first")

_, playwright_path = get_package_paths("playwright")
browser_dir = Path(playwright_path) / "driver" / "package" / ".local-browsers"
bundle_chromium = os.environ.get("PRISMAFLOW_BUNDLE_CHROMIUM") == "1"
if bundle_chromium and not any(browser_dir.glob("chromium_headless_shell-*/INSTALLATION_COMPLETE")):
    raise SystemExit("Chromium is missing: run `PLAYWRIGHT_BROWSERS_PATH=0 python -m playwright install --only-shell chromium` first")
browser_data = [(str(browser_dir), "playwright/driver/package/.local-browsers")] if bundle_chromium else []

linux = sys.platform.startswith("linux")
icon = root / "packaging" / ("prismaflow.ico" if sys.platform == "win32" else "prismaflow.png")

hiddenimports = collect_submodules("uvicorn") + collect_submodules("webview.platforms") + ["trendspy", "networkx"]
if linux:
    hiddenimports += ["gi", "gi.repository.Gtk", "gi.repository.WebKit2"]

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    datas=[
        (str(dist), "frontend/dist"),
        *browser_data,
        *collect_data_files("webview"),
    ],
    hiddenimports=hiddenimports,
    excludes=[
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "tkinter",
        "pkg_resources",
        "setuptools",
        "PIL",
        "matplotlib",
        "IPython",
        "pytest",
    ],
    hooksconfig={
        "gi": {
            "icons": ["Adwaita"],
            "themes": ["Adwaita"],
            "languages": ["pl", "en_US"],
            "module-versions": {"Gtk": "3.0", "WebKit2": "4.1"},
        }
    }
    if linux
    else {},
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="prismaflow" if linux else "PrismaFlow",
    icon=str(icon),
    console=False,
    strip=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="PrismaFlow")
