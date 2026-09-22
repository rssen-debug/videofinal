@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title VIDEOFINAL 2026 - Creator Studio
color 0F
echo.
echo ================================================================
echo                     VIDEOFINAL 2026
echo             AUTOPILOT CREATOR STUDIO - WINDOWS
echo ================================================================
echo.
for /f "tokens=2,*" %%A in ('reg query "HKCU\Environment" /v CEREBRAS_API_KEY 2^>nul ^| findstr /I "CEREBRAS_API_KEY"') do set "CEREBRAS_API_KEY=%%B"
if defined CEREBRAS_API_KEY (
  echo LLM: Cerebras key detected from Windows user environment.
) else (
  echo LLM: NOT CONFIGURED
  echo Run SET_CEREBRAS_KEY.bat once with a NEW key.
)
echo.
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 videofinal.py
) else (
  python videofinal.py
)
echo.
echo ================================================================
echo VideoFinal exited. Final MP4 files are under youtube2026\
echo ================================================================
pause
