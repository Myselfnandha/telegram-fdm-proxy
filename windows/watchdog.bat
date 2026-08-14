@echo off
title TG-FDM Proxy Watchdog
cd /d "%~dp0\.."

echo ============================================
echo  Telegram FDM Proxy - Watchdog Active
echo  Press Ctrl+C to stop permanently.
echo ============================================

:loop
echo [%date% %time%] Starting proxy...
python tg_fdm_proxy.py start --tray
echo [%date% %time%] Proxy exited (code %ERRORLEVEL%). Restarting in 3 s... >> watchdog.log
echo [%date% %time%] Proxy exited. Restarting in 3 seconds...
timeout /t 3 /nobreak > nul
goto loop
