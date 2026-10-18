@echo off
cd /d "%~dp0.."
if not exist .build-env\Scripts\python.exe python -m venv .build-env
if errorlevel 1 exit /b 1
.build-env\Scripts\python.exe -m pip install -r packaging\requirements-build.txt
if errorlevel 1 exit /b 1
.build-env\Scripts\python.exe scripts\build_release.py
if errorlevel 1 exit /b 1
pause
