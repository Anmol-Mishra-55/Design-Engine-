# start_server.ps1
# Run from: C:\Users\Anmol\Desktop\Backend\
# This sets PYTHONPATH so both 'app' and 'platform_adapter' are importable

$env:PYTHONPATH = "C:\Users\Anmol\Desktop\Backend\backend;C:\Users\Anmol\Desktop\Backend"

Set-Location "C:\Users\Anmol\Desktop\Backend\backend"

& "C:\Users\Anmol\Desktop\Backend\.venv\Scripts\uvicorn.exe" app.main:app --reload --host 0.0.0.0 --port 8000
