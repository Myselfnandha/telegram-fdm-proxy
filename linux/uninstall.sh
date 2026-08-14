#!/usr/bin/env bash
set -e

# ==============================================================================
# Telegram FDM Proxy - Arch Linux User Uninstaller
# ==============================================================================

BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/256x256/apps"
ICON_SVG_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"
SYSTEMD_DIR="${HOME}/.config/systemd/user"

echo "Stopping service if running..."
systemctl --user stop tg-fdm-proxy.service 2>/dev/null || true
systemctl --user disable tg-fdm-proxy.service 2>/dev/null || true

echo "Removing installed application files..."
rm -f "${BIN_DIR}/tg-fdm-proxy"
rm -f "${APP_DIR}/tg-fdm-proxy.desktop"
rm -f "${ICON_DIR}/tg-fdm-proxy.png"
rm -f "${ICON_SVG_DIR}/tg-fdm-proxy.svg"
rm -f "${SYSTEMD_DIR}/tg-fdm-proxy.service"

systemctl --user daemon-reload || true

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${APP_DIR}" 2>/dev/null || true
fi

echo "Uninstallation complete. Configuration files in ~/.config/tg-fdm-proxy were kept."
