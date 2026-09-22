@echo off
setlocal
cd /d "%~dp0"
echo VideoFinal Cerebras setup
echo Enter a NEW Cerebras API key. Do not paste it into GitHub.
echo.
set /p CEREBRAS_API_KEY=Cerebras API key: 
if "%CEREBRAS_API_KEY%"=="" exit /b 1
setx CEREBRAS_API_KEY "%CEREBRAS_API_KEY%" >nul
set "CEREBRAS_API_KEY=%CEREBRAS_API_KEY%"
echo.
python videofinal.py --test-llm
echo.
echo Saved for future CMD sessions. Open a new CMD after setx if needed.
pause
