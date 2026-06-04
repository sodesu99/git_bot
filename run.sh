#!/bin/bash
# Run the Git-Telegram bot

set -e

cd "$(dirname "$0")"

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Virtual environment not found. Creating..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
fi

# Check for config file
if [ ! -f "config.yaml" ]; then
    echo "config.yaml not found. Creating from example..."
    if [ -f "config.example.yaml" ]; then
        cp config.example.yaml config.yaml
        echo "Please edit config.yaml with your settings before running."
        exit 1
    else
        echo "Error: config.example.yaml not found."
        exit 1
    fi
fi

# Run the bot
python main.py --config config.yaml "$@"