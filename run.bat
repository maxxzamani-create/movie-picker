@echo off
echo Starting Movie Rando (Web Edition)...
echo.
python -m pip install flask --quiet
echo.
echo Open your browser to: http://localhost:5000
echo Press Ctrl+C to stop the server.
echo.
python server.py
echo.
echo --- Server stopped ---
pause
