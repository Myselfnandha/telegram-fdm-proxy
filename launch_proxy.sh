#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo " Telegram FDM Proxy - Single Run Launcher"
echo "============================================"

# Perform startup cleanup (release DB locks)
echo "Performing startup cleanup..."
systemctl --user stop tg-fdm-proxy.service || true

MY_PID=$$
for pid in $(pgrep -f "watchdog.sh" ; pgrep -f "launch_proxy.sh"); do
    if [ -n "$pid" ] && [ "$pid" != "$MY_PID" ]; then
        echo "Stopping other running launcher script (PID: $pid)..."
        kill -9 "$pid" 2>/dev/null || true
    fi
done

for pid in $(pgrep -f "tg_fdm_proxy.py"); do
    if [ -n "$pid" ] && [ "$pid" != "$MY_PID" ]; then
        echo "Killing running tg_fdm_proxy.py process (PID: $pid)..."
        kill -9 "$pid" 2>/dev/null || true
    fi
done

# Ensure logs directory exists
mkdir -p Logs

echo "Starting proxy in the foreground..."
./.venv/bin/python tg_fdm_proxy.py
