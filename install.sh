#!/bin/sh
set -eu

REPO="praha6248/PrismaFlow"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/PrismaFlow-app"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"

say() { printf '%s\n' "$*"; }
fail() { say "PrismaFlow: $*" >&2; exit 1; }

[ "$(uname -s)" = "Linux" ] || fail "this installer is for Linux. On Windows run: irm https://raw.githubusercontent.com/$REPO/main/install.ps1 | iex"
[ "$(uname -m)" = "x86_64" ] || fail "only x86_64 builds are published"
command -v curl >/dev/null || fail "curl is required"
command -v tar >/dev/null || fail "tar is required"

say "Looking up the latest release..."
URL=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" | grep -o '"browser_download_url": *"[^"]*linux-x86_64\.tar\.gz"' | head -n 1 | sed 's/.*"\(https[^"]*\)"/\1/')
[ -n "$URL" ] || fail "no Linux build found in the latest release"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
say "Downloading $URL"
curl -fL --progress-bar "$URL" -o "$TMP/prismaflow.tar.gz"
tar -xzf "$TMP/prismaflow.tar.gz" -C "$TMP"

rm -rf "$APP_DIR"
mkdir -p "$(dirname "$APP_DIR")" "$BIN_DIR" "$DESKTOP_DIR" "$ICON_DIR"
mv "$TMP/PrismaFlow" "$APP_DIR"
ln -sf "$APP_DIR/prismaflow" "$BIN_DIR/prismaflow"

curl -fsSL "https://raw.githubusercontent.com/$REPO/main/packaging/prismaflow.png" -o "$ICON_DIR/prismaflow.png" || true
cat > "$DESKTOP_DIR/prismaflow.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=PrismaFlow
Comment=Local-first product discovery studio
Exec=$APP_DIR/prismaflow
Icon=prismaflow
Categories=Office;Development;
Terminal=false
StartupWMClass=prismaflow
DESKTOP

say ""
say "PrismaFlow installed. Start it from the app menu or run: prismaflow"

if ! dpkg -s gir1.2-webkit2-4.1 >/dev/null 2>&1 && command -v apt-get >/dev/null; then
  say ""
  say "The window needs WebKit2GTK. If it does not open, run:"
  say "  sudo apt install gir1.2-webkit2-4.1 python3-gi"
fi

MEM_GB=$(awk '/MemTotal/ {printf "%d", $2 / 1048576}' /proc/meminfo 2>/dev/null || echo 0)
if [ "$MEM_GB" -ge 15 ]; then MODEL="gemma3:12b"; else MODEL="gemma3:4b"; fi

say ""
say "Local models (PrismaFlow shows the same steps on first launch):"
if command -v ollama >/dev/null; then
  say "  Ollama: installed"
else
  say "  1. Install Ollama:   curl -fsSL https://ollama.com/install.sh | sh"
fi
say "  2. Main model:       ollama pull $MODEL"
say "  3. Optional search:  ollama pull bge-m3"
say "  More: https://github.com/$REPO/releases/latest"
