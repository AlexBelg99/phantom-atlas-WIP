@echo off
rem Phantom Atlas launcher for Windows. Double-click to start.
rem First run: sets up a private Python environment in .venv (takes a minute).
setlocal
cd /d "%~dp0"
title Phantom Atlas

rem --- Find Python (the "py" launcher comes with the python.org installer) ---
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  python -c "import sys" >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo Python is not installed.
  echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
  start "" https://www.python.org/downloads/
  pause
  exit /b 1
)

rem --- Create the environment, or update it when requirements.txt changes ---
if not exist ".venv\Scripts\python.exe" (
  echo First run: setting up Phantom Atlas. This takes about a minute...
  %PY% -m venv .venv || goto :fail
)
fc /b requirements.txt ".venv\installed-requirements.txt" >nul 2>nul
if errorlevel 1 (
  echo Installing required packages...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt || goto :fail
  copy /y requirements.txt ".venv\installed-requirements.txt" >nul
)

rem --- API key file ---
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo.
  echo A file called .env has opened in Notepad.
  echo Replace your-fal-api-key-here with your fal.ai key, save, close Notepad,
  echo then double-click Phantom Atlas again.
  notepad ".env"
  pause
  exit /b 0
)

echo Starting Phantom Atlas. Your browser will open in a moment.
".venv\Scripts\python.exe" app\server.py %*
pause
exit /b 0

:fail
echo.
echo Setup failed. Scroll up for the error, or send a screenshot of this window.
pause
exit /b 1
