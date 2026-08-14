#!/usr/bin/env bash
set -e

# ==============================================================================
# Build Standalone Linux Executable for tg-fdm-proxy
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${SCRIPT_DIR}"

echo "======================================================"
echo " Building Standalone Linux Binary with PyInstaller"
echo "======================================================"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

echo "Ensuring build dependencies..."
./.venv/bin/pip install --quiet pyinstaller pillow pystray telethon aiohttp python-dotenv psutil cryptg

mkdir -p build dist
echo "Compiling Linux standalone binary (ELF x86_64)..."
./.venv/bin/pyinstaller --clean linux/tg_fdm_proxy_linux.spec

if [ -f "dist/tg-fdm-proxy" ]; then
    chmod +x dist/tg-fdm-proxy
    echo ""
    echo "======================================================"
    echo " ✅ Build Successful!"
    echo " Standalone executable: ${SCRIPT_DIR}/dist/tg-fdm-proxy"
    echo " Size: $(du -h dist/tg-fdm-proxy | cut -f1)"
    echo "======================================================"
else
    echo "❌ Build failed - executable not found in dist/"
    exit 1
fi
