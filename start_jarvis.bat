@echo off
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
title J.A.R.V.I.S. Desktop Assistant
color 0B

cd /d "%~dp0"

echo ================================================================
echo   J.A.R.V.I.S. -- Neural Voice Desktop Assistant
echo   Manthan AI Hackathon 2026
echo ================================================================
echo.

set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"

if exist "%OLLAMA_EXE%" (
    echo [*] Starting Ollama local AI engine...
    start /B "" "%OLLAMA_EXE%" serve >nul 2>&1
    ping 127.0.0.1 -n 4 >nul
    echo [OK] Ollama ready.
) else (
    echo [!] Ollama not found - using Gemini fallback.
)

echo.
echo [*] Launching JARVIS Core...
echo.

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0main.py"
) else (
    "%~dp0.venv-1\Scripts\python.exe" "%~dp0main.py"
)

echo.
echo JARVIS has shut down.
pause