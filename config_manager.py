#!/usr/bin/env python3
"""
Configuration Manager for AI Router + Context System.

Manages system configuration with get/set operations.
"""

import json
from typing import Any, Dict, Optional


class ConfigManager:
    """
    Manages system configuration.
    """
    
    DEFAULT_CONFIG = {
        "ai_review_required": True,
        "command_safety_check": True,
        "max_short_context": 5,
        "max_short_length": 20,
        "max_long_length": 50,
        "file_search_cutoff": 0.3,
        "file_search_limit": 5,
        "allowed_commands": [
            "ls", "pwd", "whoami", "date", "uptime", "ll", "git",
            "cat", "head", "tail", "grep", "rg", "find", "wc", "echo",
            "which", "stat", "du", "df", "ps", "tree"
        ],
    }
    
    def __init__(self, initial_config: Optional[Dict[str, Any]] = None):
        """
        Initialize configuration manager.
        
        Args:
            initial_config: Initial configuration dictionary (merged with defaults)
        """
        self.config = self.DEFAULT_CONFIG.copy()
        if initial_config:
            self.config.update(initial_config)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value.
        
        Args:
            key: Configuration key
            value: New value
        """
        # Type conversion for string inputs
        if isinstance(value, str):
            if value.lower() in ["true", "false"]:
                value = value.lower() == "true"
            elif value.isdigit():
                value = int(value)
        
        self.config[key] = value
    
    def handle_config_command(self, text: str) -> str:
        """
        Handle configuration commands (format: /config [key] [value]).
        
        Args:
            text: /config command text
            
        Returns:
            Configuration status or update result
        """
        parts = text.split()
        
        if len(parts) == 1:
            # Show current config
            config_display = json.dumps(self.config, indent=2)
            return f"Current configuration:\n```json\n{config_display}\n```"
        
        if len(parts) == 2:
            # Get specific config value
            key = parts[1]
            if key in self.config:
                return f"{key} = {self.config[key]}"
            else:
                return f"Unknown config key: {key}"
        
        # Set config value
        _, key, value = parts[:3]
        self.set(key, value)
        return f"Updated {key} = {value}"
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get all configuration.
        
        Returns:
            Complete configuration dictionary
        """
        return self.config.copy()
    
    def update(self, updates: Dict[str, Any]) -> None:
        """
        Update multiple configuration values.
        
        Args:
            updates: Dictionary of key-value updates
        """
        self.config.update(updates)
    
    def reset_to_defaults(self) -> str:
        """
        Reset configuration to defaults.
        
        Returns:
            Confirmation message
        """
        self.config = self.DEFAULT_CONFIG.copy()
        return "Configuration reset to defaults."