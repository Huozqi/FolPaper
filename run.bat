@echo off
setlocal
cd /d "%~dp0"

echo Starting Literature Management System...
echo Please keep this window open. Closing it will stop the service.
echo.

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

rem Start Flask App
start /b "" "%PYTHON_EXE%" app.py

rem Wait 2 seconds for service to start
timeout /t 2 /nobreak >nul

rem Open default browser
start http://127.0.0.1:5000

echo Service started. Opened http://127.0.0.1:5000 in your browser.
pause

