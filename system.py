#!/usr/bin/env python3
"""
AI Router + Context System for Git-Telegram bot.

Implements a low-token, high-control remote operating system with four input modes:
1. ! direct command (0 AI)
2. @ file reference (multiple selection)
3. default AI decision (restricted)
4. /config dynamic configuration

Core principle: AI only makes decisions, does not directly touch the system.

This version uses modular components:
- FileManager for file operations
- CommandExecutor for command execution
- ConfigManager for configuration
- ContextManager for conversation context
- ActionDispatcher for action execution
- LLMEngine for AI decisions
"""

import os
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from file_manager import FileManager
from command_executor import CommandExecutor
from config_manager import ConfigManager
from context_manager import ContextManager
from action_dispatcher import ActionDispatcher
from llm_engine import call_ai, get_default_engine, LLMEngine

logger = logging.getLogger(__name__)


class System:
    """
    Main system class implementing the AI Router + Context System.
    """

    def __init__(self, git_watcher=None, diff_analyzer=None):
        """
        Initialize the system.
        
        Args:
            git_watcher: Optional GitWatcher instance for Git operations
            diff_analyzer: Optional DiffAnalyzer instance for diff analysis
        """
        # Initialize managers
        self.config_manager = ConfigManager()
        self.context_manager = ContextManager(
            max_short_context=self.config_manager.get("max_short_context"),
            max_short_length=self.config_manager.get("max_short_length"),
            max_long_length=self.config_manager.get("max_long_length")
        )
        
        self.file_manager = FileManager(
            file_search_cutoff=self.config_manager.get("file_search_cutoff"),
            file_search_limit=self.config_manager.get("file_search_limit")
        )
        
        self.command_executor = CommandExecutor(
            allowed_commands=self.config_manager.get("allowed_commands"),
            command_safety_check=self.config_manager.get("command_safety_check")
        )
        
        self.action_dispatcher = ActionDispatcher(
            git_watcher=git_watcher,
            diff_analyzer=diff_analyzer,
            command_executor=self.command_executor,
            file_manager=self.file_manager
        )
        
        # LLM engine is initialized lazily on first AI request.
        # This keeps direct command paths (! / ！ / /cmd) usable even when no API key is set.
        self.llm_engine = None
        
        # Pending AI action for review
        self.pending_action = None
        
        logger.info("System initialized with modular AI Router + Context System")

    # ===== Router =====

    def route(self, text: str) -> str:
        """
        Route input based on prefix.
        
        Args:
            text: User input text
            
        Returns:
            Response string
        """
        text = text.strip()
        
        if not text:
            return "Empty input"
        
        # Update short context with user input
        self.context_manager.add_entry("user", text)
        
        # Handle y/n confirmation for pending AI action
        if self.pending_action:
            lower_text = text.lower()
            if lower_text == "y" or lower_text == "yes":
                response = self._execute_pending_action()
                self.context_manager.add_entry("system", response)
                return response
            elif lower_text == "n" or lower_text == "no":
                response = self._cancel_pending_action()
                self.context_manager.add_entry("system", response)
                return response
        
        response = ""

        # Map full-width exclamation to explicit /cmd path while preserving the leading marker.
        # Example: "！pwd" -> "/cmd ！pwd"
        if text.startswith("！"):
            response = self._handle_cmd_route(f"/cmd {text}")
        elif text.startswith("!"):
            response = self._handle_cmd_route(f"/cmd {text}")
        elif text.startswith("/cmd"):
            response = self._handle_cmd_route(text)
        elif text.startswith("@"):
            # Handle file references
            file_key = text[1:].strip()
            response = self.file_manager.handle_file_reference(file_key)
        elif text.startswith("/config"):
            response = self.config_manager.handle_config_command(text)
        else:
            response = self._handle_ai(text)
        
        # Update short context with system response
        self.context_manager.add_entry("system", response)
        
        return response

    def _handle_cmd_route(self, text: str) -> str:
        """Handle unified /cmd route and its aliases (! / ！)."""
        # Normalize into payload after /cmd
        payload = text[len("/cmd"):].strip() if text.startswith("/cmd") else text.strip()
        if not payload:
            return "用法: !<command>"

        # Keep semantic marker but strip it before execution
        if payload.startswith("!") or payload.startswith("！"):
            cmd_text = payload[1:].strip()
        else:
            cmd_text = payload

        if not cmd_text:
            return "用法: !<command>"

        # Special system commands
        if cmd_text == "execute":
            return self._execute_pending_action()
        if cmd_text == "cancel":
            return self._cancel_pending_action()
        if cmd_text == "reset":
            return self.reset_context()
        if cmd_text == "clear_files":
            return self.clear_file_map()
        if cmd_text == "allow_list":
            allowed = self.command_executor.allowed_commands
            return "Allowed commands: " + ", ".join(allowed)
        if cmd_text.startswith("allow "):
            new_cmd = cmd_text[len("allow "):].strip()
            return self._add_allowed_command(new_cmd)

        return self.command_executor.execute(cmd_text)

    def _add_allowed_command(self, cmd_base: str) -> str:
        """Add a command base to whitelist at runtime."""
        cmd_base = (cmd_base or "").strip().split()[0] if cmd_base else ""
        if not cmd_base:
            return "Usage: !allow <command_base>"

        current = list(self.config_manager.get("allowed_commands", []))
        if cmd_base in current:
            return f"'{cmd_base}' is already in allowlist."

        current.append(cmd_base)
        self.config_manager.set("allowed_commands", current)
        self.command_executor.allowed_commands = current
        return f"Added '{cmd_base}' to allowlist."

    # ===== AI Decision =====

    def _build_ai_input(self, user_input: str) -> Dict[str, Any]:
        """
        Build input for AI decision engine.
        
        Args:
            user_input: User's input text
            
        Returns:
            Structured input for AI
        """
        # Get context for AI
        ai_short_context = self.context_manager.get_short_context(for_ai=True)
        ai_long_context = self.context_manager.get_long_context()
        
        # Prepare available actions
        available_actions = self.action_dispatcher.get_available_actions()
        
        # Prepare file mappings for AI
        file_mappings = self.file_manager.get_file_mappings()
        
        return {
            "user_input": user_input,
            "short_context": ai_short_context,
            "long_context": ai_long_context,
            "available_actions": available_actions,
            "file_mappings": file_mappings,
            "current_time": datetime.now().isoformat()
        }

    def _handle_ai(self, text: str) -> str:
        """
        Handle AI decision mode.
        
        Args:
            text: User input
            
        Returns:
            Response string
        """
        # Build AI input
        ai_input = self._build_ai_input(text)

        # Lazily initialize LLM engine only for AI mode.
        # No mock fallback: missing config/key will still raise here.
        if self.llm_engine is None:
            self.llm_engine = get_default_engine()
            logger.info(f"LLM engine initialized with provider: {self.llm_engine.provider}")

        # Call AI (real implementation via LLM engine)
        ai_output = call_ai(ai_input)
        
        # If review required, ask for confirmation
        if self.config_manager.get("ai_review_required", True):
            # Store pending action
            self.pending_action = ai_output
            action = ai_output.get("action", "unknown")
            target = ai_output.get("target", "")

            # Human-friendly preview of what will run
            if action == "execute_safe":
                action_desc = f"命令: {target or 'N/A'}"
            else:
                desc = self.action_dispatcher.get_action_description(action)
                if target:
                    action_desc = f"{desc} | target: {target}"
                else:
                    action_desc = desc

            return (
                f"🤖 AI suggests: {action_desc}\n"
                f"Action JSON: {{\"action\": \"{action}\", \"target\": \"{target}\"}}\n"
                f"Reason: {ai_output.get('reason', 'No reason provided')}\n\n"
                f"回复 y 执行，n 取消。"
            )
        
        # Execute directly if review not required
        return self._execute_action(ai_output)

    # ===== Action Execution =====

    def _execute_pending_action(self) -> str:
        """
        Execute the pending AI action.
        
        Returns:
            Execution result or error if no pending action
        """
        if not self.pending_action:
            return "No pending action to execute."
        
        action_spec = self.pending_action
        self.pending_action = None
        return self._execute_action(action_spec)
    
    def _cancel_pending_action(self) -> str:
        """
        Cancel the pending AI action.
        
        Returns:
            Confirmation message
        """
        if not self.pending_action:
            return "No pending action to cancel."
        
        action_desc = self.action_dispatcher.get_action_description(self.pending_action["action"])
        self.pending_action = None
        return f"Pending action '{action_desc}' cancelled."

    def _execute_action(self, action_spec: Dict[str, Any]) -> str:
        """
        Execute an action from the DSL.
        
        Args:
            action_spec: Action specification from AI
            
        Returns:
            Execution result
        """
        # Delegate to action dispatcher
        return self.action_dispatcher.execute_action(action_spec)

    # ===== Configuration Updates =====
    
    def update_config(self, key: str, value: Any) -> None:
        """
        Update configuration and propagate to managers.
        
        Args:
            key: Configuration key
            value: New value
        """
        self.config_manager.set(key, value)
        
        # Update dependent managers if relevant config changed
        if key == "max_short_context":
            self.context_manager.max_short_context = value
        elif key == "max_short_length":
            self.context_manager.max_short_length = value
        elif key == "max_long_length":
            self.context_manager.max_long_length = value
        elif key == "file_search_cutoff":
            self.file_manager.file_search_cutoff = value
        elif key == "file_search_limit":
            self.file_manager.file_search_limit = value
        elif key == "allowed_commands":
            self.command_executor.allowed_commands = value
        elif key == "command_safety_check":
            self.command_executor.command_safety_check = value

    # ===== Utility Methods =====

    def get_status(self) -> Dict[str, Any]:
        """
        Get system status.
        
        Returns:
            Status dictionary
        """
        return {
            "config": self.config_manager.get_all(),
            "file_map_count": len(self.file_manager.file_map),
            "short_context_count": len(self.context_manager.short_context),
            "long_context": self.context_manager.long_context,
            "available_actions": self.action_dispatcher.get_available_actions(),
            "git_watcher_available": self.action_dispatcher.git_watcher is not None,
            "diff_analyzer_available": self.action_dispatcher.diff_analyzer is not None,
            "llm_provider": str(self.llm_engine.provider),
        }
    
    def get_context(self) -> Dict[str, Any]:
        """
        Get current context for logging.
        
        Returns:
            Dictionary with short_context and long_context
        """
        return {
            "short_context": self.context_manager.short_context.copy(),
            "long_context": self.context_manager.long_context,
        }

    def reset_context(self) -> str:
        """Reset context (short and long)."""
        self.context_manager.clear()
        return "Context reset."

    def clear_file_map(self) -> str:
        """Clear file mappings."""
        return self.file_manager.clear_mappings()


# ===== Simple CLI for testing =====

if __name__ == "__main__":
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    # Create a simple system instance
    system = System()
    
    print("AI Router + Context System Test")
    print("Commands: !cmd, @file, /config, or AI decision")
    print("Type 'exit' to quit\n")
    
    while True:
        try:
            user_input = input("> ").strip()
            if user_input.lower() in ["exit", "quit"]:
                break
            
            response = system.route(user_input)
            print(f"\n{response}\n")
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")