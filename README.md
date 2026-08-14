# 🚀 Telegram FDM Proxy

High-speed, multi-threaded HTTP streaming proxy that bridges **Telegram** media downloads with download managers like **Free Download Manager (FDM)**, **aria2**, and **NeatDM** on **Linux (Arch, Ubuntu, Fedora)** and **Windows (10 / 11)**.

---

## 📂 Repository Structure

```
tg_fdm_proxy/
├── 📄 Core Logic & UI
│   ├── tg_fdm_proxy.py           # Main daemon, proxy server & Telegram bot
│   └── settings_gui.py           # Dark-mode desktop configuration GUI
│
├── 🐧 Linux Packaging & Service
│   └── linux/
│       ├── install.sh            # User installer (venv, icons, .desktop, systemd)
│       ├── uninstall.sh          # User uninstaller
│       ├── PKGBUILD              # Arch Linux native package script
│       ├── build_linux.sh        # PyInstaller standalone Linux binary builder
│       └── tg_fdm_proxy_linux.spec # Linux PyInstaller spec
│
├── 🪟 Windows Packaging & Startup
│   └── windows/
│       ├── build_windows.bat     # 1-click Windows EXE builder
│       ├── tg_fdm_proxy.spec     # Windows PyInstaller spec (with ICO icon & hidden imports)
│       ├── install_startup.py    # Portable Windows Startup VBS installer
│       └── watchdog.bat          # Windows auto-restart watchdog
│
├── 🎨 Assets & Desktops
│   └── assets/
│       ├── tg-fdm-proxy.png      # 256x256 High-res app icon
│       ├── tg-fdm-proxy.ico      # Windows multi-size ICO icon
│       ├── tg-fdm-proxy.svg      # Scalable vector icon
│       ├── tray_icon.png         # 24x24 Clean system tray icon
│       ├── tg-fdm-proxy.desktop  # XDG Desktop application launcher
│       ├── tg-fdm-proxy.service  # Systemd user service unit
│       └── render_tray_icons.py  # Icon generation & supersampling engine
│
├── 🐳 Containers & Docs
│   └── docker/
│       ├── Dockerfile
│       └── docker-compose.yml
│
└── ⚙️ Configuration & Environment
    ├── .env                      # Local configuration
    └── .gitignore                # Production ignore rules
```

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

## 📥 Installation & Setup

### 🐧 Linux (Arch / Debian / Ubuntu / Fedora)

```bash
# Clone repository
git clone https://github.com/Myselfnandha/telegram-fdm-proxy.git
cd telegram-fdm-proxy

# Run user installer
chmod +x linux/install.sh
./linux/install.sh
```

**Build Standalone Linux Binary:**
```bash
chmod +x linux/build_linux.sh
./linux/build_linux.sh
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
.\.venv\Scripts\pip install telethon aiohttp python-dotenv pystray pillow psutil cryptg

# Run proxy with system tray
.\.venv\Scripts\python tg_fdm_proxy.py start --tray
```

#### 2. Building Standalone Windows Executable (`tg-fdm-proxy.exe`)

Run the automated build script:
```bat
windows\build_windows.bat
```

#### 3. Autostart on Windows Boot (Silent Background Mode)

```powershell
python windows\install_startup.py
```

#### 4. Continuous Watchdog

```bat
windows\watchdog.bat
```

---

## 🚀 CLI Commands Reference

| Action | Linux Command | Windows Command |
| :--- | :--- | :--- |
| **Start with Tray** | `tg-fdm-proxy start --tray` | `python tg_fdm_proxy.py start --tray` |
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
