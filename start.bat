@echo off
setlocal

echo ⬇️ Pulling newest bot version from Git...
git pull origin main

if not exist venv (
    echo ⚙️ Virtual environment not found. Creating 'venv'...
    python -m venv venv || py -m venv venv || "%USERPROFILE%\.local\bin\python3.14.exe" -m venv venv
)

echo 🐍 Activating virtual environment...
call venv\Scripts\activate.bat

echo 📦 Updating dependent libraries...
pip install -U -r requirements.txt

echo 🚀 Starting the bot...
python Main.py
