import os
import re
import asyncio
import io
import sys
import socket
import logging
import subprocess
import time

# Force UTF-8 output on Windows console to avoid emoji encoding crashes
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from aiohttp import web
from telethon import TelegramClient, events, Button
from telethon.tl.functions.bots import SetBotCommandsRequest
from telethon.tl.types import BotCommand, BotCommandScopeDefault
from dotenv import load_dotenv

# ────────────────────────────────────────────────────────
#  Environment — interactive setup wizard (from tg_fdm_proxy 1.py)
# ────────────────────────────────────────────────────────
def ensure_env():
    """Check .env for credentials; prompt interactively if any are missing."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(env_path)

    api_id    = os.getenv("API_ID",    "").strip()
    api_hash  = os.getenv("API_HASH",  "").strip()
    bot_token = os.getenv("BOT_TOKEN", "").strip()

    if not all([api_id, api_hash, bot_token]):
        print("\n" + "=" * 50)
        print("  TELEGRAM FDM PROXY - FIRST-TIME SETUP")
        print("=" * 50)
        print("Get these values from https://my.telegram.org and @BotFather\n")
        try:
            if not api_id:
                api_id    = input("1. Enter your API_ID   : ").strip()
            if not api_hash:
                api_hash  = input("2. Enter your API_HASH : ").strip()
            if not bot_token:
                bot_token = input("3. Enter your BOT_TOKEN: ").strip()

            with open(env_path, "w") as f:
                f.write(f"API_ID={api_id}\n")
                f.write(f"API_HASH={api_hash}\n")
                f.write(f"BOT_TOKEN={bot_token}\n")

            print(f"\nConfiguration saved to: {env_path}")
            load_dotenv(env_path)
        except KeyboardInterrupt:
            print("\nSetup cancelled.")
            sys.exit(1)

    return api_id, api_hash, bot_token


API_ID, API_HASH, BOT_TOKEN = ensure_env()
API_ID = int(API_ID)

# Target Channels (optional)
raw_channels = os.getenv("TARGET_CHANNELS", "").strip()
TARGET_CHANNELS = []
if raw_channels:
    for c in raw_channels.split(","):
        c = c.strip()
        if c.isdigit() or (c.startswith("-") and c[1:].isdigit()):
            TARGET_CHANNELS.append(int(c))
        elif c:
            TARGET_CHANNELS.append(c)

MIN_FILE_SIZE_MB   = float(os.getenv("MIN_FILE_SIZE_MB",   "50").strip())
# How long (seconds) to wait for more quality variants before picking the best
QUALITY_WAIT_SECS = int(os.getenv("QUALITY_WAIT_SECS", "30").strip())

# Option G: allowed file-extension filter — empty = accept everything
_raw_ext = os.getenv("ALLOWED_EXT", "").strip()
ALLOWED_EXT: set[str] = set()
if _raw_ext:
    for _e in _raw_ext.split(","):
        _e = _e.strip().lower()
        ALLOWED_EXT.add(_e if _e.startswith(".") else f".{_e}")

PROXY_HOST = os.getenv("PROXY_HOST", "127.0.0.1")
PROXY_PORT = int(os.getenv("PROXY_PORT", "8080"))

# Option P: keyword filters — comma-separated, case-insensitive
def _kw_set(env_key: str) -> set[str]:
    raw = os.getenv(env_key, "").strip()
    return {w.strip().lower() for w in raw.split(",") if w.strip()} if raw else set()

KEYWORD_BLOCK = _kw_set("KEYWORD_BLOCK")  # e.g. sample,trailer,cam,ts
KEYWORD_ALLOW = _kw_set("KEYWORD_ALLOW")  # e.g. 1080p,bluray,webrip  (empty=allow all)

# Option O: duplicate guard — (chat_id, message_id) → timestamp triggered
_triggered: dict[tuple, float] = {}
TRIGGER_TTL_SECS = 3600  # forget entries after 1 hour


def _is_duplicate(chat_id: int, message_id: int) -> bool:
    key = (chat_id, message_id)
    now = time.monotonic()
    # Prune stale entries
    stale = [k for k, t in _triggered.items() if now - t > TRIGGER_TTL_SECS]
    for k in stale:
        del _triggered[k]
    if key in _triggered:
        return True
    _triggered[key] = now
    return False


# Option S: auto-rename — clean filename for FDM/library
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
_RES_RE  = re.compile(r"(2160p?|4k|uhd|1080p?|720p?|480p?|360p?)", re.IGNORECASE)
_YEAR_RE = re.compile(r"(?<![\d])(19\d{2}|20[0-2]\d)(?![\d])")


def auto_rename(raw: str) -> str:
    """Option S: format raw filename as 'Title (Year) [Resolution].ext'."""
    ext  = os.path.splitext(raw)[1]          # keep original extension
    stem = os.path.splitext(raw)[0]

    res_m  = _RES_RE.search(stem)
    year_m = _YEAR_RE.search(stem)
    res    = res_m.group(1).upper() if res_m else ""
    year   = year_m.group(1)        if year_m else ""

    # Remove noise tokens
    title = _NOISE_RE.sub(" ", stem)
    # Remove the resolution and year from title string
    if res_m:  title = title[:res_m.start()] + title[res_m.end():]
    if year_m: title = title[:year_m.start()] + title[year_m.end():]
    # Collapse separators to spaces
    title = re.sub(r"[\._\-]+", " ", title).strip()
    title = re.sub(r"\s{2,}", " ", title)

    if not title:
        return raw  # bail — couldn't parse anything useful

    parts = [title]
    if year: parts.append(f"({year})")
    if res:  parts.append(f"[{res}]")
    return " ".join(parts) + ext

def find_free_port(start: int = 8080, max_attempts: int = 100) -> int:
    """Find an available TCP port starting from `start` (from tg_fdm_proxy 1.py)."""
    for port in range(start, start + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free ports found between {start} and {start + max_attempts - 1}")

# ────────────────────────────────────────────────────────
#  Logging
# ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("tg_fdm_proxy.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)
logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
# Silence Telethon's verbose flood-wait / chunk progress spam
logging.getLogger("telethon").setLevel(logging.WARNING)

# ────────────────────────────────────────────────────────
#  Download Manager Detection  (dynamic — registry first)
# ────────────────────────────────────────────────────────

# Known exe filenames per manager ID
MANAGER_EXE_NAMES = {
    "fdm":  "fdm.exe",
    "idm":  "IDMan.exe",
    "neat": "NeatDM.exe",
}

# CLI command templates per manager ({ exe } and { url } are substituted at call time)
MANAGER_COMMANDS = {
    "fdm":  ["{exe}", "-a", "{url}"],
    "idm":  ["{exe}", "/d", "{url}", "/n", "/q"],
    "neat": ["{exe}", "{url}"],
}

MANAGER_LABELS = {
    "fdm":    "🚀 FDM",
    "idm":    "⚡ IDM",
    "neat":   "💧 Neat DM",
    "direct": "📥 Copy Link",
}

# Hardcoded fallback paths (used only if registry + where.exe miss)
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

# Registry hives + uninstall key paths to scan
_REG_UNINSTALL_KEYS = [
    (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",),
    (r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",),
]


def _registry_find(exe_name: str) -> str | None:
    """Search Windows registry uninstall entries for an exe. Returns full path or None."""
    try:
        import winreg
    except ImportError:
        return None  # Not on Windows

    hives = [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]
    for hive in hives:
        for (key_path,) in _REG_UNINSTALL_KEYS:
            try:
                with winreg.OpenKey(hive, key_path) as key:
                    count = winreg.QueryInfoKey(key)[0]
                    for i in range(count):
                        try:
                            sub = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, sub) as sk:
                                for value_name in ("InstallLocation", "InstallDir"):
                                    try:
                                        loc = winreg.QueryValueEx(sk, value_name)[0].strip()
                                        if loc:
                                            candidate = os.path.join(loc, exe_name)
                                            if os.path.isfile(candidate):
                                                return candidate
                                    except FileNotFoundError:
                                        pass
                        except Exception:
                            pass
            except Exception:
                pass
    return None


def _where_find(exe_name: str) -> str | None:
    """Use where.exe to locate an executable on PATH. Returns full path or None."""
    try:
        result = subprocess.run(
            ["where", exe_name], capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            first_line = result.stdout.strip().splitlines()[0].strip()
            if os.path.isfile(first_line):
                return first_line
    except Exception:
        pass
    return None


def detect_managers() -> dict[str, str]:
    """
    Dynamically find all supported download managers.
    Search order per manager:
      1. Windows Registry (InstallLocation / InstallDir)
      2. where.exe  (anything on PATH)
      3. Hardcoded fallback paths
    Priority order in returned dict: fdm -> idm -> neat
    """
    found: dict[str, str] = {}

    for mgr_id in ("fdm", "idm", "neat"):          # priority order
        exe_name = MANAGER_EXE_NAMES[mgr_id]

        # 1. Registry
        path = _registry_find(exe_name)
        if path:
            found[mgr_id] = path
            logger.info(f"[OK] Found {mgr_id.upper()} via registry: {path}")
            continue

        # 2. where.exe (PATH)
        path = _where_find(exe_name)
        if path:
            found[mgr_id] = path
            logger.info(f"[OK] Found {mgr_id.upper()} via PATH: {path}")
            continue

        # 3. Hardcoded fallback
        for fb in _FALLBACK_PATHS.get(mgr_id, []):
            if os.path.isfile(fb):
                found[mgr_id] = fb
                logger.info(f"[OK] Found {mgr_id.upper()} via fallback: {fb}")
                break

    if not found:
        logger.warning("[!!] No download managers detected. Links will be copy-paste only.")
    return found


INSTALLED_MANAGERS: dict[str, str] = {}  # populated in main()

# Exe names as they appear in Windows tasklist for each manager
MANAGER_PROCESS_NAMES = {
    "fdm":  "fdm.exe",
    "idm":  "IDMan.exe",
    "neat": "NeatDM.exe",
}


def is_manager_running(manager_id: str) -> bool:
    """Returns True if the manager's process is currently running."""
    proc_name = MANAGER_PROCESS_NAMES.get(manager_id, "")
    if not proc_name:
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {proc_name}", "/NH"],
            capture_output=True, text=True, timeout=3,
        )
        return proc_name.lower() in result.stdout.lower()
    except Exception:
        return False


async def ensure_manager_running(manager_id: str) -> bool:
    """
    If the manager is installed but not running, launch it and wait up to 5 s
    for it to appear in the process list. Returns True when ready.
    """
    exe = INSTALLED_MANAGERS.get(manager_id)
    if not exe:
        return False

    if is_manager_running(manager_id):
        return True  # already up, nothing to do

    logger.info(f"[{manager_id.upper()}] Not running - launching {os.path.basename(exe)}...")
    try:
        # Open the app without passing a URL yet
        subprocess.Popen([exe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        logger.error(f"[{manager_id.upper()}] Failed to launch: {e}")
        return False

    # Poll until the process appears (max 5 s)
    for _ in range(10):
        await asyncio.sleep(0.5)
        if is_manager_running(manager_id):
            logger.info(f"[{manager_id.upper()}] Ready.")
            await asyncio.sleep(0.5)  # small extra buffer for UI init
            return True

    logger.warning(f"[{manager_id.upper()}] Launched but did not appear in process list within 5s.")
    return False


async def trigger_manager(manager_id: str, url: str) -> bool:
    """Ensures the manager is running, then sends the URL. Returns True on success."""
    exe = INSTALLED_MANAGERS.get(manager_id)
    if not exe:
        return False

    # Auto-launch if installed but closed (FDM priority case)
    ready = await ensure_manager_running(manager_id)
    if not ready:
        logger.warning(f"[{manager_id.upper()}] Could not confirm manager is running - attempting anyway.")

    cmd_template = MANAGER_COMMANDS.get(manager_id, [])
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


async def auto_send(url: str) -> tuple[str, bool]:
    """Try installed managers in priority order: fdm → idm → neat. Returns (manager_id, success)."""
    for mgr in ("fdm", "idm", "neat"):
        if mgr in INSTALLED_MANAGERS:
            ok = await trigger_manager(mgr, url)
            if ok:
                return mgr, True
    return "none", False


# ────────────────────────────────────────────────────────
#  Telethon Client
# ────────────────────────────────────────────────────────
client = TelegramClient(
    "fdm_proxy_bot_session", API_ID, API_HASH,
    connection_retries=10,   # auto-reconnect on TCP drop
    retry_delay=1,
)

# Batch state
batch_active = False
batch_links: list[str] = []

# Option N: speed-stats registry — keyed by (chat_id, message_id)
download_registry: dict[tuple, dict] = {}


# ────────────────────────────────────────────────────────
#  HTTP Proxy Handler (serves file chunks to the DM)
# ────────────────────────────────────────────────────────
async def handle_download(request: web.Request) -> web.StreamResponse:
    chat_id    = int(request.match_info["chat_id"])
    message_id = int(request.match_info["message_id"])
    response      = None
    _down_start    = time.monotonic()   # Option N: per-request timer
    _bytes_written = 0

    try:
        # Retrieve the specific message containing the media (from tg_fdm_proxy 1.py)
        message = await client.get_messages(chat_id, ids=message_id)
        if not message or not message.media or not hasattr(message, "file"):
            return web.Response(status=404, text="Message not found or does not contain media.")

        file_size = int(message.file.size)  # ensure int — Telegram can return float
        raw_name  = message.file.name if message.file.name else f"tg_media_{message_id}.bin"
        raw_name  = "".join([c for c in raw_name if (c.isalnum() or c in " .-_()")]).strip()
        # Option S: rename to clean format
        file_name = auto_rename(raw_name)

        range_header = request.headers.get("Range", "")
        status = 200
        start  = 0
        end    = file_size - 1

        # Parse HTTP Range Header for multi-threaded downloading in FDM
        if range_header:
            match = re.search(r"bytes=(\d+)-(\d*)", range_header)
            if match:
                start = int(match.group(1))
                if match.group(2):
                    end = int(match.group(2))
            status = 206

        length = int(end - start + 1)  # must be int for iter_download

        headers = {
            "Content-Type":        "application/octet-stream",
            "Content-Disposition": f'attachment; filename="{file_name}"',
            "Accept-Ranges":       "bytes",
            "Content-Range":       f"bytes {start}-{end}/{file_size}",
            "Content-Length":      str(length),
        }

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

        # Option N: dispatch speed-stats Telegram reply (fires exactly once per file)
        _key = (chat_id, message_id)
        if _key in download_registry and not download_registry[_key].get("notified"):
            _info = download_registry.pop(_key)
            _info["notified"] = True
            _elapsed  = time.monotonic() - _down_start
            _speed_mb = _bytes_written / max(_elapsed, 0.1) / (1024 * 1024)
            _size_gb  = _info["size_bytes"] / (1024 ** 3)
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
        # FDM closed a specific connection thread — standard behaviour in multi-threading
        return response
    except Exception as e:
        print(f"Error during download for chat {chat_id}, message {message_id}: {e}")
        logger.error(f"Download error for chat {chat_id}, message {message_id}: {e}")
        return web.Response(status=500, text=f"Download failed: {str(e)}")


# ────────────────────────────────────────────────────────
#  Helper: Build smart button row based on installed DMs
# ────────────────────────────────────────────────────────
def make_buttons(chat_id: int, message_id: int) -> list:
    """Build inline buttons — only show buttons for installed managers + direct link."""
    row1, row2 = [], []

    for mgr in ("fdm", "idm", "neat"):
        if mgr in INSTALLED_MANAGERS:
            row1.append(Button.inline(MANAGER_LABELS[mgr], data=f"dl_{mgr}_{chat_id}_{message_id}"))

    row2.append(Button.inline(MANAGER_LABELS["direct"], data=f"dl_direct_{chat_id}_{message_id}"))

    buttons = []
    if row1:
        buttons.append(row1)
    buttons.append(row2)
    return buttons


# ────────────────────────────────────────────────────────
#  Batch Commands
# ────────────────────────────────────────────────────────
@client.on(events.NewMessage(incoming=True, pattern="/start_batch"))
async def start_batch(event):
    global batch_active, batch_links
    batch_active = True
    batch_links  = []
    await event.reply(
        "📦 **Batch Mode Active**\n"
        "Forward files to add them to the queue.\n\n"
        "▸ Use `/end_batch` to finalize and push to your download manager."
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

    if success_count > 0:
        reply = (
            f"✅ **Batch Complete** — {success_count}/{len(batch_links)} pushed.\n"
            f"_(Backup link list attached)_"
        )
    else:
        reply = "📥 **No manager found.** Import the attached .txt into your download manager:"

    await event.reply(reply, file=txt_stream)
    batch_active = False
    batch_links  = []


# ────────────────────────────────────────────────────────
#  Channel Auto-Sniffer
# ────────────────────────────────────────────────────────
# ────────────────────────────────────────────────────────
#  Dynamic Channel Management  (/channels, /add_channel, /remove_channel)
# ────────────────────────────────────────────────────────
# Pre-loaded from .env TARGET_CHANNELS; editable at runtime via commands
ACTIVE_CHANNELS: set = set(TARGET_CHANNELS)


@client.on(events.NewMessage(incoming=True, pattern="/channels"))
async def cmd_channels(event):
    """List all currently watched channels."""
    if not ACTIVE_CHANNELS:
        await event.reply(
            "📡 **No channels being watched.**\n\n"
            "Add one with:\n`/add_channel @username` or `/add_channel -1001234567890`"
        )
        return
    lines = "\n".join(f"  • `{ch}`" for ch in sorted(str(c) for c in ACTIVE_CHANNELS))
    await event.reply(
        f"📡 **Watched Channels ({len(ACTIVE_CHANNELS)}):**\n{lines}\n\n"
        f"▸ `/add_channel <id>` — start watching a channel\n"
        f"▸ `/remove_channel <id>` — stop watching a channel"
    )


@client.on(events.NewMessage(incoming=True, pattern=r"/add_channel(?: (.+))?"))
async def cmd_add_channel(event):
    """Add a channel to the auto-sniffer. Usage: /add_channel @username or -100id"""
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
    logger.info(f"[CHANNELS] Added: {channel}  |  Active: {ACTIVE_CHANNELS}")
    await event.reply(f"✅ Now watching `{channel}`.\nTotal: **{len(ACTIVE_CHANNELS)}** channel(s).")


@client.on(events.NewMessage(incoming=True, pattern=r"/remove_channel(?: (.+))?"))
async def cmd_remove_channel(event):
    """Remove a channel from the auto-sniffer."""
    arg = event.pattern_match.group(1)
    if not arg:
        await event.reply("Usage: `/remove_channel @username` or `/remove_channel -1001234567890`")
        return
    arg = arg.strip()
    channel = int(arg) if arg.lstrip("-").isdigit() else arg
    if channel not in ACTIVE_CHANNELS:
        await event.reply(f"⚠️ `{channel}` is not in the watch list.")
        return
    ACTIVE_CHANNELS.discard(channel)
    logger.info(f"[CHANNELS] Removed: {channel}  |  Active: {ACTIVE_CHANNELS}")
    await event.reply(f"🗑️ Removed `{channel}`.\nRemaining: **{len(ACTIVE_CHANNELS)}** channel(s).")


# ────────────────────────────────────────────────────────
#  Quality-Selection Engine
#  Groups quality variants (1080p / 720p / SD) of the same file and picks best
# ────────────────────────────────────────────────────────

# Resolution priority (higher = better)
_RES_RANK = [
    ("2160p", 2160), ("4k", 2160), ("uhd", 2160),
    ("1080p", 1080), ("1080i", 1080),
    ("720p",  720),  ("720i",  720),
    ("480p",  480),  ("360p",  360),  ("240p", 240),
]

# Buffers: key = (chat_id, group_key)
_quality_buffer: dict[tuple, list[dict]] = {}
_quality_timers: dict[tuple, asyncio.Task]  = {}


def _quality_score(fname: str, size: int) -> tuple[int, int]:
    """Return (resolution_rank, size_bytes) — higher is better."""
    name = fname.lower()
    for keyword, rank in _RES_RANK:
        if keyword in name:
            return rank, size
    return 0, size  # no resolution tag — fall back to largest size


def _group_key(fname: str, media_group_id) -> str:
    """
    Unique key for a 'batch' of quality variants.
    - Same Telegram album  → use album id (exact)
    - Sequential messages  → strip quality/size tokens from filename and normalise
    """
    if media_group_id:
        return f"album_{media_group_id}"
    # Strip common quality/codec/size tokens to find the movie title core
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
    base = re.sub(r"[^a-z0-9]", "", base)[:35]  # keep alphanumeric only, cap at 35 chars
    return f"name_{base}" if base else "name_unknown"


async def _flush_quality_group(buf_key: tuple) -> None:
    """
    Called after QUALITY_WAIT_SECS timeout.
    Picks the best candidate and triggers the download.
    """
    candidates = _quality_buffer.pop(buf_key, [])
    _quality_timers.pop(buf_key, None)

    if not candidates:
        return

    # Sort: highest resolution first, then largest size
    best = max(candidates, key=lambda c: _quality_score(c["fname"], c["size"]))
    res_rank, _ = _quality_score(best["fname"], best["size"])
    res_label   = f"{res_rank}p" if res_rank else "best size"

    chat_id    = best["chat_id"]
    message_id = best["message_id"]
    link       = f"http://{PROXY_HOST}:{PROXY_PORT}/dl/{chat_id}/{message_id}"
    fname      = best["fname"]
    size_mb    = best["size"] / (1024 * 1024)
    event      = best["event"]

    # Option P: keyword filter
    fname_lower = fname.lower()
    if KEYWORD_BLOCK and any(kw in fname_lower for kw in KEYWORD_BLOCK):
        logger.info(f"[FILTER-P] Blocked '{fname}' — keyword match")
        return
    if KEYWORD_ALLOW and not any(kw in fname_lower for kw in KEYWORD_ALLOW):
        logger.info(f"[FILTER-P] Skipped '{fname}' — no KEYWORD_ALLOW match")
        return

    # Option O: duplicate guard
    if _is_duplicate(chat_id, message_id):
        logger.info(f"[DEDUP] Already triggered ({chat_id}/{message_id}), skipping.")
        return

    skipped = len(candidates) - 1
    logger.info(
        f"[QUALITY] Winner: '{fname}' ({res_label}, {size_mb:.0f} MB) "
        f"from {skipped+1} variant(s)"
    )

    mgr, pushed = await auto_send(link)
    label = MANAGER_LABELS.get(mgr, mgr)

    skip_note = f"\n└ _{skipped} lower-quality variant(s) skipped_" if skipped else ""
    if pushed:
        _sent = await event.reply(
            f"🏆 **Best Quality → {label}**\n"
            f"└ `{fname}`\n"
            f"└ {res_label} · {size_mb:.0f} MB"
            f"{skip_note}"
        )
        download_registry[(chat_id, message_id)] = {
            "start":      time.monotonic(),
            "reply_chat": _sent.chat_id,
            "reply_to":   _sent.id,
            "fname":      fname,
            "size_bytes": best["size"],
            "notified":   False,
        }
    else:
        await event.reply(
            f"📄 **Best Quality Ready**\n"
            f"└ `{fname}` · {res_label} · {size_mb:.0f} MB{skip_note}\n"
            f"`{link}`"
        )


# ────────────────────────────────────────────────────────
#  Channel Auto-Sniffer  (checks live ACTIVE_CHANNELS set)
# ────────────────────────────────────────────────────────
async def _sniffer_handler(event):
    """Handles new file messages in watched channels with quality-selection buffering."""
    if event.chat_id not in ACTIVE_CHANNELS:
        return
    if not (event.message.media and event.message.file):
        return

    fname   = event.message.file.name or "Unknown File"
    size    = event.message.file.size
    size_mb = size / (1024 * 1024)

    if size_mb < MIN_FILE_SIZE_MB:
        return

    # Option G: extension whitelist
    if ALLOWED_EXT:
        _ext = os.path.splitext(fname)[1].lower()
        if _ext not in ALLOWED_EXT:
            logger.info(f"[FILTER] Skipped '{fname}' — '{_ext}' not in ALLOWED_EXT")
            return

    # Quality-selection: buffer this candidate
    gkey    = _group_key(fname, getattr(event.message, "grouped_id", None))
    buf_key = (event.chat_id, gkey)

    _quality_buffer.setdefault(buf_key, []).append({
        "chat_id":    event.chat_id,
        "message_id": event.id,
        "fname":      fname,
        "size":       size,
        "event":      event,
    })

    # Cancel existing timer and restart the wait window
    existing = _quality_timers.get(buf_key)
    if existing and not existing.done():
        existing.cancel()

    res_rank, _ = _quality_score(fname, size)
    res_label   = f"{res_rank}p" if res_rank else f"{size_mb:.0f} MB"
    logger.info(
        f"[QUALITY] Buffered: '{fname}' ({res_label}) — waiting {QUALITY_WAIT_SECS}s for more variants"
    )

    _quality_timers[buf_key] = asyncio.ensure_future(
        _delayed_flush(buf_key)
    )


async def _delayed_flush(buf_key: tuple) -> None:
    """Sleep then flush the quality group."""
    await asyncio.sleep(QUALITY_WAIT_SECS)
    await _flush_quality_group(buf_key)


if ACTIVE_CHANNELS:
    client.add_event_handler(
        _sniffer_handler,
        events.NewMessage(chats=list(ACTIVE_CHANNELS)),
    )


# ────────────────────────────────────────────────────────
#  Main Message Handler
# ────────────────────────────────────────────────────────
@client.on(events.NewMessage(incoming=True))
async def on_new_message(event):
    global batch_active, batch_links

    if event.message.text and event.message.text.startswith("/"):
        return
    if not (event.message.media and event.message.file):
        return

    chat_id    = event.chat_id
    message_id = event.id
    link       = f"http://{PROXY_HOST}:{PROXY_PORT}/dl/{chat_id}/{message_id}"
    fname      = event.message.file.name or "Unknown File"
    size_mb    = event.message.file.size / (1024 * 1024)

    if batch_active:
        batch_links.append(link)
        logger.info(f"Queued: {fname}")
        await event.reply(
            f"📥 **Added to Batch Queue**\n"
            f"└ `{fname}` ({size_mb:.2f} MB)\n"
            f"📊 Total: {len(batch_links)}",
            buttons=[[Button.inline("Copy Link", data=f"dl_direct_{chat_id}_{message_id}")]],
        )
        return

    logger.info(f"Received: {fname} ({size_mb:.2f} MB) — chat {chat_id}, msg {message_id}")

    # Option P: keyword filter
    fname_lower = fname.lower()
    if KEYWORD_BLOCK and any(kw in fname_lower for kw in KEYWORD_BLOCK):
        await event.reply(f"🚫 **Blocked** — `{fname}` matched keyword filter.\n└ Manual link: `{link}`")
        return
    if KEYWORD_ALLOW and not any(kw in fname_lower for kw in KEYWORD_ALLOW):
        await event.reply(f"⏭️ **Skipped** — `{fname}` not in allowed keywords.\n└ Manual link: `{link}`")
        return

    # Option O: duplicate guard
    if _is_duplicate(chat_id, message_id):
        return

    # Auto-trigger installed download manager immediately
    mgr, pushed = await auto_send(link)
    buttons = make_buttons(chat_id, message_id)

    if pushed:
        _sent = await event.reply(
            f"✅ **Sent to {MANAGER_LABELS.get(mgr, mgr)}**\n"
            f"└ `{fname}` ({size_mb:.2f} MB)",
            buttons=buttons,
        )
        # Option N: register for speed-stats reply
        download_registry[(chat_id, message_id)] = {
            "start":      time.monotonic(),
            "reply_chat": _sent.chat_id,
            "reply_to":   _sent.id,
            "fname":      fname,
            "size_bytes": event.message.file.size,
            "notified":   False,
        }
    else:
        await event.reply(
            f"📄 **File Ready**\n"
            f"└ `{fname}` ({size_mb:.2f} MB)\n\n"
            f"⚠️ No download manager detected — use the buttons below:",
            buttons=buttons,
        )


# ────────────────────────────────────────────────────────
#  Callback: Button Presses
# ────────────────────────────────────────────────────────
@client.on(events.CallbackQuery(data=re.compile(b"^dl_")))
async def on_callback_query(event):
    raw      = event.data.decode("utf-8")     # e.g. "dl_fdm_6161427514_521"
    parts    = raw.split("_", 3)              # ["dl", "fdm", "6161427514", "521"]
    mgr_id   = parts[1]                       # "fdm" / "idm" / "neat" / "direct"
    chat_id  = parts[2]
    msg_id   = parts[3]
    link     = f"http://{PROXY_HOST}:{PROXY_PORT}/dl/{chat_id}/{msg_id}"

    await event.answer()

    if mgr_id == "direct":
        # Just show the link for manual copy-paste
        await event.respond(
            f"📥 **Direct Download Link:**\n\n"
            f"`{link}`\n\n"
            f"_(Tap to copy, then paste into any download manager)_"
        )
        return

    # Attempt to trigger the specific manager
    label = MANAGER_LABELS.get(mgr_id, mgr_id.upper())

    if mgr_id not in INSTALLED_MANAGERS:
        await event.respond(
            f"⚠️ **{label} not found on this machine.**\n\n"
            f"Use the link below instead:\n`{link}`"
        )
        return

    ok = await trigger_manager(mgr_id, link)
    if ok:
        await event.respond(
            f"{label} **Download Started!**\n"
            f"└ Check your download manager — it should appear shortly.\n\n"
            f"_Backup link:_ `{link}`"
        )
    else:
        await event.respond(
            f"❌ **Failed to trigger {label}.**\n\n"
            f"Use the link manually:\n`{link}`"
        )


# ────────────────────────────────────────────────────────
#  Startup
# ────────────────────────────────────────────────────────
def kill_port_owner(port: int) -> bool:
    """Find and kill the process occupying the given port. Returns True if a PID was killed."""
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            # Match lines like:  TCP  127.0.0.1:8080  ...  LISTENING  1234
            if f":{port}" in line and ("LISTENING" in line or "ESTABLISHED" in line):
                parts = line.split()
                pid = int(parts[-1])
                if pid > 0:
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                                   capture_output=True, timeout=5)
                    logger.info(f"[PORT] Killed process PID {pid} that was using port {port}.")
                    return True
    except Exception as e:
        logger.warning(f"[PORT] Could not kill port owner: {e}")
    return False


async def main():
    global INSTALLED_MANAGERS

    logger.info("Starting Telegram FDM Proxy")

    # Detect download managers before connecting
    INSTALLED_MANAGERS = detect_managers()

    await client.start(bot_token=BOT_TOKEN)
    logger.info("Bot connected successfully")

    # Option M: register command menu so BotFather shows it in Telegram UI
    try:
        await client(SetBotCommandsRequest(
            scope=BotCommandScopeDefault(),
            lang_code="",
            commands=[
                BotCommand("start_batch",    "Start collecting files for batch download"),
                BotCommand("end_batch",      "Push collected batch to download manager"),
                BotCommand("channels",       "List currently watched channels"),
                BotCommand("add_channel",    "Watch a new channel for auto-downloads"),
                BotCommand("remove_channel", "Stop watching a channel"),
            ],
        ))
        logger.info("[BOT] Command menu registered via setMyCommands.")
    except Exception as _cmd_err:
        logger.warning(f"[BOT] Could not register command menu: {_cmd_err}")

    app = web.Application()
    app.router.add_get("/dl/{chat_id}/{message_id}", handle_download)

    runner = web.AppRunner(app)
    await runner.setup()

    # Use find_free_port() — no need to kill existing processes (from tg_fdm_proxy 1.py)
    port = find_free_port(PROXY_PORT)
    if port != PROXY_PORT:
        logger.warning(f"[PORT] {PROXY_PORT} in use, using {port} instead.")
    site = web.TCPSite(runner, PROXY_HOST, port)
    await site.start()

    print("\n" + "=" * 52)
    print("  Telegram FDM Proxy - Running")
    print("=" * 52)
    print(f"  HTTP Server : http://{PROXY_HOST}:{port}")
    if INSTALLED_MANAGERS:
        for mgr, path in INSTALLED_MANAGERS.items():
            short = os.path.basename(path)
            print(f"  {mgr.upper():<6} : {short}")
    else:
        print("  No download managers detected")
    if ALLOWED_EXT:
        print(f"  Filter  : {', '.join(sorted(ALLOWED_EXT))}")
    print(f"  Min Size: {MIN_FILE_SIZE_MB} MB")
    print("  Forward a Telegram file to your bot to start")
    print("=" * 52 + "\n")

    try:
        await client.run_until_disconnected()
    except KeyboardInterrupt:
        print("\nStopping proxy...")
    finally:
        await site.stop()
        await runner.cleanup()
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProxy stopped.")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)
