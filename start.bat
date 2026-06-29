@echo off
chcp 65001 > nul
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
    echo Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

.venv\Scripts\python.exe main.py
pause
