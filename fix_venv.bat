@echo off
echo Cleaning up broken venv...
if exist backend\venv rmdir /s /q backend\venv

echo Creating new venv in backend directory...
cd backend
python -m venv venv --clear

echo Activating venv...
call venv\Scripts\activate

echo Installing requirements...
pip install --upgrade pip
pip install -r requirements.txt

echo Done! To activate: cd backend && venv\Scripts\activate
pause
