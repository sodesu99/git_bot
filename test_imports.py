#!/usr/bin/env python3
"""
Test that all modules can be imported correctly.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from state_machine import BotStateMachine
    print("✓ state_machine imported")
except Exception as e:
    print(f"✗ state_machine import failed: {e}")
    sys.exit(1)

try:
    from git_watcher import GitWatcher
    print("✓ git_watcher imported")
except Exception as e:
    print(f"✗ git_watcher import failed: {e}")
    sys.exit(1)

try:
    from diff_analyzer import DiffAnalyzer
    print("✓ diff_analyzer imported")
except Exception as e:
    print(f"✗ diff_analyzer import failed: {e}")
    sys.exit(1)

try:
    from telegram_bot import GitTelegramBot
    print("✓ telegram_bot imported")
except Exception as e:
    print(f"✗ telegram_bot import failed: {e}")
    sys.exit(1)

print("\n✅ All imports successful!")

# Test state machine
print("\nTesting state machine...")
sm = BotStateMachine()
print(f"Initial state: {sm.state}")
sm.check_requested()
print(f"After check_requested: {sm.state}")
sm.fetch_completed()
print(f"After fetch_completed: {sm.state}")
sm.diff_completed()
print(f"After diff_completed: {sm.state}")
sm.send_completed()
print(f"After send_completed: {sm.state}")
sm.error_occurred()
print(f"After error_occurred: {sm.state}")
sm.retry()
print(f"After retry: {sm.state}")

print("\n✅ Basic tests passed!")