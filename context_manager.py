#!/usr/bin/env python3
"""
Context Manager for AI Router + Context System.

Manages short-term and long-term conversation context.
"""

from typing import Dict, List, Any, Optional


class ContextManager:
    """
    Manages conversation context.
    """
    
    def __init__(self, max_short_context: int = 5, max_short_length: int = 20, 
                 max_long_length: int = 50):
        """
        Initialize context manager.
        
        Args:
            max_short_context: Maximum number of short context entries
            max_short_length: Maximum length of each short context entry
            max_long_length: Maximum length of long context summary
        """
        self.max_short_context = max_short_context
        self.max_short_length = max_short_length
        self.max_long_length = max_long_length
        
        # Short context: List of dicts: {"role": "user"/"system", "text": str}
        self.short_context: List[Dict[str, str]] = []
        # Long context summary
        self.long_context = ""
    
    def add_entry(self, role: str, text: str) -> None:
        """
        Add an entry to short context.
        
        Args:
            role: "user" or "system"
            text: Text content
        """
        truncated = text[:100]  # Keep more for internal use, truncate for AI later
        entry = {"role": role, "text": truncated}
        self.short_context.append(entry)
        
        # Keep only last N entries (more than AI needs for internal reference)
        max_entries = self.max_short_context * 2
        if len(self.short_context) > max_entries:
            self.short_context = self.short_context[-max_entries:]
        
        # Update long context
        self._update_long_context()
    
    def _update_long_context(self) -> None:
        """Update long context (summary of recent activity)."""
        # Simple implementation: summarize last few entries
        if len(self.short_context) >= 3:
            recent = self.short_context[-3:]
            summary_parts = []
            for entry in recent:
                role_char = "U" if entry["role"] == "user" else "S"
                summary_parts.append(f"{role_char}:{entry['text'][:30]}")
            
            self.long_context = " | ".join(summary_parts)[:self.max_long_length]
        else:
            self.long_context = ""
    
    def get_short_context(self, for_ai: bool = False) -> List[Dict[str, str]]:
        """
        Get short context, optionally truncated for AI.
        
        Args:
            for_ai: If True, truncate to max_short_context and max_short_length
            
        Returns:
            List of context entries
        """
        if not for_ai:
            return self.short_context.copy()
        
        # Truncate for AI
        ai_short_context = []
        for entry in self.short_context[-self.max_short_context:]:
            truncated_text = entry["text"][:self.max_short_length]
            ai_short_context.append({
                "role": entry["role"],
                "text": truncated_text
            })
        return ai_short_context
    
    def get_long_context(self) -> str:
        """
        Get long context.
        
        Returns:
            Long context string
        """
        return self.long_context
    
    def clear(self) -> None:
        """Clear all context."""
        self.short_context = []
        self.long_context = ""
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get context manager status.
        
        Returns:
            Status dictionary
        """
        return {
            "short_context_count": len(self.short_context),
            "long_context": self.long_context,
            "max_short_context": self.max_short_context,
            "max_short_length": self.max_short_length,
            "max_long_length": self.max_long_length,
        }