@echo off
echo ============================================
echo   Commercial Override
echo ============================================
echo.
python -m pip install flask --quiet
echo.
echo Starting... your browser will open automatically.
echo Press Ctrl+C to stop.
echo.
python server.py
echo.
echo --- Server stopped ---
pause
