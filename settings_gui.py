#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram FDM Proxy - Settings & Configuration GUI
Modern desktop configuration window for Arch Linux.
"""

import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any

def get_config_path() -> str:
    # 1. Local .env in CWD
    if os.path.isfile(os.path.join(os.getcwd(), ".env")):
        return os.path.join(os.getcwd(), ".env")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.isfile(os.path.join(script_dir, ".env")):
        return os.path.join(script_dir, ".env")

    if sys.platform != "win32":
        xdg_config = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        app_dir = os.path.join(xdg_config, "tg-fdm-proxy")
    else:
        app_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "tg-fdm-proxy")
    
    os.makedirs(app_dir, exist_ok=True)
    return os.path.join(app_dir, ".env")

def load_env_dict(path: str) -> Dict[str, str]:
    config = {}
    if not os.path.isfile(path):
        return config
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                # Strip trailing inline comments if any
                val = val.split(" #")[0].strip()
                config[key.strip()] = val
    return config

def save_env_dict(path: str, config: Dict[str, str]) -> None:
    # Read existing file to preserve comments/order if possible
    lines = []
    keys_written = set()
    
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    key = stripped.split("=", 1)[0].strip()
                    if key in config:
                        lines.append(f"{key}={config[key]}\n")
                        keys_written.add(key)
                        continue
                lines.append(line)

    for k, v in config.items():
        if k not in keys_written:
            lines.append(f"{k}={v}\n")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)

class SettingsWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Telegram FDM Proxy — Settings")
        self.root.geometry("640x720")
        self.root.minsize(580, 600)

        # Style configuration (Modern Dark Theme)
        self.bg_color = "#1e1e2e"
        self.card_bg = "#252538"
        self.fg_color = "#cdd6f4"
        self.accent_color = "#89b4fa"
        self.accent_hover = "#b4befe"
        self.input_bg = "#313244"
        self.input_fg = "#ffffff"
        self.btn_save_bg = "#a6e3a1"
        self.btn_save_fg = "#11111b"

        self.root.configure(bg=self.bg_color)
        self.config_path = get_config_path()
        self.config = load_env_dict(self.config_path)

        self._init_styles()
        self._build_ui()

    def _init_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        style.configure(".", background=self.bg_color, foreground=self.fg_color, font=("Sans", 10))
        style.configure("TNotebook", background=self.bg_color, borderwidth=0)
        style.configure("TNotebook.Tab", background=self.card_bg, foreground=self.fg_color, padding=[16, 8], font=("Sans", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", self.accent_color)], foreground=[("selected", "#11111b")])
        style.configure("TCombobox", fieldbackground=self.input_bg, background=self.card_bg, foreground=self.input_fg)
        style.map("TCombobox", fieldbackground=[("readonly", self.input_bg)])

    def _build_ui(self):
        # Header banner
        header = tk.Frame(self.root, bg=self.card_bg, height=60, padx=20, pady=12)
        header.pack(fill="x")

        title_lbl = tk.Label(header, text="⚙️ Telegram FDM Proxy Settings", font=("Sans", 14, "bold"), bg=self.card_bg, fg="#ffffff")
        title_lbl.pack(side="left")

        path_lbl = tk.Label(header, text=f"Config: {os.path.basename(self.config_path)}", font=("Sans", 9), bg=self.card_bg, fg="#a6adc8")
        path_lbl.pack(side="right")

        # Notebook tabs container
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=16, pady=12)

        # Tab 1: General & Notifications
        tab_general = tk.Frame(notebook, bg=self.bg_color, padx=16, pady=16)
        notebook.add(tab_general, text="  General & Notifications  ")
        self._build_general_tab(tab_general)

        # Tab 2: Telegram API
        tab_api = tk.Frame(notebook, bg=self.bg_color, padx=16, pady=16)
        notebook.add(tab_api, text="  Telegram Credentials  ")
        self._build_api_tab(tab_api)

        # Tab 3: Filters & Channels
        tab_filters = tk.Frame(notebook, bg=self.bg_color, padx=16, pady=16)
        notebook.add(tab_filters, text="  Filters & Quality  ")
        self._build_filters_tab(tab_filters)

        # Bottom Action Bar
        bottom_bar = tk.Frame(self.root, bg=self.card_bg, padx=20, pady=12)
        bottom_bar.pack(fill="x", side="bottom")

        btn_cancel = tk.Button(
            bottom_bar, text="Cancel", font=("Sans", 10), bg="#45475a", fg="#ffffff",
            activebackground="#585b70", activeforeground="#ffffff", relief="flat", padx=16, pady=6,
            command=self.root.destroy
        )
        btn_cancel.pack(side="left")

        btn_restart = tk.Button(
            bottom_bar, text="💾 Save & Restart Service", font=("Sans", 10, "bold"),
            bg=self.accent_color, fg="#11111b", activebackground=self.accent_hover,
            relief="flat", padx=16, pady=6, command=lambda: self.save_settings(restart=True)
        )
        btn_restart.pack(side="right", padx=(8, 0))

        btn_save = tk.Button(
            bottom_bar, text="💾 Save", font=("Sans", 10, "bold"),
            bg=self.btn_save_bg, fg=self.btn_save_fg, activebackground="#94e2d5",
            relief="flat", padx=16, pady=6, command=lambda: self.save_settings(restart=False)
        )
        btn_save.pack(side="right")

    def _create_field(self, parent, label_text: str, default_val: str = "", is_password: bool = False):
        lbl = tk.Label(parent, text=label_text, font=("Sans", 10, "bold"), bg=self.bg_color, fg=self.fg_color)
        lbl.pack(anchor="w", pady=(8, 2))
        
        entry = tk.Entry(
            parent, font=("Sans", 10), bg=self.input_bg, fg=self.input_fg,
            insertbackground="#ffffff", relief="flat", highlightthickness=1,
            highlightbackground="#45475a", highlightcolor=self.accent_color
        )
        entry.insert(0, default_val)
        if is_password:
            entry.config(show="•")
        entry.pack(fill="x", ipady=4)
        return entry

    def _build_general_tab(self, parent):
        # Notifications Card
        card_notif = tk.LabelFrame(parent, text=" 🔔 Desktop Notifications ", font=("Sans", 10, "bold"), bg=self.bg_color, fg=self.accent_color, padx=14, pady=10)
        card_notif.pack(fill="x", pady=(0, 12))

        self.var_enable_notif = tk.BooleanVar(value=self.config.get("ENABLE_NOTIFICATIONS", "true").lower() in ("true", "1", "yes"))
        chk_notif = tk.Checkbutton(
            card_notif, text="Enable Desktop Notifications (notify-send)",
            variable=self.var_enable_notif, font=("Sans", 10), bg=self.bg_color, fg="#ffffff",
            selectcolor=self.input_bg, activebackground=self.bg_color, activeforeground="#ffffff"
        )
        chk_notif.pack(anchor="w", pady=4)

        lbl_mode = tk.Label(card_notif, text="Notification Frequency / Mode:", font=("Sans", 9), bg=self.bg_color, fg=self.fg_color)
        lbl_mode.pack(anchor="w", pady=(6, 2))

        self.var_notif_mode = tk.StringVar(value=self.config.get("NOTIFICATION_MODE", "downloads_only"))
        modes = [
            ("downloads_only", "Downloads Only (Alert on download trigger, no flood)"),
            ("all", "All Events (Startup, Stop, Batch, Downloads)"),
            ("none", "Silent (No notifications)"),
        ]
        for val, desc in modes:
            rb = tk.Radiobutton(
                card_notif, text=desc, value=val, variable=self.var_notif_mode,
                font=("Sans", 9), bg=self.bg_color, fg="#cdd6f4",
                selectcolor=self.input_bg, activebackground=self.bg_color, activeforeground="#ffffff"
            )
            rb.pack(anchor="w", padx=10, pady=2)

        # Download Manager Card
        card_dm = tk.LabelFrame(parent, text=" 🚀 Download Manager & Network ", font=("Sans", 10, "bold"), bg=self.bg_color, fg=self.accent_color, padx=14, pady=10)
        card_dm.pack(fill="x", pady=6)

        lbl_mgr = tk.Label(card_dm, text="Preferred Download Manager:", font=("Sans", 9), bg=self.bg_color, fg=self.fg_color)
        lbl_mgr.pack(anchor="w", pady=(4, 2))

        self.cb_manager = ttk.Combobox(
            card_dm, state="readonly",
            values=["Auto-Detect (FDM → aria2 → NeatDM)", "fdm", "aria2", "persepolis", "kget", "neat", "direct"]
        )
        curr_mgr = self.config.get("PREFERRED_MANAGER", "Auto-Detect (FDM → aria2 → NeatDM)")
        self.cb_manager.set(curr_mgr)
        self.cb_manager.pack(fill="x", pady=(0, 8), ipady=3)

        # Proxy Host and Port in one line
        f_net = tk.Frame(card_dm, bg=self.bg_color)
        f_net.pack(fill="x", pady=4)

        f_host = tk.Frame(f_net, bg=self.bg_color)
        f_host.pack(side="left", fill="x", expand=True, padx=(0, 8))
        tk.Label(f_host, text="HTTP Proxy Host:", font=("Sans", 9), bg=self.bg_color, fg=self.fg_color).pack(anchor="w")
        self.entry_host = tk.Entry(f_host, font=("Sans", 10), bg=self.input_bg, fg=self.input_fg, insertbackground="#fff", relief="flat")
        self.entry_host.insert(0, self.config.get("PROXY_HOST", "127.0.0.1"))
        self.entry_host.pack(fill="x", ipady=4)

        f_port = tk.Frame(f_net, bg=self.bg_color)
        f_port.pack(side="right", fill="x", expand=True)
        tk.Label(f_port, text="HTTP Proxy Port:", font=("Sans", 9), bg=self.bg_color, fg=self.fg_color).pack(anchor="w")
        self.entry_port = tk.Entry(f_port, font=("Sans", 10), bg=self.input_bg, fg=self.input_fg, insertbackground="#fff", relief="flat")
        self.entry_port.insert(0, self.config.get("PROXY_PORT", "8080"))
        self.entry_port.pack(fill="x", ipady=4)

    def _build_api_tab(self, parent):
        tk.Label(parent, text="Configure your Telegram Bot and API credentials.", font=("Sans", 9), bg=self.bg_color, fg="#a6adc8").pack(anchor="w", pady=(0, 10))

        self.entry_api_id = self._create_field(parent, "API ID:", self.config.get("API_ID", ""))
        self.entry_api_hash = self._create_field(parent, "API HASH:", self.config.get("API_HASH", ""), is_password=True)
        self.entry_bot_token = self._create_field(parent, "BOT TOKEN:", self.config.get("BOT_TOKEN", ""), is_password=True)

        self.var_show_pass = tk.BooleanVar(value=False)
        def toggle_pass():
            show_char = "" if self.var_show_pass.get() else "•"
            self.entry_api_hash.config(show=show_char)
            self.entry_bot_token.config(show=show_char)

        chk_show = tk.Checkbutton(
            parent, text="Show Secrets", variable=self.var_show_pass,
            font=("Sans", 9), bg=self.bg_color, fg=self.fg_color, selectcolor=self.input_bg,
            activebackground=self.bg_color, activeforeground="#ffffff", command=toggle_pass
        )
        chk_show.pack(anchor="w", pady=8)

        # Help info
        info_card = tk.Frame(parent, bg=self.card_bg, padx=12, pady=10)
        info_card.pack(fill="x", pady=12)
        tk.Label(
            info_card,
            text="💡 Tip: API ID and Hash can be obtained from https://my.telegram.org\n"
                 "Bot Token can be created and managed via @BotFather in Telegram.",
            font=("Sans", 8), bg=self.card_bg, fg="#bac2de", justify="left"
        ).pack(anchor="w")

    def _build_filters_tab(self, parent):
        f_num = tk.Frame(parent, bg=self.bg_color)
        f_num.pack(fill="x")

        f_size = tk.Frame(f_num, bg=self.bg_color)
        f_size.pack(side="left", fill="x", expand=True, padx=(0, 8))
        tk.Label(f_size, text="Min File Size (MB):", font=("Sans", 9), bg=self.bg_color, fg=self.fg_color).pack(anchor="w")
        self.entry_min_size = tk.Entry(f_size, font=("Sans", 10), bg=self.input_bg, fg=self.input_fg, insertbackground="#fff", relief="flat")
        self.entry_min_size.insert(0, self.config.get("MIN_FILE_SIZE_MB", "50"))
        self.entry_min_size.pack(fill="x", ipady=4)

        f_wait = tk.Frame(f_num, bg=self.bg_color)
        f_wait.pack(side="right", fill="x", expand=True)
        tk.Label(f_wait, text="Quality Wait Window (Secs):", font=("Sans", 9), bg=self.bg_color, fg=self.fg_color).pack(anchor="w")
        self.entry_wait = tk.Entry(f_wait, font=("Sans", 10), bg=self.input_bg, fg=self.input_fg, insertbackground="#fff", relief="flat")
        self.entry_wait.insert(0, self.config.get("QUALITY_WAIT_SECS", "30"))
        self.entry_wait.pack(fill="x", ipady=4)

        self.entry_ext = self._create_field(parent, "Allowed Extensions (comma-separated):", self.config.get("ALLOWED_EXT", ""))
        self.entry_kw_block = self._create_field(parent, "Block Keywords (comma-separated):", self.config.get("KEYWORD_BLOCK", ""))
        self.entry_kw_allow = self._create_field(parent, "Allow Keywords (comma-separated):", self.config.get("KEYWORD_ALLOW", ""))
        self.entry_channels = self._create_field(parent, "Target Channels (comma-separated IDs/@usernames):", self.config.get("TARGET_CHANNELS", ""))

    def save_settings(self, restart: bool = False):
        new_config = dict(self.config)
        
        # General & Notifications
        new_config["ENABLE_NOTIFICATIONS"] = "true" if self.var_enable_notif.get() else "false"
        new_config["NOTIFICATION_MODE"] = self.var_notif_mode.get()
        new_config["PREFERRED_MANAGER"] = self.cb_manager.get()
        new_config["PROXY_HOST"] = self.entry_host.get().strip() or "127.0.0.1"
        new_config["PROXY_PORT"] = self.entry_port.get().strip() or "8080"

        # Telegram API
        if self.entry_api_id.get().strip():
            new_config["API_ID"] = self.entry_api_id.get().strip()
        if self.entry_api_hash.get().strip():
            new_config["API_HASH"] = self.entry_api_hash.get().strip()
        if self.entry_bot_token.get().strip():
            new_config["BOT_TOKEN"] = self.entry_bot_token.get().strip()

        # Filters
        new_config["MIN_FILE_SIZE_MB"] = self.entry_min_size.get().strip() or "50"
        new_config["QUALITY_WAIT_SECS"] = self.entry_wait.get().strip() or "30"
        new_config["ALLOWED_EXT"] = self.entry_ext.get().strip()
        new_config["KEYWORD_BLOCK"] = self.entry_kw_block.get().strip()
        new_config["KEYWORD_ALLOW"] = self.entry_kw_allow.get().strip()
        new_config["TARGET_CHANNELS"] = self.entry_channels.get().strip()

        try:
            save_env_dict(self.config_path, new_config)
            
            if restart and sys.platform != "win32":
                subprocess.run(["systemctl", "--user", "restart", "tg-fdm-proxy.service"], capture_output=True)
                messagebox.showinfo("Saved", "Settings saved and tg-fdm-proxy service restarted successfully!")
            else:
                messagebox.showinfo("Saved", "Settings successfully saved to .env!")
            
            self.root.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

def open_settings_gui():
    """Launch the settings GUI window."""
    try:
        root = tk.Tk()
        app = SettingsWindow(root)
        root.mainloop()
    except Exception as e:
        print(f"Failed to open graphical settings window ({e}). Falling back to text editor...")
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "nano"
        os.system(f'{editor} "{get_config_path()}"')

if __name__ == "__main__":
    open_settings_gui()
