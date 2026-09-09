@echo off
title AI Meeting Studio - Chay Web Offline 1-Click
echo ========================================================
echo   AI MEETING STUDIO - GIAO DIỆN WEB OFFLINE 1-CLICK
echo ========================================================
echo.
echo 1. Dang khoi dong Server Python AI ngam...
start "AI Server" python web/app.py
echo.
echo 2. Vui long cho 5 giay de mo hinh AI PhoWhisper va Vosk nap xong...
timeout /t 5 >nul
echo.
echo 3. Dang tu dong mo giao dien Web...
start "" "http://localhost:8000/screen"
echo.
echo ========================================================
echo   HE THONG DA KHOI DONG THANH CONG!
echo   Ban co the su dung giao dien Web truc tiep tren Chrome.
echo ========================================================
echo.
