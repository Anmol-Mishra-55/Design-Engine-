@echo off
echo Fixing Authentication Issue...
echo.

echo Step 1: Stopping old server...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *" 2>nul
timeout /t 2 /nobreak >nul

echo Step 2: Starting fresh server...
cd backend
start "FastAPI Server" python start_server.py

echo.
echo Server is starting...
echo Wait 10 seconds, then test at: http://localhost:8000/docs
echo.
echo Login with:
echo   Username: admin
echo   Password: bhiv2024
echo.
pause
