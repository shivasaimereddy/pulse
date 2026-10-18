@echo off
cd /d "%~dp0.."
python scripts\build_website.py
if errorlevel 1 (
    pause
    exit /b 1
)
start "" http://127.0.0.1:8787/
python -m http.server 8787 --bind 127.0.0.1 --directory website\dist
