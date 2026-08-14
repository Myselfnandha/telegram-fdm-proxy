@echo off
title Build Telegram FDM Proxy (Windows EXE)
cd /d "%~dp0\.."

echo ======================================================
echo  Building Standalone Windows Executable with PyInstaller
echo ======================================================

if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

echo Installing build dependencies...
call .venv\Scripts\pip install --quiet --upgrade pip
call .venv\Scripts\pip install --quiet pyinstaller pillow pystray telethon aiohttp python-dotenv psutil cryptg

if not exist "build" mkdir build
if not exist "dist" mkdir dist

echo Compiling Windows executable (tg-fdm-proxy.exe)...
call .venv\Scripts\pyinstaller --clean windows\tg_fdm_proxy.spec

if exist "dist\tg-fdm-proxy.exe" (
    echo ======================================================
    echo  [SUCCESS] Build complete!
    echo  Binary: dist\tg-fdm-proxy.exe
    echo ======================================================
) else (
    echo [ERROR] Build failed.
)
pause
