import os
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_CONTENT = f"""[Unit]
Description=Telegram FDM Proxy Bot
After=network.target

[Service]
Type=simple
WorkingDirectory={SCRIPT_DIR}
ExecStart={os.path.join(SCRIPT_DIR, '.venv/bin/python')} {os.path.join(SCRIPT_DIR, 'tg_fdm_proxy.py')}
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
"""

systemd_dir = os.path.expanduser("~/.config/systemd/user")
os.makedirs(systemd_dir, exist_ok=True)
service_path = os.path.join(systemd_dir, "tg-fdm-proxy.service")

try:
    with open(service_path, "w") as f:
        f.write(SERVICE_CONTENT)
    print(f"Created systemd user service at: {service_path}")
    
    # Reload systemd user daemon
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    # Enable service
    subprocess.run(["systemctl", "--user", "enable", "tg-fdm-proxy.service"], check=True)
    # Start service
    subprocess.run(["systemctl", "--user", "start", "tg-fdm-proxy.service"], check=True)
    
    print("\nSuccessfully installed and started tg-fdm-proxy systemd user service!")
    print("Commands to manage the service:")
    print("  Check status : systemctl --user status tg-fdm-proxy")
    print("  View logs    : journalctl --user -u tg-fdm-proxy -f")
    print("  Stop proxy   : systemctl --user stop tg-fdm-proxy")
    print("  Start proxy  : systemctl --user start tg-fdm-proxy")
except Exception as e:
    print(f"Error installing service: {e}")
