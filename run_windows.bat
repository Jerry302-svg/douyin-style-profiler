@echo off
setlocal
set ROOT=%~dp0
set PY=%ROOT%runtime\python\python.exe
set PLAYWRIGHT_BROWSERS_PATH=%ROOT%runtime\ms-playwright
set MODELSCOPE_CACHE=%ROOT%models\modelscope
if not exist "%PY%" (
  echo Python runtime not found. Please run tools\bootstrap_windows.ps1 first.
  exit /b 1
)
"%PY%" -m douyin_style_profiler %*
