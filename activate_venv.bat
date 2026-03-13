@echo off
echo Activating Python Virtual Environment...
call .venv\Scripts\activate.bat
echo.
echo Virtual environment activated!
echo Python location: %VIRTUAL_ENV%
echo.
echo To verify installation, run:
echo python -c "import fastapi, pymongo, motor; print('Dependencies OK')"
echo.
echo To start the server, run:
echo cd backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
echo.
cmd /k
