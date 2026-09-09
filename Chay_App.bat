@echo off
title Python AI Meeting Studio Server
echo ========================================================
echo   KHOI DONG HE THONG AI MEETING STUDIO & BIEN BAN CUOC HOP
echo ========================================================
echo.
cd /d "%~dp0"
echo Dang tai cac Model AI (Whisper + Vosk)... Vui long cho trong giay lat...
echo.
python web/app.py
pause
