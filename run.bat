@echo off
rem Starts PhoneLink: the built exe if present, otherwise from source (creates the venv on first run).
cd /d "%~dp0"
if exist dist\PhoneLink.exe (
  start "" "dist\PhoneLink.exe"
  exit /b 0
)
if not exist .venv\Scripts\pythonw.exe (
  py -m venv .venv && .venv\Scripts\python -m pip install -r requirements.txt
)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py"
