@echo off
echo Starting Literature Management System...
echo Please keep this window open. Closing it will stop the service.
echo.

rem Start Flask App
start /b .\venv_new\Scripts\python app.py

rem Wait 2 seconds for service to start
timeout /t 2 /nobreak >nul

rem Open default browser
start http://127.0.0.1:5000

echo Service started. Opened http://127.0.0.1:5000 in your browser.
pause

