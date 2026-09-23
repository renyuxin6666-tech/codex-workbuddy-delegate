@echo off
setlocal
set "PYTHONUTF8=1"
if defined WORKBUDDY_DELEGATE_CONFIG if not defined WORKBUDDY_DELEGATE_STATE_DIR goto partial_paths
if defined WORKBUDDY_DELEGATE_STATE_DIR if not defined WORKBUDDY_DELEGATE_CONFIG goto partial_paths
if not defined WORKBUDDY_DELEGATE_CONFIG if defined PLUGIN_DATA set "WORKBUDDY_DELEGATE_CONFIG=%PLUGIN_DATA%\config.json"
if not defined WORKBUDDY_DELEGATE_STATE_DIR if defined PLUGIN_DATA set "WORKBUDDY_DELEGATE_STATE_DIR=%PLUGIN_DATA%\runtime"
if not defined WORKBUDDY_DELEGATE_CONFIG if defined CLAUDE_PLUGIN_DATA set "WORKBUDDY_DELEGATE_CONFIG=%CLAUDE_PLUGIN_DATA%\config.json"
if not defined WORKBUDDY_DELEGATE_STATE_DIR if defined CLAUDE_PLUGIN_DATA set "WORKBUDDY_DELEGATE_STATE_DIR=%CLAUDE_PLUGIN_DATA%\runtime"
if not defined WORKBUDDY_DELEGATE_CONFIG (
  echo WorkBuddy Delegate config path is missing. Set PLUGIN_DATA or WORKBUDDY_DELEGATE_CONFIG. 1>&2
  exit /b 2
)
if not defined WORKBUDDY_DELEGATE_STATE_DIR (
  echo WorkBuddy Delegate state path is missing. Set PLUGIN_DATA or WORKBUDDY_DELEGATE_STATE_DIR. 1>&2
  exit /b 2
)
where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.10 or newer is required. 1>&2
  exit /b 1
)
python -X utf8 "%~dp0mcp_server.py"
exit /b %errorlevel%
:partial_paths
echo WorkBuddy Delegate requires both explicit config and state paths. 1>&2
exit /b 2
