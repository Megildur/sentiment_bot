Write-Host ">>> Pulling newest bot version from Git..." -ForegroundColor Cyan
try {
    git pull origin main
} catch {
    Write-Host "[!] Warning: git pull failed or local changes exist. Continuing..." -ForegroundColor Yellow
}

# Find Python interpreter
function Find-Python {
    $candidates = @("python3.14", "python3", "python", "py", "$env:USERPROFILE\.local\bin\python3.14.exe")
    foreach ($cand in $candidates) {
        try {
            $test = & $cand -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $test) {
                return $cand
            }
        } catch { }
    }
    return $null
}

# 1. Create venv if missing
if (-not (Test-Path "venv")) {
    Write-Host ">>> Virtual environment not found. Creating 'venv'..." -ForegroundColor Cyan
    $py = Find-Python
    if (-not $py) {
        Write-Host "[X] Error: Python not found. Please install Python or ensure it is in PATH." -ForegroundColor Red
        exit 1
    }
    Write-Host "Using $py to create virtual environment..."
    & $py -m venv venv
}

# 2. Activate virtual environment
Write-Host ">>> Activating virtual environment..." -ForegroundColor Cyan
if (Test-Path "venv\Scripts\Activate.ps1") {
    . .\venv\Scripts\Activate.ps1
} elseif (Test-Path "venv\Scripts\python.exe") {
    $env:VIRTUAL_ENV = "$PSScriptRoot\venv"
    $env:PATH = "$PSScriptRoot\venv\Scripts;$env:PATH"
}

# 3. Install / update dependencies
Write-Host ">>> Updating dependent libraries..." -ForegroundColor Cyan
pip install -U -r requirements.txt

# 4. Start the bot
Write-Host ">>> Starting the bot..." -ForegroundColor Green
python Main.py
