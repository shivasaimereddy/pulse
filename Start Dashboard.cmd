@echo off
cd /d "%~dp0"
python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/session', timeout=2)" >nul 2>&1
if not errorlevel 1 (
    start "" http://127.0.0.1:8765
    exit /b
)
start "" http://127.0.0.1:8765
python -m pulse
