#!/usr/bin/env python3
import os
import sys
import shutil

def install_windows_startup():
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        print("[ERROR] APPDATA environment variable not found.")
        return

    startup_folder = os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\Startup")
    os.makedirs(startup_folder, exist_ok=True)
    
    # Check if executable exists or use python script launcher
    exe_path = os.path.join(script_dir, "dist", "tg-fdm-proxy.exe")
    vbs_path = os.path.join(startup_folder, "TG_FDM_Proxy.vbs")

    if os.path.isfile(exe_path):
        target_cmd = f'"{exe_path}" start --tray'
    else:
        py_exe = sys.executable
        script_path = os.path.join(script_dir, "tg_fdm_proxy.py")
        target_cmd = f'"{py_exe}" "{script_path}" start --tray'

    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "{script_dir}"
WshShell.Run "{target_cmd}", 0, False
'''
    try:
        with open(vbs_path, "w", encoding="utf-8") as f:
            f.write(vbs_content)
        print(f"[OK] Successfully installed Windows Startup launcher to:\n  {vbs_path}")
    except Exception as e:
        print(f"[ERROR] Failed to install startup launcher: {e}")

if __name__ == "__main__":
    install_windows_startup()
