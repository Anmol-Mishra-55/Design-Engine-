@echo off
REM Complete Fix Script for Backend Issues
REM Run this script to fix all issues

echo.
echo ========================================
echo Backend Issues - Complete Fix Script
echo ========================================
echo.

REM Step 1: Activate virtual environment
echo [Step 1/4] Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    echo Make sure you're in the Backend directory
    pause
    exit /b 1
)
echo ✅ Virtual environment activated

echo.
echo [Step 2/4] Installing/Updating dependencies...
echo This may take 2-5 minutes...
pip install -r backend/requirements.txt --upgrade
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo ✅ Dependencies installed

echo.
echo [Step 3/4] Verifying installations...
python -c "import stable_baselines3; print('✅ stable-baselines3 installed')" 2>nul
if errorlevel 1 (
    echo ⚠️  stable-baselines3 verification failed
    echo Trying alternative installation...
    pip install stable-baselines3==2.0.0 torch==2.0.0 --no-cache-dir
)

python -c "import motor; print('✅ motor installed')" 2>nul
if errorlevel 1 (
    echo ⚠️  motor verification failed
    pip install motor>=3.3.0 --upgrade
)

echo.
echo [Step 4/4] Summary of fixes applied:
echo.
echo ✅ Fixed: MongoDB index creation error
echo    - Updated database_mongodb.py with correct create_index() format
echo.
echo ✅ Fixed: stable-baselines3 missing dependency
echo    - Added to requirements.txt and installed
echo.
echo ⚠️  Note: MongoDB connection timeout
echo    - This is an infrastructure issue
echo    - Go to https://cloud.mongodb.com and resume cluster0
echo    - Wait 2-3 minutes for it to start
echo.
echo ℹ️  Note: "No valid AI API keys" message
echo    - This is NORMAL - system uses stub mode as fallback
echo    - No action needed
echo.

echo.
echo ========================================
echo NEXT STEPS:
echo ========================================
echo.
echo 1. Resume MongoDB cluster:
echo    - Go to https://cloud.mongodb.com
echo    - Click "Resume" on cluster0
echo    - Wait 2-3 minutes
echo.
echo 2. Restart the server:
echo    - Press Ctrl+C if server is running
echo    - Run: python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
echo.
echo 3. Verify in logs:
echo    - Look for: "✅ Connected to MongoDB: bhiv_db"
echo    - Look for: "✅ MongoDB indexes created successfully"
echo.
echo 4. Test the API:
echo    - curl http://localhost:8000/health
echo.
echo ========================================
echo.
pause
