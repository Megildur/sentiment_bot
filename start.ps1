Write-Host "Pulling newest bot version from Git..."
git pull origin main

Write-Host "Activating virtual environment..."
.\venv\Scripts\Activate.ps1

Write-Host "Updating dependent libraries..."
pip install -U -r requirements.txt

Write-Host "Starting the bot..."
python Main.py
