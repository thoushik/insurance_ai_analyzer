@echo off
title InsuranceAI Server (Do Not Close)
cd /d "%~dp0"
echo Activating Virtual Environment...
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

echo Starting Application on Port 5000...
echo.
echo ******************************************************
echo * Local Access: http://127.0.0.1:5000
echo * LAN Access:   http://0.0.0.0:5000 (Try your IP)
echo ******************************************************
echo.

python -m app.main

pause
