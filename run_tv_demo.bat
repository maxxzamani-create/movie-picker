@echo off
echo ============================================
echo   Commercial Override - TV Demo
echo ============================================
echo.
echo Getting the latest version...
git pull origin main
echo.
python -m pip install flask --quiet
echo.
echo Starting the demo...
echo Your browser will open to the TV in a few seconds.
echo Press Ctrl+C in this window to stop.
echo.
set PORT=5050
start "" /min cmd /c "timeout /t 4 >nul && start "" http://localhost:5050/co/"
python server.py
echo.
echo --- Server stopped ---
pause
