@echo off
setlocal
cd /d "%~dp0"
title Morocco Data Dashboard
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m streamlit run app.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
echo The dashboard could not start. Read the error above.
echo Python 3.12 and an internet connection are required.
pause
exit /b 1
