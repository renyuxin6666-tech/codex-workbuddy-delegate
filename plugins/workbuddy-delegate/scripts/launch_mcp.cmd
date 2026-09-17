@echo off
setlocal
set "PYTHONUTF8=1"
where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.10 or newer is required. 1>&2
  exit /b 1
)
python -X utf8 "%~dp0mcp_server.py"
