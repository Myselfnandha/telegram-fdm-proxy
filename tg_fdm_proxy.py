#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram FDM Proxy for Linux (Arch) and Windows
High-speed HTTP streaming proxy for Telegram media downloads with Free Download Manager,
aria2, NeatDM, and native desktop/systemd integration.
"""

import os
import re
import io
import sys
import time
import socket
import logging
import logging.handlers
import subprocess
import threading
import argparse
import atexit
import signal
import asyncio
import email.utils
from typing import Optional, Tuple, Set, Dict, List

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Force UTF-8 output
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ────────────────────────────────────────────────────────
#  Application Paths (XDG / Portable support)
# ────────────────────────────────────────────────────────
def get_app_dir() -> str:
    """Returns directory for storing configuration, session, logs, and PID files."""
    # 1. If local .env exists in current working directory, use current directory (Dev / Portable mode)
    if os.path.isfile(os.path.join(os.getcwd(), ".env")):
        return os.getcwd()
    
    # 2. Check if running from script dir containing .env
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.isfile(os.path.join(script_dir, ".env")):
        return script_dir

    # 3. Standard Linux XDG Config directory (~/.config/tg-fdm-proxy)
    if sys.platform != "win32":
        xdg_config = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        app_dir = os.path.join(xdg_config, "tg-fdm-proxy")
    else:
        app_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "tg-fdm-proxy")

    os.makedirs(app_dir, exist_ok=True)
    return app_dir

APP_DIR = get_app_dir()
ENV_FILE = os.path.join(APP_DIR, ".env")
LOG_FILE = os.path.join(APP_DIR, "tg_fdm_proxy.log")
PID_FILE = os.path.join(APP_DIR, "tg_fdm_proxy.pid")
SESSION_NAME = os.path.join(APP_DIR, "fdm_proxy_bot_session")

# ────────────────────────────────────────────────────────
#  Desktop Notification Helper
# ────────────────────────────────────────────────────────
def find_app_icon() -> Optional[str]:
    """Find the best matching application icon on the system."""
    candidates = [
        os.path.join(APP_DIR, "assets", "tg-fdm-proxy.png"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "tg-fdm-proxy.png"),
        os.path.expanduser("~/.local/share/icons/hicolor/256x256/apps/tg-fdm-proxy.png"),
        "/usr/share/icons/hicolor/256x256/apps/tg-fdm-proxy.png",
        "/usr/share/pixmaps/tg-fdm-proxy.png",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None

_last_notif_time: Dict[str, float] = {}
NOTIFICATION_DEBOUNCE_SECS = 8.0

def send_desktop_notification(
    title: str,
    message: str,
    urgency: str = "normal",
    category: str = "general",
    dedup_key: Optional[str] = None
) -> None:
    """Send native desktop notification on Linux with rate limiting, debouncing, and settings check."""
    if sys.platform == "win32":
        return

    # Check notification settings from environment / config
    enable_notifs = os.getenv("ENABLE_NOTIFICATIONS", "true").strip().lower() in ("true", "1", "yes", "on")
    if not enable_notifs:
        return

    notif_mode = os.getenv("NOTIFICATION_MODE", "downloads_only").strip().lower()
    if notif_mode == "none":
        return
    if notif_mode == "downloads_only" and category not in ("download", "batch"):
        return

    # Deduplication & throttling per unique key
    now = time.monotonic()
    key = dedup_key or f"{title}:{message}"
    if key in _last_notif_time:
        if now - _last_notif_time[key] < NOTIFICATION_DEBOUNCE_SECS:
            return  # Suppress duplicate storm

    _last_notif_time[key] = now

    # Clean stale keys
    if len(_last_notif_time) > 100:
        stale = [k for k, t in _last_notif_time.items() if now - t > 60]
        for k in stale:
            del _last_notif_time[k]

    import shutil
    if not shutil.which("notify-send"):
        return

    icon = find_app_icon()
    cmd = ["notify-send", "-a", "Telegram FDM Proxy", "-u", urgency]
    if icon:
        cmd.extend(["-i", icon])
    cmd.extend([title, message])

    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

# ────────────────────────────────────────────────────────
#  PID Lock & Single Instance Management
# ────────────────────────────────────────────────────────
def get_running_pid() -> Optional[int]:
    """Returns PID of active tg-fdm-proxy process, or None."""
    if not os.path.isfile(PID_FILE):
        return None
    try:
        with open(PID_FILE, "r", encoding="utf-8") as f:
            pid = int(f.read().strip())
        
        # Check if process is alive
        if sys.platform != "win32":
            os.kill(pid, 0)
            return pid
        else:
            import psutil
            if psutil.pid_exists(pid):
                return pid
    except (ValueError, OSError, ProcessLookupError):
        pass
    except Exception:
        pass
    return None

def acquire_pid_lock() -> Tuple[bool, int]:
    """Acquire single-instance PID lock. Returns (acquired, active_pid)."""
    running_pid = get_running_pid()
    if running_pid and running_pid != os.getpid():
        return False, running_pid
    
    try:
        with open(PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        atexit.register(release_pid_lock)
        return True, os.getpid()
    except Exception as e:
        print(f"Warning: Could not write PID file: {e}")
        return True, os.getpid()

def release_pid_lock() -> None:
    """Release single-instance PID lock."""
    try:
        if os.path.isfile(PID_FILE):
            with open(PID_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content == str(os.getpid()):
                os.remove(PID_FILE)
    except Exception:
        pass

# ────────────────────────────────────────────────────────
#  Logging Configuration
# ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.handlers.RotatingFileHandler(
            LOG_FILE,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        ),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("tg_fdm_proxy")
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
logging.getLogger("telethon").setLevel(logging.ERROR)

# ────────────────────────────────────────────────────────
#  Environment & Credentials Setup
# ────────────────────────────────────────────────────────
from dotenv import load_dotenv

def ensure_env() -> Tuple[str, str, str]:
    """Check .env for credentials; prompt interactively or raise error."""
    load_dotenv(ENV_FILE)
    
    api_id = os.getenv("API_ID", "").strip()
    api_hash = os.getenv("API_HASH", "").strip()
    bot_token = os.getenv("BOT_TOKEN", "").strip()

    if not all([api_id, api_hash, bot_token]):
        if not (sys.stdin and sys.stdin.isatty()):
            logger.error(f"Missing API credentials in {ENV_FILE}. Please configure .env first.")
            sys.exit(1)

        print("\n" + "=" * 55)
        print("  TELEGRAM FDM PROXY - FIRST-TIME CONFIGURATION")
        print("=" * 55)
        print(f"Config path: {ENV_FILE}")
        print("Get credentials from https://my.telegram.org and @BotFather\n")
        try:
            if not api_id:
                api_id = input("1. Enter your API_ID   : ").strip()
            if not api_hash:
                api_hash = input("2. Enter your API_HASH : ").strip()
            if not bot_token:
                bot_token = input("3. Enter your BOT_TOKEN: ").strip()

            with open(ENV_FILE, "w", encoding="utf-8") as f:
                f.write(f"API_ID={api_id}\n")
                f.write(f"API_HASH={api_hash}\n")
                f.write(f"BOT_TOKEN={bot_token}\n")
                f.write("PROXY_HOST=127.0.0.1\n")
                f.write("PROXY_PORT=8080\n")
                f.write("MIN_FILE_SIZE_MB=50\n")
                f.write("QUALITY_WAIT_SECS=30\n")

            print(f"\nConfiguration successfully saved to: {ENV_FILE}")
            load_dotenv(ENV_FILE)
        except KeyboardInterrupt:
            print("\nSetup cancelled.")
            sys.exit(1)

    return api_id, api_hash, bot_token

# ────────────────────────────────────────────────────────
#  Imports requiring third-party libraries
# ────────────────────────────────────────────────────────
from aiohttp import web
from telethon import TelegramClient, events, Button, utils
from telethon.network import MTProtoSender
from telethon.tl.alltlobjects import LAYER
from telethon.tl.functions import InvokeWithLayerRequest
from telethon.tl.functions.bots import SetBotCommandsRequest
from telethon.tl.functions.auth import ExportAuthorizationRequest, ImportAuthorizationRequest
from telethon.tl.functions.upload import GetFileRequest
from telethon.tl.types import BotCommand, BotCommandScopeDefault
from telethon.errors import FloodWaitError

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

# ────────────────────────────────────────────────────────
#  Download Manager Detection & Launchers
# ────────────────────────────────────────────────────────
MANAGER_LABELS = {
    "fdm": "🚀 FDM",
    "aria2": "⚡ aria2c",
    "persepolis": "🌊 Persepolis",
    "kget": "📥 KGet",
    "neat": "💧 Neat DM",
    "idm": "⚡ IDM",
    "direct": "📋 Copy Link",
}

MANAGER_EXE_NAMES = {
    "fdm": "fdm.exe",
    "idm": "IDMan.exe",
    "neat": "NeatDM.exe",
}

MANAGER_COMMANDS = {
    "fdm": ["{exe}", "-a", "{url}"],
    "idm": ["{exe}", "/d", "{url}", "/n", "/q"],
    "neat": ["{exe}", "{url}"],
    "persepolis": ["persepolis", "--link", "{url}"],
    "kget": ["kget", "--showForeground", "{url}"],
}

USERNAME = os.getenv("USERNAME", os.getenv("USER", ""))
_FALLBACK_PATHS = {
    "fdm": [
        r"C:\Program Files\Softdeluxe\Free Download Manager\fdm.exe",
        r"C:\Program Files\FreeDownloadManager\fdm.exe",
        r"C:\Program Files (x86)\FreeDownloadManager\fdm.exe",
        r"C:\Program Files (x86)\Softdeluxe\Free Download Manager\fdm.exe",
        rf"C:\Users\{USERNAME}\AppData\Local\Programs\FreeDownloadManager\fdm.exe",
    ],
    "idm": [
        r"C:\Program Files (x86)\Internet Download Manager\IDMan.exe",
        r"C:\Program Files\Internet Download Manager\IDMan.exe",
    ],
    "neat": [
        rf"C:\Users\{USERNAME}\AppData\Local\Neat Download Manager\NeatDM.exe",
        r"C:\Program Files\Neat Download Manager\NeatDM.exe",
        r"C:\Program Files (x86)\Neat Download Manager\NeatDM.exe",
    ],
}

def detect_managers() -> Dict[str, str]:
    """Dynamically scan for all supported download managers on Linux and Windows."""
    import shutil
    found: Dict[str, str] = {}

    if sys.platform != "win32":
        # 1. Check FDM via Flatpak
        try:
            res = subprocess.run(
                ["flatpak", "info", "org.freedownloadmanager.Manager"],
                capture_output=True, text=True, timeout=2
            )
            if res.returncode == 0:
                found["fdm"] = "flatpak"
                logger.info("[OK] Found FDM via Flatpak (org.freedownloadmanager.Manager)")
        except Exception:
            pass

        # 2. Check native binaries on PATH
        linux_bins = {
            "fdm": ["freedownloadmanager", "fdm", "/opt/freedownloadmanager/fdm"],
            "aria2": ["aria2c"],
            "persepolis": ["persepolis"],
            "kget": ["kget"],
            "neat": ["neatdm", "neatdm.exe"],
        }
        for mgr_id, bins in linux_bins.items():
            if mgr_id in found:
                continue
            for b in bins:
                path = shutil.which(b) or (b if os.path.isfile(b) and os.access(b, os.X_OK) else None)
                if path:
                    found[mgr_id] = path
                    logger.info(f"[OK] Found {mgr_id.upper()} at: {path}")
                    break
    else:
        for mgr_id in ("fdm", "idm", "neat"):
            exe_name = MANAGER_EXE_NAMES[mgr_id]
            path = shutil.which(exe_name)
            if path:
                found[mgr_id] = path
                logger.info(f"[OK] Found {mgr_id.upper()} via PATH: {path}")
                continue

            for fb in _FALLBACK_PATHS.get(mgr_id, []):
                if os.path.isfile(fb):
                    found[mgr_id] = fb
                    logger.info(f"[OK] Found {mgr_id.upper()} via fallback: {fb}")
                    break

    if not found:
        logger.warning("[!!] No external download manager detected. Links will provide direct stream URLs.")
    return found

INSTALLED_MANAGERS: Dict[str, str] = {}

def is_manager_running(manager_id: str) -> bool:
    """Returns True if the download manager application is actively running."""
    if sys.platform != "win32":
        try:
            import psutil
            patterns = {
                "fdm": ["freedownloadmanager", "fdm", "org.freedownloadmanager.manager"],
                "aria2": ["aria2c"],
                "persepolis": ["persepolis"],
                "kget": ["kget"],
                "neat": ["neatdm"],
            }
            target_patterns = patterns.get(manager_id, [manager_id])
            for proc in psutil.process_iter(['name', 'cmdline']):
                try:
                    name = (proc.info['name'] or "").lower()
                    cmdline = " ".join(proc.info['cmdline'] or []).lower()
                    for pat in target_patterns:
                        if pat in name or pat in cmdline:
                            return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except ImportError:
            try:
                res = subprocess.run(["pgrep", "-f", manager_id], capture_output=True, text=True)
                return res.returncode == 0
            except Exception:
                pass
        return False
    else:
        proc_name = MANAGER_EXE_NAMES.get(manager_id, "")
        if not proc_name:
            return False
        try:
            res = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {proc_name}", "/NH"],
                capture_output=True, text=True, timeout=3
            )
            return proc_name.lower() in res.stdout.lower()
        except Exception:
            return False

async def ensure_manager_running(manager_id: str) -> bool:
    """Launch manager if installed but not running."""
    if manager_id in ("aria2", "direct"):
        return True  # CLI tools do not need pre-running UI

    exe = INSTALLED_MANAGERS.get(manager_id)
    if not exe or is_manager_running(manager_id):
        return True

    cmd = ["flatpak", "run", "org.freedownloadmanager.Manager"] if (sys.platform != "win32" and exe == "flatpak") else [exe]
    logger.info(f"[{manager_id.upper()}] Launching manager: {cmd}")
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        logger.error(f"[{manager_id.upper()}] Failed to launch: {e}")
        return False

    for _ in range(8):
        await asyncio.sleep(0.5)
        if is_manager_running(manager_id):
            return True
    return False

async def trigger_manager(manager_id: str, url: str) -> bool:
    """Dispatch download URL to the target download manager."""
    exe = INSTALLED_MANAGERS.get(manager_id)
    if not exe:
        return False

    await ensure_manager_running(manager_id)

    if sys.platform != "win32":
        if manager_id == "fdm" and exe == "flatpak":
            cmd = ["flatpak", "run", "org.freedownloadmanager.Manager", "-a", url]
        elif manager_id == "aria2":
            downloads_dir = os.path.expanduser("~/Downloads")
            cmd = ["aria2c", "-s", "16", "-x", "16", "-k", "1M", "--dir", downloads_dir, url]
            # Launch aria2 in detached subprocess
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                logger.info(f"[ARIA2] Started background download: {url}")
                return True
            except Exception as e:
                logger.error(f"[ARIA2] Launch failed: {e}")
                return False
        else:
            cmd_template = MANAGER_COMMANDS.get(manager_id, ["{exe}", "{url}"])
            cmd = [part.format(exe=exe, url=url) for part in cmd_template]
    else:
        cmd_template = MANAGER_COMMANDS.get(manager_id, ["{exe}", "{url}"])
        cmd = [part.format(exe=exe, url=url) for part in cmd_template]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.communicate()
        logger.info(f"[{manager_id.upper()}] Triggered download: {url}")
        return True
    except Exception as e:
        logger.error(f"[{manager_id.upper()}] Failed to trigger: {e}")
        return False

async def auto_send(url: str) -> Tuple[str, bool]:
    """Try installed managers in priority order, checking PREFERRED_MANAGER first."""
    pref = os.getenv("PREFERRED_MANAGER", "").strip().lower()
    if pref and pref in INSTALLED_MANAGERS:
        ok = await trigger_manager(pref, url)
        if ok:
            return pref, True

    for mgr in ("fdm", "aria2", "persepolis", "kget", "idm", "neat"):
        if mgr in INSTALLED_MANAGERS:
            ok = await trigger_manager(mgr, url)
            if ok:
                return mgr, True
    return "direct", False

# ────────────────────────────────────────────────────────
#  Filename Cleaning & Formatting
# ────────────────────────────────────────────────────────
_NOISE_RE = re.compile(
    r"[\._\-\s]+("
    r"hdrip|bdrip|bluray|blu-ray|webrip|web-dl|web|hdtv|dvdrip|hq"
    r"|x264|x265|hevc|avc|xvid|divx"
    r"|aac|ac3|eac3|dd\d|dts|atmos|mp3"
    r"|esub|subs?|sub"
    r"|multi|dual|hindi|tamil|telugu|english|dubbed"
    r"|\@[\w]+"
    r")(?=[\._\-\s]|$)",
    re.IGNORECASE,
)
_RES_RE = re.compile(r"(2160p?|4k|uhd|1080p?|720p?|480p?|360p?)", re.IGNORECASE)
_YEAR_RE = re.compile(r"(?<![\d])(19\d{2}|20[0-2]\d)(?![\d])")

def auto_rename(raw: str) -> str:
    """Format raw filename as 'Title (Year) [Resolution].ext'."""
    ext = os.path.splitext(raw)[1]
    stem = os.path.splitext(raw)[0]

    res_m = _RES_RE.search(stem)
    year_m = _YEAR_RE.search(stem)
    res = res_m.group(1).upper() if res_m else ""
    year = year_m.group(1) if year_m else ""

    title = _NOISE_RE.sub(" ", stem)
    if res_m:
        title = title[:res_m.start()] + title[res_m.end():]
    if year_m:
        title = title[:year_m.start()] + title[year_m.end():]
    title = re.sub(r"[\._\-]+", " ", title).strip()
    title = re.sub(r"\s{2,}", " ", title)

    if not title:
        return raw

    parts = [title]
    if year:
        parts.append(f"({year})")
    if res:
        parts.append(f"[{res}]")
    return " ".join(parts) + ext

def find_free_port(start: int = 8080, max_attempts: int = 100) -> int:
    """Find an available TCP port starting from `start`."""
    for port in range(start, start + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free ports found between {start} and {start + max_attempts - 1}")

# ────────────────────────────────────────────────────────
#  Duplicate & Keyword Filters
# ────────────────────────────────────────────────────────
_triggered: Dict[Tuple[int, int], float] = {}
TRIGGER_TTL_SECS = 3600

def _is_duplicate(chat_id: int, message_id: int) -> bool:
    key = (chat_id, message_id)
    now = time.monotonic()
    stale = [k for k, t in _triggered.items() if now - t > TRIGGER_TTL_SECS]
    for k in stale:
        del _triggered[k]
    if key in _triggered:
        return True
    _triggered[key] = now
    return False

# ────────────────────────────────────────────────────────
#  Globals & Bot Initialization
# ────────────────────────────────────────────────────────
client: Optional[TelegramClient] = None
batch_active = False
batch_links: List[str] = []
download_registry: Dict[Tuple[int, int], dict] = {}
dc_auth_keys: Dict[int, any] = {}
dc_locks: Dict[int, asyncio.Lock] = {}
ACTIVE_CHANNELS: Set = set()
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8080
MIN_FILE_SIZE_MB = 50.0
QUALITY_WAIT_SECS = 30
ALLOWED_EXT: Set[str] = set()
KEYWORD_BLOCK: Set[str] = set()
KEYWORD_ALLOW: Set[str] = set()
_bot_username = ""

# Message cache for fast lookup and 404 prevention
_message_cache: Dict[Tuple[int, int], Any] = {}

# ────────────────────────────────────────────────────────
#  HTTP Range Request Proxy Handler (High-speed MTProto Stream)
# ────────────────────────────────────────────────────────
async def handle_download(request: web.Request) -> web.StreamResponse:
    chat_id = int(request.match_info["chat_id"])
    message_id = int(request.match_info["message_id"])
    response = None
    _down_start = time.monotonic()
    _bytes_written = 0

    try:
        # Check in-memory cache first to avoid Telegram API roundtrips / 404s
        message = _message_cache.get((chat_id, message_id))
        if not message:
            try:
                message = await client.get_messages(chat_id, ids=message_id)
            except Exception as fetch_err:
                logger.warning(f"Could not fetch message {message_id} in {chat_id}: {fetch_err}")

        if not message or not message.media or not hasattr(message, "file"):
            return web.Response(status=404, text="Message not found or does not contain media.")

        file_size = int(message.file.size)
        raw_name = message.file.name if message.file.name else f"tg_media_{message_id}.bin"
        raw_name = "".join([c for c in raw_name if (c.isalnum() or c in " .-_()")]).strip()
        file_name = auto_rename(raw_name)

        range_header = request.headers.get("Range", "")
        status = 200
        start = 0
        end = file_size - 1

        if range_header:
            match = re.search(r"bytes=(\d+)-(\d*)", range_header)
            if match:
                start = int(match.group(1))
                if match.group(2):
                    end = int(match.group(2))
            status = 206

        length = int(end - start + 1)
        last_modified_date = email.utils.formatdate(timeval=message.date.timestamp(), usegmt=True) if hasattr(message, 'date') and message.date else None

        headers = {
            "Content-Type": "application/octet-stream",
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(length),
            "ETag": f'"{chat_id}_{message_id}_{file_size}"',
        }
        if last_modified_date:
            headers["Last-Modified"] = last_modified_date

        response = web.StreamResponse(status=status, headers=headers)
        await response.prepare(request)

        # Stream chunks — 3-attempt retry for transient errors
        max_retries = 2
        for attempt in range(max_retries):
            try:
                async for chunk in client.iter_download(
                    message.media,
                    offset=start,
                    limit=length,
                    chunk_size=2 * 1024 * 1024,  # 2 MB — Telethon maximum for highest throughput
                ):
                    await response.write(chunk)
                    _bytes_written += len(chunk)
                break  # Success
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                raise  # client disconnected — let outer handler deal with it
            except Exception as chunk_e:
                if attempt == max_retries - 1:
                    raise chunk_e
                err = str(chunk_e).lower()
                # Auto-reconnect if Telethon lost its TCP link to Telegram
                if "disconnected" in err or "not connected" in err:
                    logger.warning(f"[RECONNECT] Telethon disconnected — attempting reconnect...")
                    try:
                        await client.connect()
                    except Exception as re_err:
                        logger.error(f"[RECONNECT] Failed: {re_err}")
                logger.warning(f"Download attempt {attempt + 1} failed: {chunk_e}, retrying...")
                await asyncio.sleep(1)

        _key = (chat_id, message_id)
        if _key in download_registry and not download_registry[_key].get("notified"):
            _info = download_registry.pop(_key)
            _info["notified"] = True
            _elapsed = time.monotonic() - _down_start
            _speed_mb = _bytes_written / max(_elapsed, 0.1) / (1024 * 1024)
            _size_gb = _info["size_bytes"] / (1024 ** 3)
            _mins, _secs = divmod(int(_elapsed), 60)
            _time_str = f"{_mins}m {_secs}s" if _mins else f"{_secs}s"

            async def _send_stats(_i=_info, _ts=_time_str, _sm=_speed_mb, _sg=_size_gb):
                try:
                    await client.send_message(
                        _i["reply_chat"],
                        f"📊 `{_i['fname']}` — {_sg:.2f} GB in {_ts} (~{_sm:.1f} MB/s)",
                        reply_to=_i["reply_to"],
                    )
                except Exception as _stat_err:
                    logger.warning(f"[STATS] Could not send speed stats: {_stat_err}")

            asyncio.create_task(_send_stats())

        return response

    except ConnectionResetError:
        return response
    except Exception as e:
        logger.error(f"Download error for chat {chat_id}, message {message_id}: {e}")
        return web.Response(status=500, text=f"Download failed: {str(e)}")

# ────────────────────────────────────────────────────────
#  Inline Button Builder
# ────────────────────────────────────────────────────────
def make_buttons(chat_id: int, message_id: int) -> list:
    row1, row2 = [], []
    for mgr in ("fdm", "aria2", "persepolis", "kget", "neat", "idm"):
        if mgr in INSTALLED_MANAGERS:
            label = MANAGER_LABELS.get(mgr, mgr.upper())
            if len(row1) < 2:
                row1.append(Button.inline(label, data=f"dl_{mgr}_{chat_id}_{message_id}"))
            else:
                row2.append(Button.inline(label, data=f"dl_{mgr}_{chat_id}_{message_id}"))

    row2.append(Button.inline(MANAGER_LABELS["direct"], data=f"dl_direct_{chat_id}_{message_id}"))

    buttons = []
    if row1:
        buttons.append(row1)
    if row2:
        buttons.append(row2)
    return buttons

# ────────────────────────────────────────────────────────
#  Quality-Selection Engine
# ────────────────────────────────────────────────────────
_RES_RANK = [
    ("2160p", 2160), ("4k", 2160), ("uhd", 2160),
    ("1080p", 1080), ("1080i", 1080),
    ("720p", 720), ("720i", 720),
    ("480p", 480), ("360p", 360), ("240p", 240),
]
_quality_buffer: Dict[Tuple, list] = {}
_quality_timers: Dict[Tuple, asyncio.Task] = {}

def _quality_score(fname: str, size: int) -> Tuple[int, int]:
    name = fname.lower()
    for keyword, rank in _RES_RANK:
        if keyword in name:
            return rank, size
    return 0, size

def _group_key(fname: str, media_group_id) -> str:
    if media_group_id:
        return f"album_{media_group_id}"
    base = fname.lower()
    base = re.sub(
        r"[\._\-\s]*("
        r"2160p?|4k|uhd|1080p?|720p?|480p?|360p?|240p?"
        r"|x264|x265|hevc|avc|hdrip|bluray|bdrip|webrip|web-dl|web|hq"
        r"|esub|aac|dd\d|dts|atmos|ac3|eac3"
        r"|multi|dual|hindi|tamil|telugu|english|dubbed"
        r"|\d{2,4}mb"
        r")",
        "", base, flags=re.IGNORECASE,
    )
    base = re.sub(r"[^a-z0-9]", "", base)[:35]
    return f"name_{base}" if base else "name_unknown"

async def _flush_quality_group(buf_key: tuple) -> None:
    candidates = _quality_buffer.pop(buf_key, [])
    _quality_timers.pop(buf_key, None)
    if not candidates:
        return

    best = max(candidates, key=lambda c: _quality_score(c["fname"], c["size"]))
    res_rank, _ = _quality_score(best["fname"], best["size"])
    res_label = f"{res_rank}p" if res_rank else "best size"

    chat_id = best["chat_id"]
    message_id = best["message_id"]
    link = f"http://{PROXY_HOST}:{PROXY_PORT}/dl/{chat_id}/{message_id}"
    fname = best["fname"]
    size_mb = best["size"] / (1024 * 1024)
    event = best["event"]
    
    _message_cache[(chat_id, message_id)] = event.message

    fname_lower = fname.lower()
    if KEYWORD_BLOCK and any(kw in fname_lower for kw in KEYWORD_BLOCK):
        logger.info(f"[FILTER-P] Blocked '{fname}' — keyword match")
        return
    if KEYWORD_ALLOW and not any(kw in fname_lower for kw in KEYWORD_ALLOW):
        logger.info(f"[FILTER-P] Skipped '{fname}' — no KEYWORD_ALLOW match")
        return
    if _is_duplicate(chat_id, message_id):
        return

    skipped = len(candidates) - 1
    logger.info(f"[QUALITY] Winner: '{fname}' ({res_label}, {size_mb:.0f} MB) from {skipped+1} variant(s)")

    mgr, pushed = await auto_send(link)
    label = MANAGER_LABELS.get(mgr, mgr)

    skip_note = f"\n└ _{skipped} lower-quality variant(s) skipped_" if skipped else ""
    if pushed:
        send_desktop_notification("Download Triggered", f"Sent '{fname}' to {label}", category="download", dedup_key=f"dl_{chat_id}_{message_id}")
        _sent = await event.reply(
            f"🏆 **Best Quality → {label}**\n"
            f"└ `{fname}`\n"
            f"└ {res_label} · {size_mb:.0f} MB"
            f"{skip_note}"
        )
        download_registry[(chat_id, message_id)] = {
            "start": time.monotonic(),
            "reply_chat": _sent.chat_id,
            "reply_to": _sent.id,
            "fname": fname,
            "size_bytes": best["size"],
            "notified": False,
        }
    else:
        await event.reply(
            f"📄 **Best Quality Ready**\n"
            f"└ `{fname}` · {res_label} · {size_mb:.0f} MB{skip_note}\n"
            f"`{link}`"
        )

async def _delayed_flush(buf_key: tuple) -> None:
    await asyncio.sleep(QUALITY_WAIT_SECS)
    await _flush_quality_group(buf_key)

async def _sniffer_handler(event):
    if event.chat_id not in ACTIVE_CHANNELS:
        return
    if not (event.message.media and event.message.file):
        return

    fname = event.message.file.name or "Unknown File"
    size = event.message.file.size
    size_mb = size / (1024 * 1024)

    if size_mb < MIN_FILE_SIZE_MB:
        return

    if ALLOWED_EXT:
        _ext = os.path.splitext(fname)[1].lower()
        if _ext not in ALLOWED_EXT:
            return

    gkey = _group_key(fname, getattr(event.message, "grouped_id", None))
    buf_key = (event.chat_id, gkey)

    _quality_buffer.setdefault(buf_key, []).append({
        "chat_id": event.chat_id,
        "message_id": event.id,
        "fname": fname,
        "size": size,
        "event": event,
    })

    existing = _quality_timers.get(buf_key)
    if existing and not existing.done():
        existing.cancel()

    res_rank, _ = _quality_score(fname, size)
    res_label = f"{res_rank}p" if res_rank else f"{size_mb:.0f} MB"
    logger.info(f"[QUALITY] Buffered: '{fname}' ({res_label}) — waiting {QUALITY_WAIT_SECS}s")
    _quality_timers[buf_key] = asyncio.ensure_future(_delayed_flush(buf_key))

# ────────────────────────────────────────────────────────
#  System Tray Implementation
# ────────────────────────────────────────────────────────
_tray_icon = None

def _create_tray_icon_image(size: int = 128, connected: bool = True) -> Image.Image:
    """Load high-res app icon or render a crisp, antialiased Telegram icon using 4x supersampling."""
    icon_path = find_app_icon()
    if icon_path and os.path.isfile(icon_path):
        try:
            with Image.open(icon_path) as img:
                return img.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
        except Exception:
            pass

    # 4x Supersampling for ultra-crisp edges
    scale = 4
    canvas_size = size * scale
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = 4 * scale
    bg_color = "#24A1DE" if connected else "#5A6578"  # Official Telegram Blue
    draw.ellipse([margin, margin, canvas_size - margin, canvas_size - margin], fill=bg_color)

    cx, cy = canvas_size / 2, canvas_size / 2
    r = (canvas_size - 2 * margin) / 2

    p_tail = (cx - 0.44 * r, cy + 0.08 * r)
    p_nose = (cx + 0.48 * r, cy - 0.06 * r)
    p_top  = (cx - 0.18 * r, cy - 0.46 * r)
    p_bottom = (cx + 0.02 * r, cy + 0.32 * r)
    p_mid  = (cx - 0.14 * r, cy + 0.10 * r)

    draw.polygon([p_tail, p_nose, p_top], fill="#FFFFFF")
    draw.polygon([p_nose, p_bottom, p_mid], fill="#B8E1F5" if connected else "#9AA6B8")
    draw.polygon([p_tail, p_nose, p_mid], fill="#E6F4FB" if connected else "#BAC4D2")

    return img.resize((size, size), Image.Resampling.LANCZOS)

def _start_tray_icon(port: int):
    global _tray_icon
    if not TRAY_AVAILABLE:
        logger.info("[TRAY] pystray not installed — continuing in background mode")
        return

    def _on_open_bot(icon, item):
        if _bot_username:
            url = f"https://t.me/{_bot_username}"
            if sys.platform != "win32":
                subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                os.system(f"start {url}")

    def _on_settings(icon, item):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        gui_script = os.path.join(script_dir, "settings_gui.py")
        if os.path.isfile(gui_script):
            subprocess.Popen([sys.executable, gui_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            _on_edit_config(icon, item)

    def _on_view_logs(icon, item):
        if sys.platform != "win32":
            subprocess.Popen(["xdg-open", LOG_FILE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.system(f'notepad "{LOG_FILE}"')

    def _on_edit_config(icon, item):
        if sys.platform != "win32":
            subprocess.Popen(["xdg-open", ENV_FILE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.system(f'notepad "{ENV_FILE}"')

    def _on_quit(icon, item):
        logger.info("[TRAY] Exit requested via system tray")
        icon.stop()
        release_pid_lock()
        os._exit(0)

    try:
        _tray_icon = pystray.Icon(
            "tg_fdm_proxy",
            icon=_create_tray_icon_image(64, True),
            title=f"Telegram FDM Proxy (Port {port})",
            menu=pystray.Menu(
                pystray.MenuItem(f"TG FDM Proxy — Online (Port {port})", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("✈️ Open Telegram Bot", _on_open_bot),
                pystray.MenuItem("⚙️ Settings & Configuration", _on_settings),
                pystray.MenuItem("📄 View Live Logs", _on_view_logs),
                pystray.MenuItem("📝 Edit Configuration (.env)", _on_edit_config),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("🛑 Quit / Stop Proxy", _on_quit),
            ),
        )
        t = threading.Thread(target=_tray_icon.run, daemon=True)
        t.start()
        logger.info("[TRAY] System tray icon initialized successfully")
    except Exception as e:
        logger.warning(f"[TRAY] System tray unavailable on this display: {e}")
        logger.info("[TRAY] Gracefully operating in background daemon mode")

def _stop_tray_icon():
    global _tray_icon
    if _tray_icon:
        try:
            _tray_icon.stop()
        except Exception:
            pass
        _tray_icon = None

# ────────────────────────────────────────────────────────
#  Core Async Application Runner
# ────────────────────────────────────────────────────────
async def run_server(host: str, port: int, enable_tray: bool = True):
    global client, INSTALLED_MANAGERS, ACTIVE_CHANNELS, _bot_username
    global PROXY_HOST, PROXY_PORT, MIN_FILE_SIZE_MB, QUALITY_WAIT_SECS
    global ALLOWED_EXT, KEYWORD_BLOCK, KEYWORD_ALLOW, batch_active, batch_links

    api_id, api_hash, bot_token = ensure_env()
    API_ID = int(api_id)
    API_HASH = api_hash
    BOT_TOKEN = bot_token

    PROXY_HOST = host or os.getenv("PROXY_HOST", "127.0.0.1")
    PROXY_PORT = int(port or os.getenv("PROXY_PORT", "8080"))
    MIN_FILE_SIZE_MB = float(os.getenv("MIN_FILE_SIZE_MB", "50").strip())
    QUALITY_WAIT_SECS = int(os.getenv("QUALITY_WAIT_SECS", "30").strip())

    raw_ext = os.getenv("ALLOWED_EXT", "").strip()
    if "#" in raw_ext:
        raw_ext = raw_ext.split("#")[0].strip()
    ALLOWED_EXT = set()
    if raw_ext:
        for _e in raw_ext.split(","):
            _e = _e.strip().lower()
            ALLOWED_EXT.add(_e if _e.startswith(".") else f".{_e}")

    def _kw_set(key: str) -> set:
        raw = os.getenv(key, "").strip()
        if "#" in raw:
            raw = raw.split("#")[0].strip()
        return {w.strip().lower() for w in raw.split(",") if w.strip()} if raw else set()

    KEYWORD_BLOCK = _kw_set("KEYWORD_BLOCK")
    KEYWORD_ALLOW = _kw_set("KEYWORD_ALLOW")

    raw_channels = os.getenv("TARGET_CHANNELS", "").strip()
    if raw_channels:
        for c in raw_channels.split(","):
            c = c.strip()
            if c.isdigit() or (c.startswith("-") and c[1:].isdigit()):
                ACTIVE_CHANNELS.add(int(c))
            elif c:
                ACTIVE_CHANNELS.add(c)

    INSTALLED_MANAGERS = detect_managers()

    client = TelegramClient(
        SESSION_NAME, API_ID, API_HASH,
        connection_retries=10,
        retry_delay=1,
    )

    # Register Bot Event Handlers
    @client.on(events.NewMessage(incoming=True, pattern="/start_batch"))
    async def start_batch(event):
        global batch_active, batch_links
        batch_active = True
        batch_links = []
        await event.reply(
            "📦 **Batch Mode Active**\n"
            "Forward files to queue them.\n\n"
            "▸ Send `/end_batch` to push all files to your download manager."
        )

    @client.on(events.NewMessage(incoming=True, pattern="/end_batch"))
    async def end_batch(event):
        global batch_active, batch_links
        if not batch_active:
            await event.reply("⚠️ **No Active Batch** — use `/start_batch` first.")
            return
        if not batch_links:
            await event.reply("📂 **Batch is Empty** — forward some files first.")
            batch_active = False
            return

        success_count = 0
        if INSTALLED_MANAGERS:
            await event.reply(f"🚀 Pushing {len(batch_links)} files to download manager...")
            for link in batch_links:
                _, ok = await auto_send(link)
                if ok:
                    success_count += 1
                await asyncio.sleep(0.5)

        txt_stream = io.BytesIO("\n".join(batch_links).encode("utf-8"))
        txt_stream.name = "fdm_batch_links.txt"
        reply = f"✅ **Batch Complete** — {success_count}/{len(batch_links)} pushed.\n_(Backup link list attached)_" if success_count > 0 else "📥 **No manager found.** Import the attached .txt:"
        await event.reply(reply, file=txt_stream)
        send_desktop_notification("Batch Finished", f"Pushed {success_count}/{len(batch_links)} files.")
        batch_active = False
        batch_links = []

    @client.on(events.NewMessage(incoming=True, pattern="/channels"))
    async def cmd_channels(event):
        if not ACTIVE_CHANNELS:
            await event.reply("📡 **No channels watched.**\nUse `/add_channel @username` to add one.")
            return
        lines = "\n".join(f"  • `{ch}`" for ch in sorted(str(c) for c in ACTIVE_CHANNELS))
        await event.reply(f"📡 **Watched Channels ({len(ACTIVE_CHANNELS)}):**\n{lines}\n\n▸ `/add_channel <id>`\n▸ `/remove_channel <id>`")

    @client.on(events.NewMessage(incoming=True, pattern=r"/add_channel(?: (.+))?"))
    async def cmd_add_channel(event):
        arg = event.pattern_match.group(1)
        if not arg:
            await event.reply("Usage: `/add_channel @username` or `/add_channel -1001234567890`")
            return
        arg = arg.strip()
        channel = int(arg) if arg.lstrip("-").isdigit() else arg
        if channel in ACTIVE_CHANNELS:
            await event.reply(f"✅ `{channel}` is already being watched.")
            return
        ACTIVE_CHANNELS.add(channel)
        client.add_event_handler(_sniffer_handler, events.NewMessage(chats=[channel]))
        logger.info(f"[CHANNELS] Added: {channel}")
        await event.reply(f"✅ Now watching `{channel}` (Total: {len(ACTIVE_CHANNELS)}).")

    @client.on(events.NewMessage(incoming=True, pattern=r"/remove_channel(?: (.+))?"))
    async def cmd_remove_channel(event):
        arg = event.pattern_match.group(1)
        if not arg:
            await event.reply("Usage: `/remove_channel @username` or `/remove_channel -1001234567890`")
            return
        arg = arg.strip()
        channel = int(arg) if arg.lstrip("-").isdigit() else arg
        if channel not in ACTIVE_CHANNELS:
            await event.reply(f"⚠️ `{channel}` not found in watch list.")
            return
        ACTIVE_CHANNELS.discard(channel)
        logger.info(f"[CHANNELS] Removed: {channel}")
        await event.reply(f"🗑️ Removed `{channel}`.")

    @client.on(events.NewMessage(incoming=True))
    async def on_new_message(event):
        global batch_active, batch_links
        if event.message.text and event.message.text.startswith("/"):
            return
        if not (event.message.media and event.message.file):
            return

        chat_id = event.chat_id
        message_id = event.id
        link = f"http://{PROXY_HOST}:{PROXY_PORT}/dl/{chat_id}/{message_id}"
        fname = event.message.file.name or "Unknown File"
        size_mb = event.message.file.size / (1024 * 1024)

        if batch_active:
            batch_links.append(link)
            logger.info(f"Queued: {fname}")
            await event.reply(
                f"📥 **Added to Batch Queue**\n└ `{fname}` ({size_mb:.2f} MB)\n📊 Total: {len(batch_links)}",
                buttons=[[Button.inline("Copy Link", data=f"dl_direct_{chat_id}_{message_id}")]],
            )
            return

        fname_lower = fname.lower()
        if KEYWORD_BLOCK and any(kw in fname_lower for kw in KEYWORD_BLOCK):
            await event.reply(f"🚫 **Blocked** — `{fname}` matched keyword filter.")
            return
        if KEYWORD_ALLOW and not any(kw in fname_lower for kw in KEYWORD_ALLOW):
            await event.reply(f"⏭️ **Skipped** — `{fname}` not in allowed keywords.")
            return
        if _is_duplicate(chat_id, message_id):
            return

        # Cache message in memory for instant HTTP proxy serving without 404s
        _message_cache[(chat_id, message_id)] = event.message

        mgr, pushed = await auto_send(link)
        buttons = make_buttons(chat_id, message_id)
        label = MANAGER_LABELS.get(mgr, mgr)

        if pushed:
            send_desktop_notification(
                "Download Triggered",
                f"Sent '{fname}' to {label}",
                category="download",
                dedup_key=f"dl_{chat_id}_{message_id}",
            )
            _sent = await event.reply(
                f"✅ **Sent to {label}**\n└ `{fname}` ({size_mb:.2f} MB)",
                buttons=buttons,
            )
            download_registry[(chat_id, message_id)] = {
                "start": time.monotonic(),
                "reply_chat": _sent.chat_id,
                "reply_to": _sent.id,
                "fname": fname,
                "size_bytes": event.message.file.size,
                "notified": False,
            }
        else:
            await event.reply(
                f"📄 **File Ready**\n└ `{fname}` ({size_mb:.2f} MB)\n\nUse buttons below to download:",
                buttons=buttons,
            )

    @client.on(events.CallbackQuery(data=re.compile(b"^dl_")))
    async def on_callback_query(event):
        raw = event.data.decode("utf-8")
        parts = raw.split("_", 3)
        mgr_id = parts[1]
        chat_id = parts[2]
        msg_id = parts[3]
        link = f"http://{PROXY_HOST}:{PROXY_PORT}/dl/{chat_id}/{msg_id}"
        await event.answer()

        if mgr_id == "direct":
            await event.respond(f"📥 **Direct Stream URL:**\n`{link}`\n\n_(Paste into any download manager)_")
            return

        label = MANAGER_LABELS.get(mgr_id, mgr_id.upper())
        if mgr_id not in INSTALLED_MANAGERS:
            await event.respond(f"⚠️ **{label} not detected.**\nManual link: `{link}`")
            return

        ok = await trigger_manager(mgr_id, link)
        if ok:
            send_desktop_notification("Download Dispatched", f"Sent to {label}")
            await event.respond(f"{label} **Download Started!**\n`{link}`")
        else:
            await event.respond(f"❌ **Failed to launch {label}.**\nManual link: `{link}`")

    # Connect Bot Client
    await client.start(bot_token=BOT_TOKEN)
    me = await client.get_me()
    _bot_username = me.username or ""
    logger.info(f"Bot connected as @{_bot_username}")

    try:
        await client(SetBotCommandsRequest(
            scope=BotCommandScopeDefault(),
            lang_code="",
            commands=[
                BotCommand("start_batch", "Start collecting batch links"),
                BotCommand("end_batch", "Push batch links to download manager"),
                BotCommand("channels", "List watched channels"),
                BotCommand("add_channel", "Watch channel for downloads"),
                BotCommand("remove_channel", "Stop watching channel"),
            ],
        ))
    except Exception as _cmd_err:
        logger.warning(f"Command registration notice: {_cmd_err}")

    if ACTIVE_CHANNELS:
        client.add_event_handler(_sniffer_handler, events.NewMessage(chats=list(ACTIVE_CHANNELS)))

    # Start HTTP Proxy
    app = web.Application()
    app.router.add_get("/dl/{chat_id}/{message_id}", handle_download)
    runner = web.AppRunner(app)
    await runner.setup()

    actual_port = find_free_port(PROXY_PORT)
    if actual_port != PROXY_PORT:
        logger.warning(f"Port {PROXY_PORT} occupied, using port {actual_port}")
        PROXY_PORT = actual_port

    site = web.TCPSite(runner, PROXY_HOST, PROXY_PORT)
    await site.start()

    send_desktop_notification("Telegram FDM Proxy Active", f"Proxy listening on http://{PROXY_HOST}:{PROXY_PORT}")

    if enable_tray:
        _start_tray_icon(PROXY_PORT)

    print("\n" + "=" * 55)
    print("  🚀 Telegram FDM Proxy - Running")
    print("=" * 55)
    print(f"  • Bot User   : @{_bot_username}")
    print(f"  • HTTP Proxy : http://{PROXY_HOST}:{PROXY_PORT}")
    print(f"  • Config Dir : {APP_DIR}")
    print(f"  • Log File   : {LOG_FILE}")
    if INSTALLED_MANAGERS:
        for mgr, path in INSTALLED_MANAGERS.items():
            print(f"  • Manager    : {MANAGER_LABELS.get(mgr, mgr)} ({os.path.basename(path)})")
    else:
        print("  • Manager    : None (Direct Stream Mode)")
    print("=" * 55 + "\n")

    try:
        while True:
            try:
                if not client.is_connected():
                    await client.connect()
                await client.run_until_disconnected()
                break
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Connection glitch: {e}. Reconnecting...")
                await asyncio.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        _stop_tray_icon()
        await site.stop()
        await runner.cleanup()
        await client.disconnect()
        release_pid_lock()

# ────────────────────────────────────────────────────────
#  CLI Management Commands (Arch Linux / Desktop)
# ────────────────────────────────────────────────────────
def cli_status():
    """Display status of the application and systemd service."""
    running_pid = get_running_pid()
    print("=" * 50)
    print("  Telegram FDM Proxy - Status")
    print("=" * 50)
    print(f"Config Directory : {APP_DIR}")
    print(f"Config File      : {ENV_FILE} ({'Exists' if os.path.isfile(ENV_FILE) else 'Missing'})")
    print(f"Log File         : {LOG_FILE}")

    if running_pid:
        print(f"Proxy Process    : 🟢 RUNNING (PID: {running_pid})")
    else:
        print("Proxy Process    : 🔴 STOPPED")

    if sys.platform != "win32":
        try:
            res = subprocess.run(["systemctl", "--user", "is-active", "tg-fdm-proxy.service"], capture_output=True, text=True)
            svc_active = res.stdout.strip()
            print(f"Systemd Service  : {'🟢 ' + svc_active if svc_active == 'active' else '⚪ ' + svc_active}")
        except Exception:
            pass

    managers = detect_managers()
    print("\nDetected Download Managers:")
    if managers:
        for m, path in managers.items():
            print(f"  • {MANAGER_LABELS.get(m, m)}: {path}")
    else:
        print("  • None detected (Direct link streaming active)")
    print("=" * 50)

def cli_stop():
    """Stop running instance of tg-fdm-proxy."""
    stopped = False
    if sys.platform != "win32":
        try:
            subprocess.run(["systemctl", "--user", "stop", "tg-fdm-proxy.service"], capture_output=True)
        except Exception:
            pass

    pid = get_running_pid()
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            for _ in range(10):
                time.sleep(0.1)
                try:
                    os.kill(pid, 0)
                except OSError:
                    stopped = True
                    break
            else:
                try:
                    os.kill(pid, signal.SIGKILL)
                    stopped = True
                except OSError:
                    stopped = True
            print(f"Stopped tg-fdm-proxy (PID {pid}).")
        except Exception as e:
            print(f"Error stopping PID {pid}: {e}")

    if PSUTIL_AVAILABLE:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.pid != os.getpid():
                    cmd = " ".join(proc.info['cmdline'] or [])
                    if "tg_fdm_proxy.py" in cmd:
                        proc.kill()
                        stopped = True
            except Exception:
                pass

    release_pid_lock()
    if stopped:
        print("Proxy stopped successfully.")
    else:
        print("No running instance detected.")

def cli_logs(follow: bool = False, lines: int = 50):
    """View or follow logs."""
    if not os.path.isfile(LOG_FILE):
        print(f"Log file not found at: {LOG_FILE}")
        return

    if follow:
        try:
            subprocess.run(["tail", "-n", str(lines), "-f", LOG_FILE])
        except KeyboardInterrupt:
            pass
    else:
        try:
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                content = f.readlines()
            print("".join(content[-lines:]))
        except Exception as e:
            print(f"Could not read log file: {e}")

def cli_config():
    """Open config file in default editor."""
    if not os.path.isfile(ENV_FILE):
        ensure_env()
    
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if editor:
        os.system(f'{editor} "{ENV_FILE}"')
    elif sys.platform != "win32":
        import shutil
        if shutil.which("xdg-open"):
            subprocess.run(["xdg-open", ENV_FILE])
        elif shutil.which("nano"):
            subprocess.run(["nano", ENV_FILE])
    else:
        os.system(f'notepad "{ENV_FILE}"')

# ────────────────────────────────────────────────────────
#  Main Entrypoint & Dispatcher
# ────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Telegram FDM Proxy - High-speed Download Manager Stream Gateway",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Start command
    p_start = subparsers.add_parser("start", help="Start proxy server")
    p_start.add_argument("--daemon", "-d", action="store_true", help="Run in headless daemon mode (no tray)")
    p_start.add_argument("--tray", "-t", action="store_true", help="Run with system tray icon")
    p_start.add_argument("--host", default="127.0.0.1", help="Host IP to bind HTTP proxy")
    p_start.add_argument("--port", "-p", type=int, default=8080, help="Port to bind HTTP proxy")

    # Stop command
    subparsers.add_parser("stop", help="Stop running proxy server")

    # Restart command
    p_restart = subparsers.add_parser("restart", help="Restart proxy server")
    p_restart.add_argument("--tray", "-t", action="store_true", help="Run with system tray icon")

    # Status command
    subparsers.add_parser("status", help="Show running status and download managers")

    # Logs command
    p_logs = subparsers.add_parser("logs", help="View proxy server logs")
    p_logs.add_argument("-f", "--follow", action="store_true", help="Follow live log output")
    p_logs.add_argument("-n", "--lines", type=int, default=50, help="Number of lines to view")

    # Config command
    subparsers.add_parser("config", help="Edit configuration (.env) file")

    # Top-level direct flags
    parser.add_argument("--daemon", "-d", action="store_true", help="Run in headless daemon mode")
    parser.add_argument("--tray", "-t", action="store_true", help="Run with system tray icon")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Port for HTTP proxy")
    parser.add_argument("--host", default="127.0.0.1", help="Host for HTTP proxy")

    args = parser.parse_args()

    if args.command == "status":
        cli_status()
        return
    elif args.command == "stop":
        cli_stop()
        return
    elif args.command == "restart":
        cli_stop()
        time.sleep(1)
        # Re-run start
        args.command = "start"
    elif args.command == "logs":
        cli_logs(follow=args.follow, lines=args.lines)
        return
    elif args.command == "config":
        cli_config()
        return

    # Check Single Instance Lock
    acquired, active_pid = acquire_pid_lock()
    if not acquired:
        print(f"⚠️ Telegram FDM Proxy is already running (PID: {active_pid}).")
        send_desktop_notification("Telegram FDM Proxy", f"Already active (PID: {active_pid})")
        return

    enable_tray = False if getattr(args, "daemon", False) else True
    if getattr(args, "tray", False):
        enable_tray = True

    try:
        asyncio.run(run_server(host=args.host, port=args.port, enable_tray=enable_tray))
    except KeyboardInterrupt:
        print("\nStopping Telegram FDM Proxy...")
    finally:
        release_pid_lock()

if __name__ == "__main__":
    main()
