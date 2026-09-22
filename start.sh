#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status (except where handled)
set -e

echo "⬇️ Pulling newest bot version from Git..."
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git pull origin main || echo "⚠️ Warning: git pull failed or there are local changes. Continuing anyway..."
else
    echo "⚠️ Not a git repository. Skipping git pull."
fi

# Detect Python interpreter if venv needs to be created
find_python() {
    for cmd in python3.14 python3 python py; do
        if command -v "$cmd" >/dev/null 2>&1; then
            # Verify it's a real working Python and not the Windows Store shortcut
            if "$cmd" -c "import sys" >/dev/null 2>&1; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

# 1. Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    echo "⚙️ Virtual environment not found. Creating 'venv'..."
    PY_CMD=$(find_python)
    if [ -z "$PY_CMD" ]; then
        echo "❌ Error: Python not found. Please install Python and ensure it is added to PATH."
        exit 1
    fi
    echo "Using '$PY_CMD' to create virtual environment..."
    "$PY_CMD" -m venv venv
fi

# 2. Activate virtual environment (handles both Windows and Linux/macOS paths)
echo "🐍 Activating virtual environment..."
if [ -f "venv/Scripts/activate" ]; then
    # Windows (Git Bash / MSYS / Cygwin)
    # shellcheck disable=SC1091
    source venv/Scripts/activate
elif [ -f "venv/bin/activate" ]; then
    # Linux / macOS / WSL
    # shellcheck disable=SC1091
    source venv/bin/activate
else
    echo "❌ Error: Could not find activate script in venv/Scripts/activate or venv/bin/activate"
    exit 1
fi

# 3. Install / update dependencies
echo "📦 Updating dependent libraries..."
pip install -U -r requirements.txt

# 4. Start the bot
echo "🚀 Starting the bot..."
python Main.py