#!/usr/bin/env python3
"""
Test what exception is raised when remote doesn't exist.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from git import Repo

repo_path = '/Users/zeng/project/orchestrator_v4'
repo = Repo(repo_path)

print(f"Repository remotes: {list(repo.remotes)}")
print(f"Remote names: {[r.name for r in repo.remotes]}")

try:
    remote_obj = repo.remotes['origin']
    print(f"Remote 'origin' found: {remote_obj}")
except Exception as e:
    print(f"Exception type: {type(e)}")
    print(f"Exception: {e}")
    import traceback
    traceback.print_exc()

# Also test if 'origin' in repo.remotes
print(f"\n'origin' in repo.remotes: {'origin' in repo.remotes}")
print(f"repo.remotes is: {repo.remotes}")
print(f"Type of repo.remotes: {type(repo.remotes)}")