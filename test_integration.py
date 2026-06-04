#!/usr/bin/env python3
"""Integration test for System in GitTelegramBot."""

import sys
import asyncio
from unittest.mock import Mock, AsyncMock
from telegram import Update
from telegram.ext import ContextTypes

# Mock the required components
sys.path.insert(0, '.')

from git_watcher import GitWatcher
from diff_analyzer import DiffAnalyzer
from telegram_bot import GitTelegramBot

def create_mock_update(text: str, user_id: int = 12345):
    """Create a mock Update object."""
    update = Mock(spec=Update)
    update.effective_user = Mock()
    update.effective_user.id = user_id
    update.effective_chat = Mock()
    update.effective_chat.id = user_id
    update.message = Mock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update

async def test_sys_command():
    """Test /sys command."""
    # Create bot with mock components
    config = {
        'repositories': {
            'test-repo': {'path': '/tmp/test'}
        }
    }
    git_watcher = GitWatcher(config['repositories'])
    diff_analyzer = DiffAnalyzer(git_watcher)
    bot = GitTelegramBot(
        token="fake-token",
        git_watcher=git_watcher,
        diff_analyzer=diff_analyzer,
        allowed_user_ids=[12345]
    )
    
    # Mock update for /sys
    update = create_mock_update("/sys !pwd", user_id=12345)
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = ["!pwd"]
    
    await bot.sys_command(update, context)
    
    # Check that reply_text was called
    update.message.reply_text.assert_called()
    print("sys_command called successfully")
    
    # Test /sys without args
    update2 = create_mock_update("/sys", user_id=12345)
    context2 = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context2.args = []
    
    await bot.sys_command(update2, context2)
    update2.message.reply_text.assert_called()
    print("sys_command status called successfully")

if __name__ == "__main__":
    asyncio.run(test_sys_command())