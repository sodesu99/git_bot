#!/usr/bin/env python3
"""
Command Executor for AI Router + Context System.

Handles safe execution of shell commands.
"""

import os
import subprocess
from typing import List, Optional


class CommandExecutor:
    """
    Executes shell commands with safety checks.
    """
    
    def __init__(self, allowed_commands: Optional[List[str]] = None, 
                 command_safety_check: bool = True, timeout: int = 10):
        """
        Initialize command executor.
        
        Args:
            allowed_commands: List of allowed command bases (e.g., ["ls", "pwd"])
            command_safety_check: Whether to enforce command safety checks
            timeout: Command timeout in seconds
        """
        self.allowed_commands = allowed_commands or [
            "ls", "pwd", "whoami", "date", "uptime", "ll", "git",
            "cat", "head", "tail", "grep", "rg", "find", "wc", "echo",
            "which", "stat", "du", "df", "ps", "tree"
        ]
        self.command_safety_check = command_safety_check
        self.timeout = timeout
    
    def execute(self, cmd: str, cwd: Optional[str] = None) -> str:
        """
        Execute a command with safety checks.
        
        Args:
            cmd: Command string
            cwd: Working directory (defaults to current)
            
        Returns:
            Command output or error
        """
        # Security: check if command is allowed (skip if command_safety_check is False)
        if self.command_safety_check:
            cmd_base = cmd.split()[0] if cmd.split() else ""
            
            # Handle aliases
            if cmd_base == "ll":
                # Convert ll to ls -la
                args = cmd.split()[1:] if len(cmd.split()) > 1 else []
                cmd = "ls -la " + " ".join(args)
                cmd_base = "ls"
            
            if cmd_base not in self.allowed_commands:
                return f"Command '{cmd_base}' not in allowed list. Allowed: {', '.join(self.allowed_commands)}"
        
        try:
            # Execute with timeout
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=cwd or os.getcwd()
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                return output[:4000] if output else "(no output)"
            else:
                error = result.stderr.strip()
                return f"Error (exit {result.returncode}): {error[:2000]}"
                
        except subprocess.TimeoutExpired:
            return f"Command timed out after {self.timeout} seconds"
        except Exception as e:
            return f"Execution error: {str(e)}"
    
    def is_safe_command(self, cmd: str) -> bool:
        """
        Check if a command is safe for execution.
        
        Args:
            cmd: Command string
            
        Returns:
            True if command is considered safe
        """
        if not self.command_safety_check:
            return True
        
        cmd_base = cmd.split()[0] if cmd.split() else ""
        
        # Handle aliases
        if cmd_base == "ll":
            cmd_base = "ls"
        
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
        
        return cmd_base in self.allowed_commands
    
    def get_status(self) -> dict:
        """
        Get command executor status.
        
        Returns:
            Status dictionary
        """
        return {
            "allowed_commands": self.allowed_commands,
            "command_safety_check": self.command_safety_check,
            "timeout": self.timeout
        }