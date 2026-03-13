# PowerShell script to set up virtual environment
Write-Host "Cleaning up broken venv..." -ForegroundColor Yellow
if (Test-Path "backend\venv") {
    Remove-Item -Recurse -Force backend\venv
}

Write-Host "Creating new venv in backend directory..." -ForegroundColor Green
Set-Location backend
python -m venv venv

Write-Host "Setting execution policy..." -ForegroundColor Green
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force

Write-Host "Activating venv..." -ForegroundColor Green
& "venv\Scripts\Activate.ps1"

Write-Host "Installing requirements..." -ForegroundColor Green
pip install --upgrade pip
pip install -r requirements.txt

Write-Host "Done! To activate: cd backend; venv\Scripts\Activate.ps1" -ForegroundColor Cyan
