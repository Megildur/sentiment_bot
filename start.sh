echo "⬇️ Pulling newest bot version from Git..."
git pull origin main

echo "🐍 Activating virtual environment..."
source venv/bin/activate

echo "📦 Updating dependent libraries..."
pip install -U -r requirements.txt

echo "🚀 Starting the bot..."
python Main.py