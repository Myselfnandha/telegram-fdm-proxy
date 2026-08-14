# 🚀 Telegram FDM Proxy

High-speed, multi-threaded HTTP streaming proxy that bridges **Telegram** media downloads with download managers like **Free Download Manager (FDM)**, **aria2**, and **NeatDM** on **Linux (Arch, Ubuntu, Fedora)** and **Windows**.

---

## ✨ Features

- **⚡ Blazing Fast Streaming**: Multi-range HTTP streaming chunk pipeline with maximum throughput using Telethon and `cryptg`.
- **🎯 Auto-Send Integration**: Automatically dispatches incoming Telegram files directly into Free Download Manager (Native & Flatpak), `aria2c`, or NeatDM.
- **🎨 Desktop Suite & System Tray**: Native AppIndicator DBus tray icon with quick actions (Open Bot, Live Logs, Settings, Quit).
- **⚙️ Graphical Settings UI**: Dark-mode Tkinter configuration window to manage credentials, notifications, and filters with ease.
- **🔕 Smart Notification Debouncing**: Built-in rate limiting prevents notification spam during batch downloads.
- **📦 Arch Linux Packaging**: Native `PKGBUILD`, systemd user unit (`tg-fdm-proxy.service`), and `.desktop` application launcher.
- **🛡️ Auto-Recovery & PID Lock**: Single-instance daemon protection with process recycling and resilient socket reconnection.

---

## 📥 Installation

### Arch Linux / General Linux

```bash
# Clone repository
git clone https://github.com/Myselfnandha/telegram-fdm-proxy.git
cd telegram-fdm-proxy

# Run user installer
chmod +x install.sh
./install.sh
```

### Building Standalone Linux Binary

```bash
chmod +x build_linux.sh
./build_linux.sh
```

---

## 🚀 Usage

### Command Line Interface (CLI)

```bash
tg-fdm-proxy start --tray       # Start with System Tray integration
tg-fdm-proxy start --daemon     # Start in headless background mode
tg-fdm-proxy status             # Check service status & detected download managers
tg-fdm-proxy config             # Open graphical settings window
tg-fdm-proxy logs -f            # Follow live streaming logs
tg-fdm-proxy stop               # Cleanly shut down proxy
```

### Systemd User Service

```bash
systemctl --user enable --now tg-fdm-proxy   # Enable on startup
systemctl --user status tg-fdm-proxy         # Check service status
```

---

## ⚙️ Configuration (`.env`)

You can configure settings via the **Settings GUI** (`tg-fdm-proxy config`) or edit `.env` directly:

```ini
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token

PROXY_HOST=127.0.0.1
PROXY_PORT=8080
MIN_FILE_SIZE_MB=50
QUALITY_WAIT_SECS=30

ALLOWED_EXT=.mkv,.mp4,.avi,.mov,.flv,.wmv,.zip,.rar,.tar,.gz,.7z,.iso
KEYWORD_BLOCK=sample,trailer,cam,ts,telesync,PRE-DVD
KEYWORD_ALLOW=

ENABLE_NOTIFICATIONS=true
NOTIFICATION_MODE=downloads_only
PREFERRED_MANAGER=Auto-Detect (FDM → aria2 → NeatDM)
```

---

## 📄 License
MIT License
