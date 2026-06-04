#!/usr/bin/env python3
"""
Telegram bot module for Git change notifications.
"""

import logging
import asyncio
from collections import defaultdict, deque
from datetime import datetime
from typing import Optional, Dict, Any, List, Deque
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    Application,
    filters,
)

from state_machine import BotStateMachine
from git_watcher import GitWatcher
from diff_analyzer import DiffAnalyzer
from system import System

logger = logging.getLogger(__name__)


class GitTelegramBot:
    """Main Telegram bot for Git repository monitoring."""

    def __init__(
        self,
        token: str,
        git_watcher: GitWatcher,
        diff_analyzer: DiffAnalyzer,
        allowed_user_ids: Optional[List[int]] = None,
    ):
        self.token = token
        self.git_watcher = git_watcher
        self.diff_analyzer = diff_analyzer
        self.allowed_user_ids = allowed_user_ids or []
        self.state_machines: Dict[str, BotStateMachine] = {}  # per-user state machines
        self.command_history: Dict[int, Deque[Dict[str, str]]] = defaultdict(lambda: deque(maxlen=200))
        self.application: Optional[Application] = None
        # AI Router + Context System (per-user)
        self.user_systems: Dict[int, System] = {}
        self.git_watcher = git_watcher
        self.diff_analyzer = diff_analyzer
        # AI interaction logs
        self.ai_logs: Deque[Dict[str, Any]] = deque(maxlen=200)
        # Last raw input per user (for bare ! replay)
        self._last_raw_input: Dict[int, str] = {}

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        user_id = update.effective_user.id
        if self.allowed_user_ids and user_id not in self.allowed_user_ids:
            await update.message.reply_text("Sorry, you are not authorized to use this bot.")
            return

        self._record_command(user_id, update.message.text or "/start")

        welcome_text = (
            "🤖 Git Repository Watcher Bot\n\n"
            "I can monitor your Git repositories for changes.\n\n"
            "Available commands:\n"
            "/start - Show this message\n"
            "/help - Show help\n"
            "/list - List available repositories\n"
            "/check <repo> - Check a repository for changes\n"
            "/ck <n> <repo> - Show latest n commits (n defaults to 5)\n"
            "/his [n] - Show your recent commands (default 10)\n"
            "/file <repo> <fileName> - Find latest updated file by name and send full content\n"
            "/status - Show bot status\n"
            "/allow [cmd|list] - Manage command allowlist\n"
            "/sys <input> - AI Router + Context System (use !, @, /config, or AI)\n"
        )
        await update.message.reply_text(welcome_text)

    def _record_command(self, user_id: int, command_text: str) -> None:
        self.command_history[user_id].appendleft({
            'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'cmd': command_text,
        })
        # Extract raw input from command_text (unwrap /sys prefix if present)
        raw = command_text
        if raw.startswith("/sys "):
            raw = raw[5:]
        self._last_raw_input[user_id] = raw

    def _chunk_text(self, text: str, chunk_size: int = 3500) -> List[str]:
        if len(text) <= chunk_size:
            return [text]
        chunks: List[str] = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end])
            start = end
        return chunks

    def _parse_repo_and_limit(self, args: List[str]) -> tuple[Optional[str], int, Optional[str]]:
        """Parse args for /ck: /ck <repo> or /ck <n> <repo>."""
        if not args:
            return None, 5, "Usage: /ck <repo> or /ck <n> <repo>"

        if len(args) == 1:
            return args[0].strip(), 5, None

        try:
            limit = int(args[0])
            repo_name = args[1].strip()
            if limit <= 0:
                return None, 5, "n must be a positive integer."
            return repo_name, min(limit, 50), None
        except ValueError:
            repo_name = args[0].strip()
            try:
                limit = int(args[1])
            except ValueError:
                return None, 5, "Usage: /ck <repo> or /ck <n> <repo>"
            if limit <= 0:
                return None, 5, "n must be a positive integer."
            return repo_name, min(limit, 50), None

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        user_id = update.effective_user.id
        if self.allowed_user_ids and user_id not in self.allowed_user_ids:
            return

        self._record_command(user_id, update.message.text or "/help")

        help_text = (
            "📚 Help\n\n"
            "To check a repository for changes:\n"
            "/check <repository_name>\n\n"
            "To view recent commits:\n"
            "/ck <n> <repository_name>\n"
            "(n is optional, default 5)\n\n"
            "To view your command history:\n"
            "/his [n]\n"
            "(n is optional, default 10)\n\n"
            "To send full content of a recently updated file:\n"
            "/file <repo> <fileName>\n\n"
            "Examples:\n"
            "/check my-project\n"
            "/ck 8 backend\n"
            "/his 20\n"
            "/file backend main.py\n\n"
            "Other commands:\n"
            "/list - Show all configured repositories\n"
            "/list add <path> <name> - Add a repository\n"
            "/list rm <name> - Remove a repository\n"
            "/status - Show bot status\n"
            "/allow [cmd|list] - Manage command allowlist\n"
            "/sys - AI Router + Context System (use !, @, /config, or AI)\n"
            "!<command> - 执行 shell 命令（如 !whoami, !ls）\n"
            "! 或 ！ - 重复上一次命令（shell 命令或 bot 命令都行）\n"
            "/help - Show this message\n\n"
            "The bot will fetch the latest changes from the remote repository "
            "and show you what files have changed along with a preview of their contents."
        )
        await update.message.reply_text(help_text)

    async def list_repositories(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /list command."""
        user_id = update.effective_user.id
        if self.allowed_user_ids and user_id not in self.allowed_user_ids:
            return

        self._record_command(user_id, update.message.text or "/list")
        
        # Handle /list add <path> <repo_name>
        if context.args and len(context.args) >= 1 and context.args[0] == "add":
            if len(context.args) < 3:
                await update.message.reply_text("Usage: /list add <path> <repo_name>\nExample: /list add /Users/zeng/project/git-telegram-bot git-telegram")
                return
            
            path = context.args[1].strip()
            repo_name = context.args[2].strip()
            
            success, message = self.git_watcher.add_repository(repo_name, path)
            if success:
                await update.message.reply_text(f"✅ {message}")
            else:
                await update.message.reply_text(f"❌ {message}")
            return

        # Handle /list rm <repo_name>
        if context.args and len(context.args) >= 1 and context.args[0] == "rm":
            if len(context.args) < 2:
                await update.message.reply_text("Usage: /list rm <repo_name>\nExample: /list rm my-project")
                return

            repo_name = context.args[1].strip()
            success, message = self.git_watcher.remove_repository(repo_name)
            if success:
                await update.message.reply_text(f"🗑️ {message}")
            else:
                await update.message.reply_text(f"❌ {message}")
            return

        # Regular /list command - show repositories
        repos = self.git_watcher.list_repositories()
        if not repos:
            await update.message.reply_text("No repositories configured.\n\nUse /list add <path> <repo_name> to add a repository.")
            return

        message = "📁 Available repositories:\n\n"
        for repo_name in repos:
            info = self.git_watcher.get_repository_info(repo_name)
            if info:
                message += (
                    f"• {repo_name}\n"
                    f"  Path: {info['path']}\n"
                    f"  Branch: {info['active_branch']}\n"
                    f"  Commit: {info['head_commit']}\n"
                    f"  Dirty: {info['is_dirty']}\n\n"
                )
            else:
                message += f"• {repo_name} (error loading info)\n\n"
        
        message += "To add: /list add <path> <name>\nTo remove: /list rm <name>"

        await update.message.reply_text(message)

    async def check_repository(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /check command."""
        user_id = update.effective_user.id
        if self.allowed_user_ids and user_id not in self.allowed_user_ids:
            await update.message.reply_text("Sorry, you are not authorized to use this bot.")
            return

        self._record_command(user_id, update.message.text or "/check")

        # Check if repository name provided
        if not context.args:
            await update.message.reply_text("Please specify a repository name. Example: /check my-repo")
            return

        repo_name = context.args[0].strip()

        # Initialize state machine for this user if not exists
        user_key = f"{user_id}_{repo_name}"
        if user_key not in self.state_machines:
            self.state_machines[user_key] = BotStateMachine({
                'user_id': user_id,
                'repo_name': repo_name,
                'chat_id': update.effective_chat.id,
            })

        sm = self.state_machines[user_key]

        # Ensure state machine is idle
        if not sm.is_idle():
            await update.message.reply_text(f"Already checking '{repo_name}'. Please wait.")
            return

        # Start check process
        try:
            sm.check_requested()
            await update.message.reply_text(f"🔍 Checking repository '{repo_name}'...")

            # Fetch changes
            sm.fetch_completed()
            has_changes, changed_files, error = self.git_watcher.check_repository(repo_name)

            if error:
                sm.set_error(error)
                await update.message.reply_text(f"❌ Error checking '{repo_name}': {error}")
                sm.retry()
                return

            sm.diff_completed()
            if not has_changes:
                sm.send_completed()
                await update.message.reply_text(f"✅ Repository '{repo_name}' has no new changes.")
                return

            # Analyze changes
            analysis = self.diff_analyzer.analyze_changes(repo_name, changed_files)
            sm.context['analysis'] = analysis

            sm.send_completed()
            # Send results
            message, truncated = self.diff_analyzer.format_message_for_telegram(analysis)
            await update.message.reply_text(message, parse_mode='Markdown')

            if truncated:
                await update.message.reply_text("📝 Note: Message was truncated due to length limits.")

            # Also send compact summary
            summary = self.diff_analyzer.format_compact_message(analysis)
            await update.message.reply_text(summary)

        except Exception as e:
            logger.exception(f"Error processing check for '{repo_name}': {e}")
            sm.set_error(str(e))
            await update.message.reply_text(f"❌ Unexpected error: {e}")
            sm.retry()

    async def check_commits(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /ck command: show latest n commits for repository."""
        user_id = update.effective_user.id
        if self.allowed_user_ids and user_id not in self.allowed_user_ids:
            await update.message.reply_text("Sorry, you are not authorized to use this bot.")
            return

        self._record_command(user_id, update.message.text or "/ck")

        repo_name, limit, error = self._parse_repo_and_limit(context.args)
        if error:
            await update.message.reply_text(error)
            return

        commits, err = self.git_watcher.get_recent_commits(repo_name, limit)
        if err:
            await update.message.reply_text(f"❌ {err}")
            return

        if not commits:
            await update.message.reply_text(f"No commits found for '{repo_name}'.")
            return

        lines = [f"🧾 Latest {len(commits)} commits for '{repo_name}':", ""]
        for i, c in enumerate(commits, 1):
            first_line = c['message'].splitlines()[0] if c['message'] else '(no message)'
            files = c.get('files', [])
            if files:
                files_block = "\n".join([f"      - {f}" for f in files])
            else:
                files_block = "      - (no file stats)"

            lines.append(
                f"{i}. {c['short_sha']} {first_line}\n"
                f"   👤 {c['author']} | 🕒 {c['date']}\n"
                f"   📂 Files:\n{files_block}"
            )

        full_text = "\n\n".join(lines)
        for part in self._chunk_text(full_text, chunk_size=3500):
            await update.message.reply_text(part)

    async def command_history_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /his command: show recent commands for current user."""
        user_id = update.effective_user.id
        if self.allowed_user_ids and user_id not in self.allowed_user_ids:
            await update.message.reply_text("Sorry, you are not authorized to use this bot.")
            return

        self._record_command(user_id, update.message.text or "/his")

        limit = 10
        if context.args:
            try:
                limit = int(context.args[0])
            except ValueError:
                await update.message.reply_text("Usage: /his [n], n must be an integer")
                return

        if limit <= 0:
            await update.message.reply_text("n must be a positive integer.")
            return

        safe_limit = min(limit, 50)
        history = list(self.command_history[user_id])[:safe_limit]

        if not history:
            await update.message.reply_text("No command history yet.")
            return

        lines = [f"📜 Recent {len(history)} commands:", ""]
        for i, item in enumerate(history, 1):
            lines.append(f"{i}. {item['cmd']}\n   🕒 {item['ts']}")

        await update.message.reply_text("\n".join(lines))

    async def file_from_recent_updates(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /file command: find files in repo by name/path and send content."""
        user_id = update.effective_user.id
        if self.allowed_user_ids and user_id not in self.allowed_user_ids:
            await update.message.reply_text("Sorry, you are not authorized to use this bot.")
            return

        self._record_command(user_id, update.message.text or "/file")

        if len(context.args) < 2:
            await update.message.reply_text("Usage: /file <repo> <fileName>")
            return

        repo_name = context.args[0].strip()
        file_name = " ".join(context.args[1:]).strip()

        matched_files, err = self.git_watcher.find_file_in_repo(repo_name, file_name)
        if err:
            await update.message.reply_text(f"❌ {err}")
            return

        if len(matched_files) == 1:
            # Single match: send content
            matched_path = matched_files[0]
            content = self.git_watcher.read_file_content(repo_name, matched_path, max_lines=5000)
            if content is None:
                await update.message.reply_text(f"❌ Found '{matched_path}', but failed to read content.")
                return

            all_text = f"📄 {matched_path}\n\n{content}"

            parts = self._chunk_text(all_text, chunk_size=3500)
            for idx, part in enumerate(parts, 1):
                prefix = "" if len(parts) == 1 else f"(part {idx}/{len(parts)})\n"
                await update.message.reply_text(prefix + part)
        else:
            # Multiple matches: list relative paths
            lines = [f"📂 Found {len(matched_files)} files matching '{file_name}':", ""]
            for path in matched_files:
                lines.append(f"• {path}")
            await update.message.reply_text("\n".join(lines))

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        user_id = update.effective_user.id
        if self.allowed_user_ids and user_id not in self.allowed_user_ids:
            return

        self._record_command(user_id, update.message.text or "/status")

        total_repos = len(self.git_watcher.list_repositories())
        user_sm_count = sum(1 for key in self.state_machines if key.startswith(str(user_id)))

        status_text = (
            f"🤖 Bot Status\n\n"
            f"• Configured repositories: {total_repos}\n"
            f"• Your active checks: {user_sm_count}\n"
            f"• Bot version: 1.0.0\n"
            f"• Uptime: (TODO)\n"
        )
        await update.message.reply_text(status_text)

    async def sys_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /sys command for AI Router + Context System."""
        user_id = update.effective_user.id
        if self.allowed_user_ids and user_id not in self.allowed_user_ids:
            await update.message.reply_text("Sorry, you are not authorized to use this bot.")
            return

        self._record_command(user_id, update.message.text or "/sys")

        # Get or create system instance for this user
        if user_id not in self.user_systems:
            self.user_systems[user_id] = System(
                git_watcher=self.git_watcher,
                diff_analyzer=self.diff_analyzer
            )
        system = self.user_systems[user_id]

        # Combine all arguments as the input text
        input_text = " ".join(context.args).strip() if context.args else ""
        
        if not input_text:
            # Show system status if no input
            status = system.get_status()
            status_text = (
                "🤖 AI Router + Context System (User-specific)\n\n"
                f"• File mappings: {status['file_map_count']}\n"
                f"• Short context entries: {status['short_context_count']}\n"
                f"• Long context: {status['long_context']}\n"
                f"• Available actions: {len(status['available_actions'])}\n"
                f"• AI review required: {status['config']['ai_review_required']}\n"
                f"• Git watcher available: {status['git_watcher_available']}\n\n"
                "Usage:\n"
                "  /sys !ls - Execute command\n"
                "  /sys @file - View file\n"
                "  /sys /config ai_review_required false - Configure\n"
                "  /sys check logs - AI decision\n"
                "  /sys !execute - Execute pending AI action\n"
                "  /sys !cancel - Cancel pending AI action\n"
                "  /sys !reset - Reset context\n"
                "  /sys !clear_files - Clear file mappings\n"
                "  /sys !allow <cmd> - Add command to allowlist\n"
                "  /sys !allow_list - Show allowlist"
            )
            await update.message.reply_text(status_text)
            return

        # Get current context before routing
        context_before = system.get_context()
        
        # Record AI interaction with full context
        log_entry = {
            'user_id': user_id,
            'input': input_text,
            'context': context_before,
            'timestamp': datetime.now().isoformat(),
            'response': None,
            'error': None
        }
        
        # Route the input through the system
        try:
            response = system.route(input_text)
            # Truncate if too long for Telegram
            if len(response) > 3500:
                response = response[:3500] + "\n[...truncated]"
            
            log_entry['response'] = response
            self.ai_logs.append(log_entry)
            
            await update.message.reply_text(response)
        except Exception as e:
            logger.exception(f"Error in sys_command: {e}")
            log_entry['error'] = str(e)
            self.ai_logs.append(log_entry)
            await update.message.reply_text(f"❌ System error: {str(e)}")

    async def exclamation_alias(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Map plain text messages to /sys route (including full-width exclamation)."""
        if not update.message or not update.message.text:
            return

        text = update.message.text.strip()
        if not text:
            return

        user_id = update.effective_user.id
        if self.allowed_user_ids and user_id not in self.allowed_user_ids:
            await update.message.reply_text("Sorry, you are not authorized to use this bot.")
            return

        # Bare ! or ！: replay last command (check first, don't pollute _last_raw_input)
        if text in ("!", "！"):
            last_raw = self._last_raw_input.get(user_id, "")
            if not last_raw:
                await update.message.reply_text("还没有发送过任何命令。")
                return

            if last_raw.startswith("/"):
                await update.message.reply_text(f"上一次命令是: {last_raw}，直接重发即可。")
                return

            # !-style command: forward to system for replay
            system = self.user_systems.get(user_id)
            if system is None:
                self.user_systems[user_id] = System(
                    git_watcher=self.git_watcher,
                    diff_analyzer=self.diff_analyzer
                )
                system = self.user_systems[user_id]

            try:
                response = system.route(last_raw)
                if len(response) > 3500:
                    response = response[:3500] + "\n[...truncated]"
                await update.message.reply_text(response)
            except Exception as e:
                logger.exception(f"Error in ! replay: {e}")
                await update.message.reply_text(f"❌ 重放命令失败: {str(e)}")
            return

        # Get or create system instance for this user
        if user_id not in self.user_systems:
            self.user_systems[user_id] = System(
                git_watcher=self.git_watcher,
                diff_analyzer=self.diff_analyzer
            )
        system = self.user_systems[user_id]

        # Record raw input + /sys mapping for command history and ! replay
        self._record_command(user_id, f"/sys {text}")

        context_before = system.get_context()
        log_entry = {
            'user_id': user_id,
            'input': text,
            'context': context_before,
            'timestamp': datetime.now().isoformat(),
            'response': None,
            'error': None
        }

        try:
            response = system.route(text)
            if len(response) > 3500:
                response = response[:3500] + "\n[...truncated]"

            log_entry['response'] = response
            self.ai_logs.append(log_entry)
            await update.message.reply_text(response)
        except Exception as e:
            logger.exception(f"Error in exclamation_alias: {e}")
            log_entry['error'] = str(e)
            self.ai_logs.append(log_entry)
            await update.message.reply_text(f"❌ System error: {str(e)}")

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors in the bot."""
        logger.error(f"Update {update} caused error {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "Sorry, an error occurred while processing your request."
            )
    
    async def allow_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /allow command for command allowlist management."""
        user_id = update.effective_user.id
        if self.allowed_user_ids and user_id not in self.allowed_user_ids:
            await update.message.reply_text("Sorry, you are not authorized to use this bot.")
            return

        self._record_command(user_id, update.message.text or "/allow")

        # Get or create system instance for this user
        if user_id not in self.user_systems:
            self.user_systems[user_id] = System(
                git_watcher=self.git_watcher,
                diff_analyzer=self.diff_analyzer
            )
        system = self.user_systems[user_id]

        if not context.args:
            response = system.route("!allow_list")
            await update.message.reply_text(response)
            return

        if context.args[0].lower() == "list":
            response = system.route("!allow_list")
            await update.message.reply_text(response)
            return

        cmd = context.args[0].strip()
        response = system.route(f"!allow {cmd}")
        await update.message.reply_text(response)

    async def log_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /log command to show recent AI interactions."""
        user_id = update.effective_user.id
        if self.allowed_user_ids and user_id not in self.allowed_user_ids:
            return
        
        self._record_command(user_id, update.message.text or "/log")
        
        # Determine how many logs to show
        limit = 10
        if context.args:
            try:
                limit = int(context.args[0])
            except ValueError:
                await update.message.reply_text("Usage: /log [n] where n is number of logs to show (default 10)")
                return
        
        if limit <= 0:
            await update.message.reply_text("n must be a positive integer.")
            return
        
        # Get recent logs
        logs = list(self.ai_logs)[-limit:]
        
        if not logs:
            await update.message.reply_text("No AI logs yet.")
            return
        
        message = f"📝 Recent {len(logs)} AI interactions:\n\n"
        for i, log in enumerate(reversed(logs), 1):
            message += f"{i}. 👤 User: {log['user_id']}\n"
            message += f"   ⏰ {log['timestamp']}\n"
            # Context summary
            if 'context' in log:
                ctx = log['context']
                short_count = len(ctx.get('short_context', []))
                long_preview = ctx.get('long_context', '')[:50]
                message += f"   📋 Context: {short_count} entries"
                if long_preview:
                    message += f", summary: '{long_preview}...'\n"
                else:
                    message += "\n"
            message += f"   📥 Input: {log['input'][:80]}{'...' if len(log['input']) > 80 else ''}\n"
            if log['error']:
                message += f"   ❌ Error: {log['error'][:80]}{'...' if len(log['error']) > 80 else ''}\n"
            else:
                message += f"   📤 Response: {log['response'][:80]}{'...' if len(log['response']) > 80 else ''}\n"
            message += "\n"
        
        await update.message.reply_text(message)

    def run(self):
        """Start the bot."""
        # Create application
        self.application = ApplicationBuilder().token(self.token).build()

        # Add command handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("list", self.list_repositories))
        self.application.add_handler(CommandHandler("check", self.check_repository))
        self.application.add_handler(CommandHandler("ck", self.check_commits))
        self.application.add_handler(CommandHandler("his", self.command_history_handler))
        self.application.add_handler(CommandHandler("file", self.file_from_recent_updates))
        self.application.add_handler(CommandHandler("status", self.status))
        self.application.add_handler(CommandHandler("allow", self.allow_command))
        self.application.add_handler(CommandHandler("sys", self.sys_command))
        self.application.add_handler(CommandHandler("log", self.log_command))
        # Plain text alias: map "！..." to /sys route
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.exclamation_alias))

        # Add error handler
        self.application.add_error_handler(self.error_handler)
        
        # Set bot commands for menu and input suggestions
        import asyncio
        
        # Create and set event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Set bot commands
            loop.run_until_complete(self._set_bot_commands_async())
            
            # Start polling
            logger.info("Starting bot polling...")
            self.application.run_polling(allowed_updates=Update.ALL_TYPES)
        finally:
            loop.close()
    
    async def _set_bot_commands_async(self):
        """Set bot commands for menu and input suggestions (async)."""
        from telegram import BotCommand
        
        commands = [
            BotCommand("start", "启动机器人"),
            BotCommand("help", "显示帮助信息"),
            BotCommand("list", "列出监控的仓库 (支持 /list add <path> <name>)"),
            BotCommand("check", "检查仓库变更 (/check <repo>)"),
            BotCommand("ck", "查看最近提交 (/ck <n> <repo>)"),
            BotCommand("his", "查看命令历史 (/his [n])"),
            BotCommand("file", "查看最近更新的文件 (/file <repo> <fileName>)"),
            BotCommand("status", "查看机器人状态"),
            BotCommand("allow", "管理命令白名单 (/allow [cmd|list])"),
            BotCommand("sys", "AI 路由系统 (!命令 @文件 /配置 AI决策)"),
            BotCommand("log", "查看AI交互日志 (/log [n])"),
        ]
        
        try:
            # Use the bot instance to set commands
            await self.application.bot.set_my_commands(commands)
            logger.info("Bot commands menu set successfully")
        except Exception as e:
            logger.error(f"Failed to set bot commands: {e}")


if __name__ == '__main__':
    # Test the bot (requires actual configuration)
    import yaml
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python telegram_bot.py <config_file>")
        sys.exit(1)

    config_file = sys.argv[1]
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    token = config['telegram']['token']
    repo_configs = config['repositories']
    allowed_user_ids = config['telegram'].get('allowed_user_ids', [])

    git_watcher = GitWatcher(repo_configs)
    diff_analyzer = DiffAnalyzer(git_watcher)
    bot = GitTelegramBot(token, git_watcher, diff_analyzer, allowed_user_ids)
    bot.run()