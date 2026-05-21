@echo off
REM Run from: C:\Users\Anmol\Desktop\Backend\
REM Sets PYTHONPATH so both 'app' and 'platform_adapter' are importable

set PYTHONPATH=C:\Users\Anmol\Desktop\Backend\backend;C:\Users\Anmol\Desktop\Backend

cd /d C:\Users\Anmol\Desktop\Backend\backend

C:\Users\Anmol\Desktop\Backend\.venv\Scripts\uvicorn.exe app.main:app --reload --host 0.0.0.0 --port 8000
