#!/usr/bin/env python3
"""
Git watcher module for monitoring repository changes.
Supports multiple repositories and periodic checking.
"""

import os
import logging
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
from git import Repo, GitCommandError, InvalidGitRepositoryError
from datetime import datetime

CUSTOM_REPOS_FILE = "custom_repos.yaml"

logger = logging.getLogger(__name__)


class GitWatcher:
    """Watches Git repositories for changes."""

    def __init__(self, repo_configs: Dict[str, Dict[str, str]]):
        """
        Initialize with repository configurations.

        Args:
            repo_configs: Dict mapping repo name to config dict
                {
                    'path': '/path/to/repo',
                    'branch': 'main',
                    'remote': 'origin'
                }
        """
        self.repo_configs = repo_configs
        self._original_repo_configs = dict(repo_configs)  # snapshot for persistence tracking
        self.repos: Dict[str, Repo] = {}
        self._known_remote_heads: Dict[str, str] = {}  # repo_name -> last known remote HEAD SHA
        self._merge_custom_repos()
        self._load_repositories()

    def _merge_custom_repos(self):
        """Merge repos from custom_repos.yaml into repo_configs (in-memory only)."""
        import yaml
        custom_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CUSTOM_REPOS_FILE)
        if not os.path.exists(custom_path):
            return
        try:
            with open(custom_path, 'r') as f:
                custom = yaml.safe_load(f) or {}
            for name, cfg in custom.items():
                if name not in self.repo_configs:
                    self.repo_configs[name] = cfg
                    logger.info(f"Loaded custom repository '{name}' from {CUSTOM_REPOS_FILE}")
                else:
                    logger.debug(f"Custom repo '{name}' skipped (already in config)")
        except Exception as e:
            logger.error(f"Failed to load {CUSTOM_REPOS_FILE}: {e}")

    def _persist_custom_repos(self):
        """Write current dynamic repositories to custom_repos.yaml."""
        import yaml
        # Only persist repos that are NOT in the original config.yaml
        custom_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CUSTOM_REPOS_FILE)
        try:
            with open(custom_path, 'w') as f:
                yaml.dump(self._custom_repos(), f, default_flow_style=False, allow_unicode=True)
            logger.info(f"Persisted {len(self._custom_repos())} custom repos to {CUSTOM_REPOS_FILE}")
        except Exception as e:
            logger.error(f"Failed to persist {CUSTOM_REPOS_FILE}: {e}")

    def _custom_repos(self) -> Dict[str, Dict[str, str]]:
        """Return only repos that were added dynamically (not in original config)."""
        if not hasattr(self, '_original_repo_configs'):
            return {}
        result = {}
        for name, cfg in self.repo_configs.items():
            if name not in self._original_repo_configs:
                result[name] = cfg
        return result

    def _load_repositories(self):
        """Load GitPython Repo objects for each configured repository."""
        for name, config in self.repo_configs.items():
            path = config.get('path')
            if not path:
                logger.warning(f"Repository '{name}' missing path, skipping")
                continue
            if not os.path.exists(path):
                logger.warning(f"Repository path '{path}' does not exist, skipping")
                continue
            try:
                repo = Repo(path)
                self.repos[name] = repo
                logger.info(f"Loaded repository '{name}' from {path}")
            except InvalidGitRepositoryError:
                logger.error(f"Path '{path}' is not a valid Git repository")
            except Exception as e:
                logger.error(f"Failed to load repository '{name}': {e}")

    def lightweight_check(self, repo_name: str) -> Tuple[bool, Optional[str]]:
        """
        Lightweight remote check using git ls-remote instead of full git fetch.
        Only checks if the remote HEAD SHA has changed since last check.
        Returns (has_new_remote_commits, error_message).
        """
        if repo_name not in self.repos:
            return False, f"Repository '{repo_name}' not found"

        repo = self.repos[repo_name]
        config = self.repo_configs[repo_name]
        remote = config.get('remote', 'origin')

        # No remote → skip (local-only repos need the full check)
        remote_exists = any(r.name == remote for r in repo.remotes)
        if not remote_exists:
            return False, None

        try:
            # git ls-remote is a single lightweight HTTP request (~bytes)
            output = repo.git.ls_remote(remote, 'HEAD').strip()
            if not output:
                return False, None

            # Parse: "<sha>\\tHEAD"
            remote_sha = output.split('\t')[0].strip()
            if not remote_sha:
                return False, None

            known = self._known_remote_heads.get(repo_name)
            if known and known == remote_sha:
                return False, None  # unchanged, skip full fetch

            # SHA is new or this is the first check → record and flag as changed
            self._known_remote_heads[repo_name] = remote_sha
            return True, None

        except Exception as e:
            logger.debug(f"lightweight_check failed for '{repo_name}': {e}")
            return False, None  # non-fatal: fall through to full check

    def check_repository(self, repo_name: str) -> Tuple[bool, List[str], Optional[str]]:
        """
        Check a single repository for changes.

        Args:
            repo_name: Name of the repository as configured

        Returns:
            Tuple of (has_changes, changed_files, error_message)
        """
        if repo_name not in self.repos:
            return False, [], f"Repository '{repo_name}' not found"

        repo = self.repos[repo_name]
        config = self.repo_configs[repo_name]
        branch = config.get('branch', 'main')
        remote = config.get('remote', 'origin')

        try:
            # Check if remote exists
            remote_exists = False
            for r in repo.remotes:
                if r.name == remote:
                    remote_exists = True
                    break
            
            if not remote_exists:
                logger.info(f"Remote '{remote}' not found for '{repo_name}', checking local changes")
                return self._check_local_changes(repo, repo_name)
            
            # Remote exists, try to fetch and diff
            logger.debug(f"Remote '{remote}' exists, fetching updates for '{repo_name}'")
            remote_obj = repo.remotes[remote]
            remote_obj.fetch()

            # Get diff between HEAD and remote/branch
            remote_ref = f"{remote}/{branch}"
            if remote_ref not in repo.references:
                logger.warning(f"Remote branch '{remote_ref}' not found, checking local changes instead")
                return self._check_local_changes(repo, repo_name)

            # Get list of changed files
            diff = repo.git.diff('HEAD', remote_ref, name_only=True)
            files = [f.strip() for f in diff.splitlines() if f.strip()]

            if files:
                logger.info(f"Repository '{repo_name}' has {len(files)} changed files (remote diff)")
                return True, files, None
            else:
                logger.debug(f"Repository '{repo_name}' has no changes (remote diff)")
                return False, [], None

        except GitCommandError as e:
            error_msg = f"Git command failed for '{repo_name}': {e}"
            logger.error(error_msg)
            return False, [], error_msg
        except Exception as e:
            error_msg = f"Unexpected error checking '{repo_name}': {e}"
            logger.error(error_msg)
            return False, [], error_msg

    def _check_local_changes(self, repo: Repo, repo_name: str) -> Tuple[bool, List[str], Optional[str]]:
        """
        Check for local uncommitted changes (staged or unstaged).

        Args:
            repo: GitPython Repo object
            repo_name: Name of the repository for logging

        Returns:
            Tuple of (has_changes, changed_files, error_message)
        """
        try:
            # Use git status --porcelain for machine-readable output
            # Format: XY filename (X=staged, Y=unstaged)
            porcelain_output = repo.git.status(porcelain=True)
            files = []
            
            for line in porcelain_output.splitlines():
                line = line.strip()
                if not line:
                    continue
                    
                # Parse porcelain format: first 2 chars are status codes, then space, then filename
                # For renames: "R  oldfile -> newfile"
                if line.startswith('R  '):
                    # Renamed file, extract new filename
                    # Format: "R  oldfile -> newfile"
                    parts = line[3:].split(' -> ')
                    if len(parts) == 2:
                        filename = parts[1].strip()
                        # Skip directories (shouldn't be directories for renamed files, but check)
                        if not filename.endswith('/'):
                            files.append(filename)
                elif len(line) > 3 and line[2] == ' ':
                    # Normal case: status + space + filename
                    filename = line[3:].strip()
                    # Skip directories (git status shows directories with trailing slash)
                    if filename.endswith('/'):
                        continue
                    # Handle possible quotes (remove surrounding quotes if present)
                    if filename.startswith('"') and filename.endswith('"'):
                        filename = filename[1:-1]
                    files.append(filename)
            
            # Remove duplicates while preserving order
            seen = set()
            unique_files = []
            for f in files:
                if f not in seen:
                    seen.add(f)
                    unique_files.append(f)
            
            if unique_files:
                logger.info(f"Repository '{repo_name}' has {len(unique_files)} locally changed files")
                return True, unique_files, None
            else:
                logger.debug(f"Repository '{repo_name}' has no local changes")
                return False, [], None
                
        except GitCommandError as e:
            error_msg = f"Failed to check local changes for '{repo_name}': {e}"
            logger.error(error_msg)
            return False, [], error_msg
        except Exception as e:
            error_msg = f"Unexpected error checking local changes for '{repo_name}': {e}"
            logger.error(error_msg)
            return False, [], error_msg

    def get_repository_info(self, repo_name: str) -> Optional[Dict[str, str]]:
        """Get information about a repository."""
        if repo_name not in self.repos:
            return None

        repo = self.repos[repo_name]
        try:
            active_branch = repo.active_branch.name
        except:
            active_branch = "detached"

        try:
            head_commit = repo.head.commit.hexsha[:8]
        except (ValueError, Exception):
            head_commit = "(no commits)"

        try:
            is_dirty = repo.is_dirty()
        except Exception:
            is_dirty = False

        return {
            'path': repo.working_dir,
            'active_branch': active_branch,
            'head_commit': head_commit,
            'is_dirty': is_dirty,
        }

    def list_repositories(self) -> List[str]:
        """Return list of available repository names."""
        return list(self.repos.keys())
    
    def add_repository(self, repo_name: str, path: str, branch: str = "main", remote: str = "origin") -> Tuple[bool, str]:
        """
        Add a repository dynamically (persisted to custom_repos.yaml).
        
        Args:
            repo_name: Name for the repository
            path: Path to the repository
            branch: Branch to monitor (default: "main")
            remote: Remote name (default: "origin")
            
        Returns:
            Tuple of (success, message)
        """
        if repo_name in self.repo_configs:
            return False, f"Repository '{repo_name}' already exists"
        
        if not os.path.exists(path):
            return False, f"Path '{path}' does not exist"
        
        try:
            repo = Repo(path)
            self.repos[repo_name] = repo
            self.repo_configs[repo_name] = {
                'path': path,
                'branch': branch,
                'remote': remote
            }
            self._persist_custom_repos()
            logger.info(f"Added repository '{repo_name}' from {path}")
            return True, f"Repository '{repo_name}' added successfully"
        except InvalidGitRepositoryError:
            return False, f"Path '{path}' is not a valid Git repository"
        except Exception as e:
            logger.error(f"Failed to add repository '{repo_name}': {e}")
            return False, f"Failed to add repository: {str(e)}"

    def remove_repository(self, repo_name: str) -> Tuple[bool, str]:
        """
        Remove a repository dynamically.

        Args:
            repo_name: Name of the repository to remove

        Returns:
            Tuple of (success, message)
        """
        if repo_name not in self.repo_configs:
            return False, f"Repository '{repo_name}' not found"

        # Remove from runtime dicts
        self.repo_configs.pop(repo_name, None)
        self.repos.pop(repo_name, None)
        self._known_remote_heads.pop(repo_name, None)

        # Only persist if it was a custom repo (config.yaml repos are read-only)
        if repo_name not in self._original_repo_configs:
            self._persist_custom_repos()
            logger.info(f"Removed custom repository '{repo_name}'")
        else:
            logger.info(f"Removed repository '{repo_name}' from runtime (defined in config.yaml)")

        return True, f"Repository '{repo_name}' removed"

    def read_file_content(self, repo_name: str, file_path: str, max_lines: int = 100) -> Optional[str]:
        """
        Read content of a file from repository.

        Args:
            repo_name: Repository name
            file_path: Path relative to repository root
            max_lines: Maximum number of lines to read

        Returns:
            File content as string, or None if error
        """
        if repo_name not in self.repos:
            return None

        repo = self.repos[repo_name]
        full_path = os.path.join(repo.working_dir, file_path)

        if not os.path.exists(full_path):
            return None
        
        # Skip directories
        if os.path.isdir(full_path):
            return None

        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        lines.append(f"... (truncated after {max_lines} lines)")
                        break
                    lines.append(line.rstrip('\n'))
                return '\n'.join(lines)
        except Exception as e:
            logger.error(f"Failed to read file '{file_path}': {e}")
            return None

    def get_multiple_files_content(self, repo_name: str, file_paths: List[str]) -> Dict[str, Optional[str]]:
        """Read content of multiple files."""
        result = {}
        for file_path in file_paths:
            result[file_path] = self.read_file_content(repo_name, file_path)
        return result

    def get_recent_commits(
        self,
        repo_name: str,
        limit: int = 5,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Get recent commits for a repository."""
        if repo_name not in self.repos:
            return [], f"Repository '{repo_name}' not found"

        repo = self.repos[repo_name]
        try:
            # Check if repo has any commits first
            try:
                repo.head.commit
            except (ValueError, Exception):
                return [], None  # Empty repo, no commits

            safe_limit = max(1, min(limit, 50))
            commits = list(repo.iter_commits(max_count=safe_limit))
            result: List[Dict[str, Any]] = []
            for c in commits:
                files = list(c.stats.files.keys())
                result.append({
                    'hexsha': c.hexsha,
                    'short_sha': c.hexsha[:8],
                    'author': str(c.author),
                    'date': datetime.fromtimestamp(c.committed_date).strftime('%Y-%m-%d %H:%M:%S'),
                    'message': c.message.strip(),
                    'files': files,
                })
            return result, None
        except Exception as e:
            error_msg = f"Failed to read commits for '{repo_name}': {e}"
            logger.error(error_msg)
            return [], error_msg

    def find_file_in_repo(
        self,
        repo_name: str,
        file_name: str,
        max_results: int = 50,
    ) -> Tuple[List[str], Optional[str]]:
        """Find files in the repository matching the given name or relative path.

        Searches the actual filesystem of the repo (not commit history).
        The file_name can be a filename, a partial relative path, or a full relative path.

        Args:
            repo_name: Repository name
            file_name: File name or relative path to search for
            max_results: Maximum number of matches to return (default: 50)

        Returns:
            (list_of_relative_paths, error_message)
        """
        if repo_name not in self.repos:
            return [], f"Repository '{repo_name}' not found"

        repo = self.repos[repo_name]
        target = file_name.strip()
        if not target:
            return [], "fileName cannot be empty"

        try:
            repo_root = Path(repo.working_dir)
            target_lower = target.lower()

            matches: List[str] = []
            for f in repo_root.rglob("*"):
                if not f.is_file():
                    continue
                # Skip .git directory
                if ".git" in f.relative_to(repo_root).parts:
                    continue

                rel_path = f.relative_to(repo_root)
                rel_str = str(rel_path)

                # Match: full relative path, ends with target, or filename matches
                if (rel_str.lower() == target_lower
                        or rel_str.lower().endswith(f"/{target_lower}")
                        or rel_path.name.lower() == target_lower):
                    matches.append(str(rel_path))
                    if len(matches) >= max_results:
                        break

            if not matches:
                return [], f"No file matched '{file_name}' in repository"

            matches.sort()
            return matches, None
        except Exception as e:
            error_msg = f"Failed to search files in '{repo_name}': {e}"
            logger.error(error_msg)
            return [], error_msg


if __name__ == '__main__':
    # Test the module
    logging.basicConfig(level=logging.DEBUG)
    configs = {
        'test-repo': {
            'path': '/tmp/test-repo',
            'branch': 'main',
            'remote': 'origin'
        }
    }
    watcher = GitWatcher(configs)
    print(f"Loaded repos: {watcher.list_repositories()}")
    if watcher.list_repositories():
        has_changes, files, error = watcher.check_repository('test-repo')
        print(f"Has changes: {has_changes}, Files: {files}, Error: {error}")