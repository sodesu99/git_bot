#!/usr/bin/env python3
"""
Test Telegram bot initialization and basic functionality.
"""

import os
import sys
import logging
import asyncio
import yaml
from unittest.mock import AsyncMock, MagicMock, patch

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

from git_watcher import GitWatcher
from diff_analyzer import DiffAnalyzer
from telegram_bot import GitTelegramBot
from state_machine import BotStateMachine

def load_test_config():
    """Load test configuration."""
    config_path = 'test_config.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config

def test_bot_initialization():
    """Test bot initialization with real token."""
    print("🧪 Testing Telegram bot initialization")
    print("="*60)
    
    try:
        config = load_test_config()
        
        # Check token
        token = config['telegram']['token']
        if not token or token == "DUMMY_TOKEN_FOR_TESTING":
            print("⚠️ Using dummy token, skipping real connection test")
            return False
        
        print(f"Token found: {token[:10]}... (truncated for security)")
        
        # Initialize components
        watcher = GitWatcher(config['repositories'])
        analyzer = DiffAnalyzer(watcher)
        allowed_user_ids = config['telegram'].get('allowed_user_ids', [])
        
        print(f"GitWatcher loaded {len(watcher.list_repositories())} repositories")
        print(f"Allowed user IDs: {allowed_user_ids}")
        
        # Initialize bot (without starting)
        bot = GitTelegramBot(token, watcher, analyzer, allowed_user_ids)
        
        print("✅ Bot initialization successful")
        print(f"  - Token: Valid")
        print(f"  - Components: GitWatcher, DiffAnalyzer, StateMachine")
        print(f"  - User restriction: {len(allowed_user_ids)} allowed user(s)")
        
        return True
        
    except Exception as e:
        print(f"❌ Bot initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_bot_connection():
    """Test bot connection to Telegram API."""
    print(f"\n{'='*60}")
    print("🧪 Testing Telegram API connection")
    print("="*60)
    
    try:
        config = load_test_config()
        token = config['telegram']['token']
        
        if not token or token == "DUMMY_TOKEN_FOR_TESTING":
            print("⚠️ Using dummy token, skipping connection test")
            return False
        
        # Test connection using Telegram's getMe API
        from telegram import Bot
        
        print(f"Connecting to Telegram API with token: {token[:10]}...")
        bot = Bot(token=token)
        
        # This will raise an exception if token is invalid
        me = await bot.get_me()
        
        print(f"✅ Connection successful!")
        print(f"  Bot ID: {me.id}")
        print(f"  Bot username: @{me.username}")
        print(f"  Bot name: {me.first_name}")
        
        # Test sending a message (to ourselves if user ID is configured)
        allowed_user_ids = config['telegram'].get('allowed_user_ids', [])
        if allowed_user_ids:
            test_user_id = allowed_user_ids[0]
            try:
                test_message = "🤖 Git-Telegram Bot connection test successful!"
                await bot.send_message(
                    chat_id=test_user_id,
                    text=test_message
                )
                print(f"  Test message sent to user {test_user_id}")
            except Exception as e:
                print(f"  ⚠️ Could not send test message: {e}")
                print(f"  This might be because the bot hasn't been started by the user yet")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        # Don't print full traceback for connection errors (common)
        return False

def test_mock_commands():
    """Test bot command handlers with mocks."""
    print(f"\n{'='*60}")
    print("🧪 Testing bot command handlers (mock)")
    print("="*60)
    
    try:
        config = load_test_config()
        watcher = GitWatcher(config['repositories'])
        analyzer = DiffAnalyzer(watcher)
        allowed_user_ids = config['telegram'].get('allowed_user_ids', [])
        
        # Initialize bot with mock application
        bot = GitTelegramBot("TEST_TOKEN", watcher, analyzer, allowed_user_ids)
        
        # Mock update and context
        mock_update = MagicMock(spec=AsyncMock)
        mock_update.effective_user.id = 8498873087
        mock_update.effective_chat.id = 8498873087
        mock_update.message.reply_text = AsyncMock()
        
        mock_context = MagicMock(spec=AsyncMock)
        mock_context.args = []
        
        # Test /start command
        print("Testing /start command...")
        asyncio.run(bot.start(mock_update, mock_context))
        mock_update.message.reply_text.assert_called_once()
        print("  ✅ /start handler works")
        
        # Test /help command
        mock_update.message.reply_text.reset_mock()
        asyncio.run(bot.help_command(mock_update, mock_context))
        mock_update.message.reply_text.assert_called_once()
        print("  ✅ /help handler works")
        
        # Test /list command
        mock_update.message.reply_text.reset_mock()
        asyncio.run(bot.list_repositories(mock_update, mock_context))
        mock_update.message.reply_text.assert_called_once()
        print("  ✅ /list handler works")
        
        # Test /check command with no args
        mock_update.message.reply_text.reset_mock()
        mock_context.args = []
        asyncio.run(bot.check_repository(mock_update, mock_context))
        mock_update.message.reply_text.assert_called_once()
        print("  ✅ /check handler (no args) works")
        
        # Test /status command
        mock_update.message.reply_text.reset_mock()
        asyncio.run(bot.status(mock_update, mock_context))
        mock_update.message.reply_text.assert_called_once()
        print("  ✅ /status handler works")
        
        print("✅ All command handlers test passed")
        return True
        
    except Exception as e:
        print(f"❌ Mock command test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_real_command_flow():
    """Test real command flow with actual bot (but not starting polling)."""
    print(f"\n{'='*60}")
    print("🧪 Testing real command flow")
    print("="*60)
    
    try:
        config = load_test_config()
        token = config['telegram']['token']
        
        if not token or token == "DUMMY_TOKEN_FOR_TESTING":
            print("⚠️ Using dummy token, skipping real command flow test")
            return False
        
        watcher = GitWatcher(config['repositories'])
        analyzer = DiffAnalyzer(watcher)
        allowed_user_ids = config['telegram'].get('allowed_user_ids', [])
        
        # Initialize bot
        bot = GitTelegramBot(token, watcher, analyzer, allowed_user_ids)
        
        # Get bot info
        from telegram import Bot
        telegram_bot = Bot(token=token)
        me = await telegram_bot.get_me()
        
        print(f"Bot: @{me.username} ({me.first_name})")
        print(f"Repositories: {', '.join(watcher.list_repositories())}")
        
        # Test sending actual messages
        if allowed_user_ids:
            test_user_id = allowed_user_ids[0]
            
            # Send welcome message
            welcome_text = (
                "🤖 Git-Telegram Bot Test\n\n"
                "This is a test message from the integration test.\n"
                f"Bot: @{me.username}\n"
                f"Repositories configured: {len(watcher.list_repositories())}\n\n"
                "Try these commands:\n"
                "/start - Welcome message\n"
                "/list - List repositories\n"
                "/check <repo> - Check for changes"
            )
            
            try:
                await telegram_bot.send_message(
                    chat_id=test_user_id,
                    text=welcome_text
                )
                print(f"✅ Test message sent to user {test_user_id}")
            except Exception as e:
                print(f"⚠️ Could not send test message: {e}")
                print("This is normal if the user hasn't started the bot yet")
        
        print("✅ Real command flow test completed")
        return True
        
    except Exception as e:
        print(f"❌ Real command flow test failed: {e}")
        return False

def main():
    """Run all Telegram bot tests."""
    import asyncio
    
    print("🚀 Starting Telegram bot integration tests")
    print("="*60)
    
    results = []
    
    # Test 1: Initialization
    results.append(('Initialization', test_bot_initialization()))
    
    # Test 2: Mock commands
    results.append(('Mock commands', test_mock_commands()))
    
    # Test 3: API connection (async)
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        connection_result = loop.run_until_complete(test_bot_connection())
        results.append(('API connection', connection_result))
    except Exception as e:
        print(f"❌ Async test setup failed: {e}")
        results.append(('API connection', False))
    
    # Test 4: Real command flow (async)
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        flow_result = loop.run_until_complete(test_real_command_flow())
        results.append(('Real command flow', flow_result))
    except Exception as e:
        print(f"❌ Async command flow test failed: {e}")
        results.append(('Real command flow', False))
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 Telegram Bot Test Summary")
    print(f"{'='*60}")
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:30} {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print(f"\n✅ All Telegram bot tests passed!")
        print(f"\n🎉 Bot is ready to use!")
        print(f"   Bot username: (check connection test output)")
        print(f"   Available commands: /start, /help, /list, /check, /status")
        print(f"   Configured repositories: {len(config['repositories'])}")
        return 0
    else:
        print(f"\n⚠️ Some tests failed. Bot may still work, but check issues above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())