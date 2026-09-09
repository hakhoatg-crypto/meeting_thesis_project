@echo off
title Tao Link Public Cho Phap Moi Nguoi Truy Cap Web
echo ========================================================
echo   TAO LINK PUBLIC INTERNET (NGROK HTTPS TUNNEL)
echo ========================================================
echo.
taskkill /f /im ngrok.exe >nul 2>&1
echo Dang mo cong public HTTPS cho he thong AI Meeting Studio...
echo Vui long giu cua so nay mo trong suot qua trinh su dung Web.
echo.
ngrok http 8000
pause
