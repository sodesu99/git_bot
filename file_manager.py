#!/usr/bin/env python3
"""
File Manager for AI Router + Context System.

Handles file mapping, searching, and reading.
"""

import os
import difflib
from typing import Dict, List, Optional


class FileManager:
    """
    Manages file mappings and file operations.
    """
    
    def __init__(self, file_search_cutoff: float = 0.3, file_search_limit: int = 5):
        """
        Initialize file manager.
        
        Args:
            file_search_cutoff: Similarity cutoff for file search (0.0-1.0)
            file_search_limit: Maximum number of search results
        """
        self.file_search_cutoff = file_search_cutoff
        self.file_search_limit = file_search_limit
        
        # File mapping: F1 -> real path
        self.file_map: Dict[str, str] = {}
        # Reverse mapping: path -> F1
        self.reverse_file_map: Dict[str, str] = {}
        # Last file search candidates (for multi-file selection)
        self.last_candidates: Dict[str, str] = {}
        
        # Track file counter for mapping
        self.file_counter = 1
    
    def handle_file_reference(self, key: str) -> str:
        """
        Handle file reference starting with @.
        
        Args:
            key: File identifier (F1, F2, or search keyword)
            
        Returns:
            File content or list of candidates
        """
        # Check if it's a mapped file identifier (F1, F2, etc.)
        if key in self.file_map:
            path = self.file_map[key]
            return self._read_file(path)
        
        # Check if it's a single-character selection from last candidates
        if len(key) == 1 and key in self.last_candidates:
            path = self.last_candidates[key]
            return self._read_file(path)
        
        # Otherwise, search for files
        files = self.search_files(key)
        
        if not files:
            return f"No files found matching '{key}'"
        
        # Single file found
        if len(files) == 1:
            path = files[0]
            # Create mapping if not exists
            if path not in self.reverse_file_map:
                file_id = f"F{self.file_counter}"
                self.file_map[file_id] = path
                self.reverse_file_map[path] = file_id
                self.file_counter += 1
                return f"Mapped {file_id} -> {path}\n\n{self._read_file(path)}"
            else:
                file_id = self.reverse_file_map[path]
                return f"{file_id} -> {path}\n\n{self._read_file(path)}"
        
        # Multiple files found - present as candidates
        self.last_candidates = {}
        response_lines = ["Multiple files found:"]
        for i, path in enumerate(files[:5]):  # Limit to 5
            candidate_key = chr(97 + i)  # a, b, c, d, e
            self.last_candidates[candidate_key] = path
            response_lines.append(f"  {candidate_key}. {path}")
        
        response_lines.append("\nSelect with @a, @b, etc.")
        return "\n".join(response_lines)
    
    def search_files(self, keyword: str) -> List[str]:
        """
        Search for files matching keyword.
        
        Args:
            keyword: Search term
            
        Returns:
            List of matching file paths
        """
        all_files = []
        for root, _, files in os.walk("."):
            for f in files:
                all_files.append(os.path.join(root, f))
        
        # Use difflib for fuzzy matching
        matches = difflib.get_close_matches(
            keyword, 
            all_files, 
            n=self.file_search_limit, 
            cutoff=self.file_search_cutoff
        )
        
        return matches
    
    def _read_file(self, path: str) -> str:
        """
        Read file content.
        
        Args:
            path: File path
            
        Returns:
            File content (truncated)
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                return content[:4000] + ("..." if len(content) > 4000 else "")
        except UnicodeDecodeError:
            # Try binary mode
            try:
                with open(path, 'rb') as f:
                    return f"[Binary file: {path}]"
            except Exception as e:
                return f"Error reading file: {str(e)}"
        except Exception as e:
            return f"Error reading file: {str(e)}"
    
    def get_file_mappings(self) -> Dict[str, str]:
        """
        Get current file mappings.
        
        Returns:
            Dictionary of file_id -> path
        """
        return self.file_map.copy()
    
    def clear_mappings(self) -> str:
        """Clear all file mappings."""
        self.file_map = {}
        self.reverse_file_map = {}
        self.file_counter = 1
        self.last_candidates = {}
        return "File mappings cleared."
    
    def get_status(self) -> Dict[str, any]:
        """
        Get file manager status.
        
        Returns:
            Status dictionary
        """
        return {
            "file_map_count": len(self.file_map),
            "last_candidates_count": len(self.last_candidates),
            "file_search_cutoff": self.file_search_cutoff,
            "file_search_limit": self.file_search_limit,
        }