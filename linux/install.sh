#!/usr/bin/env bash
set -e

# ==============================================================================
# Telegram FDM Proxy - Arch Linux / Desktop User Installer
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/256x256/apps"
ICON_SVG_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"
SYSTEMD_DIR="${HOME}/.config/systemd/user"
CONFIG_DIR="${HOME}/.config/tg-fdm-proxy"

echo "======================================================"
echo " Installing Telegram FDM Proxy on Arch Linux"
echo "======================================================"

# 1. Ensure directory structures
mkdir -p "${BIN_DIR}" "${APP_DIR}" "${ICON_DIR}" "${ICON_SVG_DIR}" "${SYSTEMD_DIR}" "${CONFIG_DIR}"

# 2. Virtual Environment Setup (with system site packages for native AppIndicator / GTK)
if [ ! -d "${SCRIPT_DIR}/.venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv --system-site-packages "${SCRIPT_DIR}/.venv"
fi

echo "Installing required Python dependencies..."
"${SCRIPT_DIR}/.venv/bin/pip" install --quiet --upgrade pip
"${SCRIPT_DIR}/.venv/bin/pip" install --quiet telethon aiohttp python-dotenv pystray pillow psutil cryptg

# 3. Copy configuration template if .env doesn't exist
if [ -f "${SCRIPT_DIR}/.env" ] && [ ! -f "${CONFIG_DIR}/.env" ]; then
    echo "Copying existing .env to ${CONFIG_DIR}/.env..."
    cp "${SCRIPT_DIR}/.env" "${CONFIG_DIR}/.env"
fi

# 4. Generate/Install application wrapper script
echo "Installing executable launcher to ${BIN_DIR}/tg-fdm-proxy..."
cat << EOF > "${BIN_DIR}/tg-fdm-proxy"
#!/usr/bin/env bash
EXEC_DIR="${SCRIPT_DIR}"
exec "\${EXEC_DIR}/.venv/bin/python" "\${EXEC_DIR}/tg_fdm_proxy.py" "\$@"
EOF
chmod +x "${BIN_DIR}/tg-fdm-proxy"

# 5. Install Desktop Icons
echo "Installing application icons..."
if [ -f "${SCRIPT_DIR}/assets/tg-fdm-proxy.png" ]; then
    cp "${SCRIPT_DIR}/assets/tg-fdm-proxy.png" "${ICON_DIR}/tg-fdm-proxy.png"
fi
if [ -f "${SCRIPT_DIR}/assets/tg-fdm-proxy.svg" ]; then
    cp "${SCRIPT_DIR}/assets/tg-fdm-proxy.svg" "${ICON_SVG_DIR}/tg-fdm-proxy.svg"
fi

# 6. Install Desktop Entry (.desktop)
echo "Installing desktop launcher to ${APP_DIR}/tg-fdm-proxy.desktop..."
cat << EOF > "${APP_DIR}/tg-fdm-proxy.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=Telegram FDM Proxy
GenericName=Telegram Download Proxy
Comment=High-speed Telegram media stream proxy for Free Download Manager and aria2
Exec=${BIN_DIR}/tg-fdm-proxy start --tray
Icon=tg-fdm-proxy
Terminal=false
Categories=Network;FileTransfer;Utility;
Keywords=telegram;fdm;download;proxy;aria2;media;streaming;
StartupNotify=true
Actions=Tray;Daemon;Logs;Stop;Config;

[Desktop Action Tray]
Name=Start with System Tray
Exec=${BIN_DIR}/tg-fdm-proxy start --tray

[Desktop Action Daemon]
Name=Start in Background (Service)
Exec=${BIN_DIR}/tg-fdm-proxy start --daemon

[Desktop Action Logs]
Name=View Live Logs
Exec=${BIN_DIR}/tg-fdm-proxy logs -f

[Desktop Action Config]
Name=Edit Settings (.env)
Exec=${BIN_DIR}/tg-fdm-proxy config

[Desktop Action Stop]
Name=Stop Proxy
Exec=${BIN_DIR}/tg-fdm-proxy stop
EOF
chmod +x "${APP_DIR}/tg-fdm-proxy.desktop"

# 7. Install Systemd User Service Unit
echo "Installing systemd user service unit to ${SYSTEMD_DIR}/tg-fdm-proxy.service..."
cat << EOF > "${SYSTEMD_DIR}/tg-fdm-proxy.service"
[Unit]
Description=Telegram FDM Proxy Bot Service
After=network.target network-online.target graphical-session.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${BIN_DIR}/tg-fdm-proxy start --tray
Restart=always
RestartSec=5
TimeoutStopSec=10
KillMode=process
Environment=PYTHONUNBUFFERED=1
PassEnvironment=DISPLAY WAYLAND_DISPLAY XAUTHORITY DBUS_SESSION_BUS_ADDRESS

[Install]
WantedBy=default.target
EOF

# Reload user daemon
systemctl --user daemon-reload || true

# Update desktop & icon caches
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${APP_DIR}" 2>/dev/null || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "${HOME}/.local/share/icons/hicolor" 2>/dev/null || true
fi

echo ""
echo "======================================================"
echo " ✅ Installation Complete!"
echo "======================================================"
echo "Make sure ${BIN_DIR} is in your PATH."
echo ""
echo "Manage Telegram FDM Proxy:"
echo "  • CLI Commands      : tg-fdm-proxy status | start | stop | logs | config"
echo "  • Systemd Enable    : systemctl --user enable --now tg-fdm-proxy"
echo "  • Systemd Status    : systemctl --user status tg-fdm-proxy"
echo "  • Systemd Logs      : journalctl --user -u tg-fdm-proxy -f"
echo "  • Desktop Launcher  : Search for 'Telegram FDM Proxy' in your App Menu"
echo "======================================================"
