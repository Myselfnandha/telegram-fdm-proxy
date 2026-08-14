# 🚀 Telegram FDM Proxy

High-speed, multi-threaded HTTP streaming proxy that bridges **Telegram** media downloads with download managers like **Free Download Manager (FDM)**, **aria2**, and **NeatDM** on **Linux (Arch, Ubuntu, Fedora)** and **Windows (10 / 11)**.

---

## ✨ Features

- **⚡ Blazing Fast Streaming**: Multi-range HTTP streaming chunk pipeline with maximum throughput using Telethon and `cryptg`.
- **🎯 Auto-Send Integration**: Automatically dispatches incoming Telegram files directly into Free Download Manager (Native & Flatpak), `aria2c`, or NeatDM.
- **🎨 Desktop Suite & System Tray**: Native AppIndicator (Linux) & Win32 Notification Area (Windows) tray icon with quick actions (Open Bot, Live Logs, Settings, Quit).
- **⚙️ Graphical Settings UI**: Dark-mode Tkinter configuration window to manage credentials, notifications, and filters with ease.
- **🔕 Smart Notification Debouncing**: Built-in rate limiting prevents notification spam during batch downloads.
- **📦 Packaging & Background Daemons**: 
  - **Linux**: Native `PKGBUILD`, systemd user unit (`tg-fdm-proxy.service`), and `.desktop` application launcher.
  - **Windows**: Standalone `.exe` packaging via PyInstaller, Windows Startup integration, and watchdog auto-restart script.
- **🛡️ Auto-Recovery & PID Lock**: Single-instance daemon protection with process recycling and resilient socket reconnection.

---

## 📥 Installation

### 🐧 Linux (Arch / Debian / Ubuntu / Fedora)

```bash
# Clone repository
git clone https://github.com/Myselfnandha/telegram-fdm-proxy.git
cd telegram-fdm-proxy

# Run user installer
chmod +x install.sh
./install.sh
```

**Build Standalone Linux Binary:**
```bash
chmod +x build_linux.sh
./build_linux.sh
```

---

### 🪟 Windows (10 / 11)

#### 1. Quick Run with Python

```powershell
# Clone repository
git clone https://github.com/Myselfnandha/telegram-fdm-proxy.git
cd telegram-fdm-proxy

# Setup virtual environment & dependencies
python -m venv .venv
.\.venv\Scripts\pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt  # Or install: telethon aiohttp python-dotenv pystray pillow psutil cryptg

# Run proxy with system tray
.\.venv\Scripts\python tg_fdm_proxy.py start --tray
```

#### 2. Building Standalone Windows Executable (`tg-fdm-proxy.exe`)

Run the automated build script:
```bat
build_windows.bat
```
Or run PyInstaller manually:
```powershell
pyinstaller --clean tg_fdm_proxy.spec
```
The compiled binary will be in `dist\tg-fdm-proxy.exe`.

#### 3. Autostart on Windows Boot (Silent Background Mode)

To run the proxy silently in the background whenever Windows starts:
```powershell
python install_startup.py
```
This creates a lightweight VBS startup entry in `AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup`.

#### 4. Continuous Watchdog (Auto-restart on crash)

```bat
watchdog.bat
```

---

## 🚀 CLI Commands Reference

| Action | Linux Command | Windows Command |
| :--- | :--- | :--- |
| **Start with Tray** | `tg-fdm-proxy start --tray` | `python tg_fdm_proxy.py start --tray` (or `tg-fdm-proxy.exe start --tray`) |
| **Start as Daemon** | `tg-fdm-proxy start --daemon` | `python tg_fdm_proxy.py start --daemon` |
| **Check Status** | `tg-fdm-proxy status` | `python tg_fdm_proxy.py status` |
| **Settings GUI** | `tg-fdm-proxy config` | `python tg_fdm_proxy.py config` |
| **View Live Logs** | `tg-fdm-proxy logs -f` | `python tg_fdm_proxy.py logs -f` |
| **Stop Proxy** | `tg-fdm-proxy stop` | `python tg_fdm_proxy.py stop` |

---

## ⚙️ Configuration (`.env`)

You can configure settings via the **Settings GUI** (`tg-fdm-proxy config` or right-click tray icon) or edit `.env` directly:

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
