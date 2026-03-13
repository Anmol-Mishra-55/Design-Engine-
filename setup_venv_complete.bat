@echo off
echo ========================================
echo Setting up Python Virtual Environment
echo ========================================

REM Remove existing .venv if it exists
if exist ".venv" (
    echo Removing existing .venv directory...
    rmdir /s /q ".venv"
)

REM Create new virtual environment
echo Creating new virtual environment...
python -m venv .venv

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies from the complete requirements file
echo Installing dependencies...
pip install -r requirements_complete.txt

REM Also install from backend requirements if it exists
if exist "backend\requirements.txt" (
    echo Installing backend-specific requirements...
    pip install -r backend\requirements.txt
)

REM Install MongoDB specific requirements
if exist "MONGODB_REQUIREMENTS.txt" (
    echo Installing MongoDB requirements...
    pip install -r MONGODB_REQUIREMENTS.txt
)

echo ========================================
echo Virtual Environment Setup Complete!
echo ========================================
echo.
echo To activate the environment, run:
echo .venv\Scripts\activate.bat
echo.
echo To deactivate, run:
echo deactivate
echo.
echo To verify installation, run:
echo python -c "import fastapi, pymongo, motor; print('All dependencies installed successfully!')"
echo ========================================

pause
