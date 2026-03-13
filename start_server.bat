@echo off
echo Activating virtual environment and starting server...

cd /d c:\Users\Anmol\Desktop\Backend

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Change to backend directory
cd backend

REM Start the server
echo Starting FastAPI server...
python -m uvicorn app.main_simple:app --reload --host 0.0.0.0 --port 8000

pause
