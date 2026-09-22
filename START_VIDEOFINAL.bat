@echo off
setlocal
cd /d "%~dp0"
echo.
echo ================================================================
echo VIDEOFINAL 2026
echo ================================================================
echo.
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 videofinal.py
) else (
  python videofinal.py
)
echo.
pause
