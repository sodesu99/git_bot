#!/usr/bin/env python3
"""
Diff analyzer module for processing Git changes and generating user-friendly messages.
"""

import os
import logging
from typing import List, Dict, Optional, Tuple
from git_watcher import GitWatcher

logger = logging.getLogger(__name__)


class DiffAnalyzer:
    """Analyzes Git differences and prepares messages for users."""

    def __init__(self, git_watcher: GitWatcher):
        self.git_watcher = git_watcher

    def analyze_changes(self, repo_name: str, changed_files: List[str]) -> Dict[str, any]:
        """
        Analyze changed files and prepare a report.

        Args:
            repo_name: Repository name
            changed_files: List of changed file paths

        Returns:
            Dictionary with analysis results:
            {
                'repo_name': str,
                'file_count': int,
                'files': [
                    {
                        'path': str,
                        'content_preview': str,
                        'line_count': int,
                        'truncated': bool
                    }
                ],
                'summary': str
            }
        """
        if not changed_files:
            return {
                'repo_name': repo_name,
                'file_count': 0,
                'files': [],
                'summary': 'No files changed'
            }

        # Read content for each file
        files_info = []
        total_lines = 0
        max_total_lines = 100  # Limit total lines across all files
        max_lines_per_file = 30

        for file_path in changed_files:
            content = self.git_watcher.read_file_content(repo_name, file_path, max_lines_per_file)
            line_count = 0
            truncated = False

            if content is not None:
                lines = content.split('\n')
                line_count = len(lines)
                # Check if content was truncated by read_file_content
                if line_count >= max_lines_per_file and lines[-1].startswith('... (truncated'):
                    truncated = True
                    line_count = max_lines_per_file - 1

                # Further truncation if we're exceeding total budget
                if total_lines + line_count > max_total_lines:
                    allowed_lines = max(0, max_total_lines - total_lines)
                    if allowed_lines > 0:
                        content = '\n'.join(lines[:allowed_lines])
                        content += f'\n... (truncated, showing {allowed_lines} of {line_count} lines)'
                        line_count = allowed_lines
                    else:
                        content = f'(skipped, reached total line limit)'
                        line_count = 0

                total_lines += line_count
            else:
                content = '(unable to read file)'

            files_info.append({
                'path': file_path,
                'content_preview': content,
                'line_count': line_count,
                'truncated': truncated or (line_count >= max_lines_per_file)
            })

        # Generate summary
        summary = f"Found {len(changed_files)} changed file(s) in '{repo_name}':\n"
        for file_info in files_info:
            summary += f"- {file_info['path']} ({file_info['line_count']} lines shown)\n"

        return {
            'repo_name': repo_name,
            'file_count': len(changed_files),
            'files': files_info,
            'summary': summary.strip()
        }

    def format_message_for_telegram(self, analysis: Dict[str, any], max_length: int = 4000) -> Tuple[str, bool]:
        """
        Format analysis results into a Telegram message.

        Args:
            analysis: Analysis dictionary from analyze_changes
            max_length: Maximum message length for Telegram

        Returns:
            Tuple of (message, truncated_flag)
        """
        repo_name = analysis['repo_name']
        file_count = analysis['file_count']

        if file_count == 0:
            return f"Repository '{repo_name}' has no changes.", False

        # Build message parts
        parts = []
        parts.append(f"📊 Changes detected in '{repo_name}' ({file_count} file(s)):\n")

        for i, file_info in enumerate(analysis['files'], 1):
            file_part = f"\n{i}. {file_info['path']}:\n"
            file_part += "```\n"
            file_part += file_info['content_preview']
            file_part += "\n```\n"

            # Check if adding this file would exceed limit
            if len('\n'.join(parts) + file_part) > max_length:
                # Truncate and indicate more files remain
                remaining = file_count - (i - 1)
                parts.append(f"\n... and {remaining} more file(s) (message too long)")
                return '\n'.join(parts), True

            parts.append(file_part)

        message = '\n'.join(parts)

        # Final truncation if still too long (shouldn't happen with above check)
        if len(message) > max_length:
            message = message[:max_length - 100] + "\n... (truncated)"
            return message, True

        return message, False

    def format_compact_message(self, analysis: Dict[str, any]) -> str:
        """Format a compact summary message."""
        repo_name = analysis['repo_name']
        file_count = analysis['file_count']

        if file_count == 0:
            return f"Repository '{repo_name}' has no changes."

        file_list = ', '.join([f['path'] for f in analysis['files'][:5]])
        if file_count > 5:
            file_list += f" and {file_count - 5} more"

        return f"📦 {repo_name}: {file_count} changed file(s)\nFiles: {file_list}"

    def get_file_extensions(self, changed_files: List[str]) -> Dict[str, int]:
        """Count file extensions in changed files."""
        extensions = {}
        for file_path in changed_files:
            # Skip directories (should already be filtered, but double-check)
            if file_path.endswith('/'):
                continue
            
            # Remove surrounding quotes if present
            clean_path = file_path
            if clean_path.startswith('"') and clean_path.endswith('"'):
                clean_path = clean_path[1:-1]
            
            # Extract extension (last part after dot, but not including path separators)
            basename = os.path.basename(clean_path)
            if '.' in basename:
                # Split by dot and get last part
                parts = basename.split('.')
                if len(parts) > 1:
                    ext = parts[-1].lower()
                    # Filter out empty extensions and common backup patterns
                    if ext and not ext.endswith('~') and ext not in ['backup', 'bak', 'new']:
                        extensions[ext] = extensions.get(ext, 0) + 1
                    else:
                        # Backup files or special extensions
                        extensions['backup'] = extensions.get('backup', 0) + 1
            else:
                # No extension
                extensions['no_extension'] = extensions.get('no_extension', 0) + 1
        return extensions


if __name__ == '__main__':
    # Test the module
    logging.basicConfig(level=logging.DEBUG)
    from git_watcher import GitWatcher

    # Mock configuration
    configs = {
        'test-repo': {
            'path': '/tmp/test-repo',
            'branch': 'main',
            'remote': 'origin'
        }
    }
    watcher = GitWatcher(configs)
    analyzer = DiffAnalyzer(watcher)

    # Simulate changed files
    changed_files = ['README.md', 'src/main.py', 'config.yaml']
    analysis = analyzer.analyze_changes('test-repo', changed_files)
    print("Analysis:", analysis)
    message, truncated = analyzer.format_message_for_telegram(analysis)
    print("Telegram message:", message)
    print("Truncated:", truncated)