@echo off
setlocal
cd /d "%~dp0"

echo Starting FolPaper...

rem 检测可用 Python
set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" --version >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=.venv\Scripts\python.exe"
)

start /b "" "%PYTHON_EXE%" app.py
