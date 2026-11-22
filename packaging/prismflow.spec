from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH).parent
dist = root / "frontend" / "dist"
if not (dist / "index.html").is_file():
    raise SystemExit("frontend/dist is missing: run `npm run build` in frontend/ first")

hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("webview.platforms")
    + ["trendspy", "networkx", "gi", "gi.repository.Gtk", "gi.repository.WebKit2"]
)

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    datas=[(str(dist), "frontend/dist"), *collect_data_files("webview")],
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
    },
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="prismflow",
    console=False,
    strip=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="PrismFlow")
