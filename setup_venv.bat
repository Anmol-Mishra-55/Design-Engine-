@echo off
echo === Virtual Environment Setup Script ===

REM Clean any existing venv
if exist venv rmdir /s /q venv

echo Step 1: Creating virtual environment...
python -m venv venv --without-pip
if %errorlevel% neq 0 (
    echo Failed to create venv, trying alternative method...
    pip install virtualenv
    virtualenv venv
)

echo Step 2: Activating virtual environment...
call venv\Scripts\activate

echo Step 3: Installing pip...
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python get-pip.py
del get-pip.py

echo Step 4: Upgrading pip...
python -m pip install --upgrade pip

echo Step 5: Installing requirements...
cd backend
pip install -r requirements.txt

echo Step 6: Verifying installation...
python verify_setup.py

echo === Setup Complete! ===
echo To activate in future: venv\Scripts\activate
pause
