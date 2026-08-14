@echo off
title TG-FDM Proxy Watchdog
echo ============================================
echo  Telegram FDM Proxy - Watchdog Active
echo  Press Ctrl+C to stop permanently.
echo ============================================

:loop
echo [%date% %time%] Starting proxy...
python tg_fdm_proxy.py
echo [%date% %time%] Proxy exited (code %ERRORLEVEL%). Restarting in 3 s... >> watchdog.log
echo [%date% %time%] Proxy exited. Restarting in 3 seconds...
timeout /t 3 /nobreak > nul
goto loop
