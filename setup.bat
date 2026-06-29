@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo [1/3] Removing old virtual environment (if any)...
if exist .venv (
    rmdir /s /q .venv
)

echo [2/3] Creating virtual environment...
python -m venv .venv
if errorlevel 1 (
    echo ERROR: Failed to create venv. Make sure Python is installed and in PATH.
    pause
    exit /b 1
)

echo [3/3] Installing dependencies...
.venv\Scripts\pip.exe install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo Done! Run start.bat to launch the bot.
pause
