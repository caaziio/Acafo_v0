#!/bin/bash

echo "🚀 Starting Flask Resume Builder..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found!"
    echo "📝 Please copy .env.example to .env and configure your environment variables:"
    echo "   cp .env.example .env"
    echo "   # Then edit .env with your actual values"
    echo ""
    echo "🔑 Required variables:"
    echo "   - APP_SECRET_KEY"
    echo "   - OPENAI_API_KEY"
    echo ""
    echo "📋 Optional variables (with defaults):"
    echo "   - OPENAI_MODEL (default: gpt-4o-mini)"
    echo "   - AI_MAX_TOKENS (default: 2000)"
    echo "   - AI_TIMEOUT_SECONDS (default: 30)"
    echo "   - GOOGLE_SHEET_URL (for logging)"
    echo "   - GOOGLE_CREDENTIALS_PATH (default: credentials.json)"
    echo "   - RATE_LIMIT_DEFAULT (default: 100 per minute)"
    echo "   - RATE_LIMIT_AI (default: 10 per minute)"
    echo "   - LOGS_DIR (default: logs)"
    echo ""
    echo "❌ Cannot start without .env configuration"
    exit 1
fi

# Check if required environment variables are set
echo "🔍 Checking configuration..."
if ! python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
required = ['OPENAI_API_KEY', 'APP_SECRET_KEY']
missing = [var for var in required if not os.getenv(var)]
if missing:
    print(f'❌ Missing required environment variables: {missing}')
    exit(1)
print('✅ Configuration looks good!')
"; then
    echo "❌ Configuration check failed. Please check your .env file."
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p logs

echo "✅ All checks passed!"
echo "🚀 Starting Flask application..."
echo "📱 Open your browser to: http://localhost:3000"
echo "🛑 Press Ctrl+C to stop the application"
echo ""

# Start the Flask application
python3 app.py
