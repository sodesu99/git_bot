#!/usr/bin/env python3
"""
Main entry point for Git-Telegram bot system.
"""

import os
import sys
import yaml
import logging
import asyncio
import signal
from typing import Dict, Any
from loguru import logger

from git_watcher import GitWatcher
from diff_analyzer import DiffAnalyzer
from telegram_bot import GitTelegramBot


def setup_logging(config: Dict[str, Any]):
    """Configure logging based on config."""
    log_level = config.get('logging', {}).get('level', 'INFO')
    log_file = config.get('logging', {}).get('file')

    # Remove default handler
    logger.remove()

    # Add console handler
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )

    # Add file handler if specified
    if log_file:
        logger.add(
            log_file,
            level=log_level,
            rotation="10 MB",
            retention="1 month",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}"
        )

    # Also configure standard logging for libraries that use it
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    if not os.path.exists(config_path):
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path, 'r') as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse config file: {e}")
            sys.exit(1)

    # Validate required fields
    if 'telegram' not in config or 'token' not in config['telegram']:
        logger.error("Config missing 'telegram.token'")
        sys.exit(1)

    if 'repositories' not in config:
        logger.error("Config missing 'repositories'")
        sys.exit(1)

    return config


async def periodic_check(config: Dict[str, Any], git_watcher: GitWatcher, diff_analyzer: DiffAnalyzer):
    """Periodically check repositories for changes."""
    from telegram import Bot
    import asyncio

    polling_interval = config.get('polling_interval', 300)  # seconds
    token = config['telegram']['token']
    allowed_user_ids = config['telegram'].get('allowed_user_ids', [])

    if not allowed_user_ids:
        logger.warning("No allowed_user_ids specified for periodic checks. Skipping.")
        return

    bot = Bot(token=token)

    while True:
        logger.info(f"Running periodic check (interval: {polling_interval}s)")
        for repo_name in git_watcher.list_repositories():
            try:
                # Lightweight check first: git ls-remote instead of full fetch
                has_new_remote, light_err = git_watcher.lightweight_check(repo_name)
                if light_err:
                    logger.error(f"Lightweight check error for {repo_name}: {light_err}")
                    continue
                if not has_new_remote:
                    # No remote changes detected, skip this repo
                    continue

                logger.info(f"Remote changes detected for {repo_name}, performing full check...")
                has_changes, changed_files, error = git_watcher.check_repository(repo_name)
                if error:
                    logger.error(f"Error checking {repo_name}: {error}")
                    continue

                if has_changes:
                    analysis = diff_analyzer.analyze_changes(repo_name, changed_files)
                    message, _ = diff_analyzer.format_message_for_telegram(analysis)

                    # Notify all allowed users
                    for user_id in allowed_user_ids:
                        try:
                            await bot.send_message(
                                chat_id=user_id,
                                text=f"🔄 Periodic check detected changes in '{repo_name}':\n\n{message}",
                                parse_mode='Markdown'
                            )
                            logger.info(f"Notified user {user_id} about changes in {repo_name}")
                        except Exception as e:
                            logger.error(f"Failed to notify user {user_id}: {e}")
            except Exception as e:
                logger.exception(f"Unexpected error checking {repo_name}: {e}")

        await asyncio.sleep(polling_interval)


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description='Git-Telegram Bot System')
    parser.add_argument('--config', '-c', default='config.yaml',
                       help='Path to configuration file (default: config.yaml)')
    parser.add_argument('--periodic', '-p', action='store_true',
                       help='Enable periodic checking in addition to bot commands')
    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)
    setup_logging(config)

    logger.info("Starting Git-Telegram Bot System")

    # Initialize components
    git_watcher = GitWatcher(config['repositories'])
    diff_analyzer = DiffAnalyzer(git_watcher)

    # Check if any repositories loaded
    repos = git_watcher.list_repositories()
    if not repos:
        logger.warning("No repositories loaded. Check your configuration.")
    else:
        logger.info(f"Loaded {len(repos)} repositories: {', '.join(repos)}")

    # Initialize and run bot
    token = config['telegram']['token']
    allowed_user_ids = config['telegram'].get('allowed_user_ids', [])
    bot = GitTelegramBot(token, git_watcher, diff_analyzer, allowed_user_ids)

    # Set up signal handling for graceful shutdown
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal")
        if bot.application:
            bot.application.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run bot (and optionally periodic checks)
    if args.periodic:
        logger.info("Starting with periodic checks enabled")
        import threading

        # Start periodic checks in a separate thread
        loop = asyncio.new_event_loop()
        periodic_thread = threading.Thread(
            target=lambda: loop.run_until_complete(periodic_check(config, git_watcher, diff_analyzer)),
            daemon=True
        )
        periodic_thread.start()

        # Run bot in main thread
        bot.run()
    else:
        logger.info("Starting bot (periodic checks disabled)")
        bot.run()


if __name__ == '__main__':
    main()