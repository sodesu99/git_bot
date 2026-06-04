#!/usr/bin/env python3
"""
Run the Telegram bot for a short test period.
"""

import os
import sys
import signal
import logging
import yaml
import asyncio
import threading
import time

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from git_watcher import GitWatcher
from diff_analyzer import DiffAnalyzer
from telegram_bot import GitTelegramBot

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    print(f"\nReceived signal {signum}, shutting down...")
    sys.exit(0)

def run_bot_test():
    """Run bot for a short test period."""
    print("🚀 Starting Git-Telegram Bot Test")
    print("="*60)
    
    # Load configuration
    config_path = 'test_config.yaml'
    if not os.path.exists(config_path):
        print(f"❌ Config file not found: {config_path}")
        return 1
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    token = config['telegram']['token']
    allowed_user_ids = config['telegram'].get('allowed_user_ids', [])
    
    print(f"Bot token: {token[:10]}...")
    print(f"Allowed users: {allowed_user_ids}")
    print(f"Repositories: {list(config['repositories'].keys())}")
    
    # Initialize components
    watcher = GitWatcher(config['repositories'])
    analyzer = DiffAnalyzer(watcher)
    
    # Initialize bot
    bot = GitTelegramBot(token, watcher, analyzer, allowed_user_ids)
    
    # Set up signal handling
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("\n🤖 Bot is starting...")
    print("  - Send /start to begin")
    print("  - Send /list to see repositories")
    print("  - Send /check <repo> to check for changes")
    print("  - Send /status to see bot status")
    print(f"\n  Test duration: 30 seconds")
    print("  Press Ctrl+C to stop early")
    
    # Run bot in a separate thread
    bot_thread = threading.Thread(target=bot.run, daemon=True)
    bot_thread.start()
    
    # Wait for 30 seconds (or until interrupted)
    try:
        for i in range(30):
            time.sleep(1)
            if i % 10 == 0:
                remaining = 30 - i
                print(f"  Time remaining: {remaining} seconds...")
    except KeyboardInterrupt:
        print("\n⏹️ Stopping bot...")
    
    print("\n✅ Test completed!")
    print("Bot will stop automatically (daemon thread)")
    
    return 0

def quick_command_test():
    """Test sending commands to the running bot."""
    print(f"\n{'='*60}")
    print("📝 Quick Command Reference")
    print(f"{'='*60}")
    
    print("\nOnce the bot is running, try these commands in Telegram:")
    print("\n1. /start")
    print("   - Welcome message and introduction")
    
    print("\n2. /help")
    print("   - Detailed help with examples")
    
    print("\n3. /list")
    print("   - List all configured repositories")
    print("   - Shows: name, path, branch, commit, dirty status")
    
    print("\n4. /check <repository_name>")
    print("   - Check a repository for changes")
    print("   - Example: /check orchestrator-v4")
    print("   - Example: /check rag-system")
    
    print("\n5. /status")
    print("   - Show bot status and active state machines")
    
    print(f"\n{'='*60}")
    print("🎯 Expected Results")
    print(f"{'='*60}")
    
    print("\nFor /check commands:")
    print("  - If no changes: 'Repository has no new changes'")
    print("  - If changes: Shows file list with content preview")
    print("  - Automatic truncation for long messages")
    print("  - Compact summary at the end")
    
    print("\nFor your current repositories:")
    print("  - orchestrator-v4: 55 locally changed files")
    print("  - rag-system: 3 locally changed files")

def main():
    """Main function."""
    # Show command reference first
    quick_command_test()
    
    print(f"\n{'='*60}")
    response = input("Start bot for 30-second test? (y/n): ")
    
    if response.lower() != 'y':
        print("Skipping bot start. You can run it later with:")
        print("  python main.py --config test_config.yaml")
        return 0
    
    return run_bot_test()

if __name__ == '__main__':
    sys.exit(main())