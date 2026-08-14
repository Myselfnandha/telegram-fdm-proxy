import os
import shutil

# Paths
source = r"c:\Scripts\tg_fdm_proxy\launch_proxy.vbs"
startup_folder = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
destination = os.path.join(startup_folder, "TG_FDM_Proxy.vbs")

try:
    shutil.copy2(source, destination)
    print(f"Successfully installed to: {destination}")
except Exception as e:
    print(f"Error: {e}")
