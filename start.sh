#!/bin/bash
# Freelance Domination Engine v5.0 — Quick Start

echo "🚀 Freelance Domination Engine v5.0 Hybrid"
echo "============================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "❌ Python not found. Installing..."
    if command -v pkg &> /dev/null; then
        pkg update && pkg install python -y
    elif command -v apt &> /dev/null; then
        sudo apt update && sudo apt install python3 -y
    elif command -v brew &> /dev/null; then
        brew install python3
    else
        echo "Please install Python 3.8+ manually"
        exit 1
    fi
fi

PYTHON=$(command -v python3 || command -v python)
echo "✅ Python: $PYTHON"

# Check optional dependencies
if $PYTHON -c "import requests, bs4" 2>/dev/null; then
    echo "✅ requests + beautifulsoup4 installed"
else
    echo "⚠️  Optional dependencies missing (scraper will use built-in urllib)"
    echo "   For better reliability: pip install requests beautifulsoup4"
fi

echo ""
echo "Starting scraper in ONCE mode (single run)..."
echo "For continuous mode: python local_scraper.py"
echo "For dry-run: python local_scraper.py --dry-run --once"
echo ""

$PYTHON local_scraper.py --once "$@"

echo ""
echo "✅ Run complete!"
echo "📊 Dashboard: https://freelance-domination-engine.fde-work.workers.dev/"
echo "📱 Check Telegram for job alerts"
