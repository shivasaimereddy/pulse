@echo off
cd /d "%~dp0.."
python -m pulse --choose-database
if errorlevel 1 pause
