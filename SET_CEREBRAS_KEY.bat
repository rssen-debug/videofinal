@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title VIDEOFINAL - Cerebras Setup
color 0F
echo.
echo ================================================================
echo                 VIDEOFINAL CEREBRAS SETUP
echo ================================================================
echo Enter a NEW Cerebras API key.
echo Do NOT put the key in GitHub, source files, screenshots or chat.
echo.
set /p "CEREBRAS_API_KEY=Paste NEW Cerebras API key: "
if not defined CEREBRAS_API_KEY (
  echo No key entered.
  pause
  exit /b 1
)
setx CEREBRAS_API_KEY "%CEREBRAS_API_KEY%" >nul
echo.
echo Saved to your Windows user environment.
echo Testing the current CMD session:
python videofinal.py --test-llm
echo.
echo Start a new CMD with START_VIDEOFINAL.bat for the clean 3-click flow.
pause
