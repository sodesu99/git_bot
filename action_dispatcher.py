#!/usr/bin/env python3
"""
Action Dispatcher for AI Router + Context System.

Dispatches and executes actions from the DSL.
"""

import os
import subprocess
from typing import Dict, Any, Optional, Callable


class ActionDispatcher:
    """
    Dispatches and executes actions.
    """
    
    def __init__(self, git_watcher=None, diff_analyzer=None, command_executor=None, file_manager=None):
        """
        Initialize action dispatcher.
        
        Args:
            git_watcher: Optional GitWatcher instance for Git operations
            diff_analyzer: Optional DiffAnalyzer instance for diff analysis
            command_executor: Optional CommandExecutor for safe command execution
            file_manager: Optional FileManager for file operations
        """
        self.git_watcher = git_watcher
        self.diff_analyzer = diff_analyzer
        self.command_executor = command_executor
        self.file_manager = file_manager
        
        # Action DSL definitions
        self.actions = {
            "git_pull": "Pull latest changes from remote repository",
            "git_status": "Check repository status",
            "check_logs": "Check logs of a service",
            "restart_service": "Restart a service (e.g., docker container)",
            "deploy": "Deploy application",
            "check_repo": "Check repository for changes",
            "view_file": "View file content",
            "list_files": "List files in directory",
            "execute_safe": "Execute a safe shell command",
        }
        
        # Action to handler mapping
        self.handlers = {
            "git_pull": self._handle_git_pull,
            "git_status": self._handle_git_status,
            "check_logs": self._handle_check_logs,
            "restart_service": self._handle_restart_service,
            "deploy": self._handle_deploy,
            "check_repo": self._handle_check_repo,
            "view_file": self._handle_view_file,
            "list_files": self._handle_list_files,
            "execute_safe": self._handle_execute_safe,
        }
    
    def execute_action(self, action_spec: Dict[str, Any]) -> str:
        """
        Execute an action from the DSL.
        
        Args:
            action_spec: Action specification with keys: action, target, reason
            
        Returns:
            Execution result
        """
        action = action_spec.get("action")
        
        if not action:
            return "No action specified"
        
        # Check if action is available
        if action not in self.handlers:
            return f"Unknown action: {action}. Available: {', '.join(self.handlers.keys())}"
        
        try:
            # Call the action handler
            handler = self.handlers[action]
            return handler(action_spec)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.exception(f"Error executing action {action}")
            return f"Error executing {action}: {str(e)}"
    
    def get_available_actions(self) -> list:
        """
        Get list of available action names.
        
        Returns:
            List of action names
        """
        return list(self.actions.keys())
    
    def get_action_description(self, action: str) -> str:
        """
        Get description of an action.
        
        Args:
            action: Action name
            
        Returns:
            Action description
        """
        return self.actions.get(action, "Unknown action")
    
    # ===== Action Handlers =====
    
    def _handle_git_pull(self, action_spec: Dict[str, Any]) -> str:
        """Handle git pull action."""
        if not self.git_watcher:
            return "Git watcher not available"
        
        target = action_spec.get("target", "current")
        # For now, just pull current directory
        try:
            result = subprocess.run(
                ["git", "pull"],
                capture_output=True,
                text=True,
                cwd=os.getcwd(),
                timeout=30
            )
            if result.returncode == 0:
                return f"Git pull successful:\n{result.stdout[:2000]}"
            else:
                return f"Git pull failed:\n{result.stderr[:2000]}"
        except Exception as e:
            return f"Git pull error: {str(e)}"
    
    def _handle_git_status(self, action_spec: Dict[str, Any]) -> str:
        """Handle git status action."""
        try:
            result = subprocess.run(
                ["git", "status"],
                capture_output=True,
                text=True,
                cwd=os.getcwd(),
                timeout=10
            )
            if result.returncode == 0:
                return f"Git status:\n{result.stdout[:2000]}"
            else:
                return f"Git status error:\n{result.stderr[:2000]}"
        except Exception as e:
            return f"Git status error: {str(e)}"
    
    def _handle_check_logs(self, action_spec: Dict[str, Any]) -> str:
        """Handle check logs action."""
        target = action_spec.get("target", "service")
        # Simple log check - last 10 lines of common log files
        log_files = [
            "/var/log/syslog",
            "/var/log/messages",
            "/var/log/docker.log",
            "./logs/app.log",
            "./log/development.log"
        ]
        
        results = []
        for log_file in log_files:
            if os.path.exists(log_file):
                try:
                    result = subprocess.run(
                        ["tail", "-20", log_file],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        results.append(f"{log_file}:\n{result.stdout[:1000]}")
                except:
                    pass
        
        if results:
            return "Recent logs:\n" + "\n---\n".join(results[:3])
        else:
            return "No common log files found or accessible."
    
    def _handle_restart_service(self, action_spec: Dict[str, Any]) -> str:
        """Handle restart service action."""
        target = action_spec.get("target", "unknown")
        # Safety check - only allow specific services
        allowed_services = ["docker", "nginx", "redis"]
        
        if target not in allowed_services:
            return f"Service '{target}' not in allowed list: {', '.join(allowed_services)}"
        
        return f"Would restart service '{target}' (simulated). In production, actual restart would occur."
    
    def _handle_deploy(self, action_spec: Dict[str, Any]) -> str:
        """Handle deploy action."""
        target = action_spec.get("target", "app")
        return f"Would deploy '{target}' (simulated)."
    
    def _handle_check_repo(self, action_spec: Dict[str, Any]) -> str:
        """Handle check repo action (Git-Telegram specific)."""
        if not self.git_watcher:
            return "Git watcher not available for repository checks."
        
        target = action_spec.get("target", "default")
        repos = self.git_watcher.list_repositories()
        
        if not repos:
            return "No repositories configured."
        
        # Check first repository
        repo_name = repos[0]
        has_changes, changed_files, error = self.git_watcher.check_repository(repo_name)
        
        if error:
            return f"Error checking '{repo_name}': {error}"
        
        if not has_changes:
            return f"Repository '{repo_name}' has no new changes."
        
        if self.diff_analyzer:
            analysis = self.diff_analyzer.analyze_changes(repo_name, changed_files)
            message, _ = self.diff_analyzer.format_message_for_telegram(analysis)
            return f"Changes in '{repo_name}':\n\n{message[:3000]}"
        else:
            return f"Changes in '{repo_name}': {len(changed_files)} files changed."
    
    def _handle_view_file(self, action_spec: Dict[str, Any]) -> str:
        """Handle view file action."""
        if not self.file_manager:
            return "File manager not available."
        
        target = action_spec.get("target", "")
        if not target:
            return "No file target specified."
        
        # Delegate to file manager
        return self.file_manager.handle_file_reference(target)
    
    def _handle_list_files(self, action_spec: Dict[str, Any]) -> str:
        """Handle list files action."""
        target = action_spec.get("target", ".")
        
        try:
            result = subprocess.run(
                ["ls", "-la", target],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return f"Files in '{target}':\n{result.stdout[:2000]}"
            else:
                return f"Error listing '{target}': {result.stderr[:1000]}"
        except Exception as e:
            return f"Error listing files: {str(e)}"
    
    def _handle_execute_safe(self, action_spec: Dict[str, Any]) -> str:
        """Handle safe command execution."""
        target = action_spec.get("target", "")
        if not target:
            return "No command specified."
        
        # Use command executor if available
        if self.command_executor:
            return self.command_executor.execute(target)
        
        # Otherwise, execute directly with basic safety check
        # This replicates the old safety logic
        def is_safe_command(cmd: str) -> bool:
            # Basic safe commands
            safe_commands = ["pwd", "whoami", "date", "uptime", "ls", "ls -la"]
            if cmd in safe_commands:
                return True
            
            # Allow ls with arguments
            if cmd.startswith("ls "):
                return True
            
            # Allow safe git commands
            if cmd.startswith("git "):
                safe_git_commands = ["init", "add", "commit", "push", "clone", "status", "pull", "log", "diff"]
                git_parts = cmd.split()
                if len(git_parts) >= 2:
                    git_subcommand = git_parts[1]
                    if git_subcommand in safe_git_commands:
                        return True
            
            return False
        
        if not is_safe_command(target):
            return f"Command '{target}' not allowed for safe execution."
        
        try:
            result = subprocess.run(
                target,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
                cwd=os.getcwd()
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                return output[:4000] if output else "(no output)"
            else:
                error = result.stderr.strip()
                return f"Error (exit {result.returncode}): {error[:2000]}"
                
        except subprocess.TimeoutExpired:
            return "Command timed out after 10 seconds"
        except Exception as e:
            return f"Execution error: {str(e)}"