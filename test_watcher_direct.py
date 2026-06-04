#!/usr/bin/env python3
"""
Direct test of GitWatcher with local changes detection.
"""

import os
import sys
import logging

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging to see debug messages
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')

# Import after path is set
from git_watcher import GitWatcher

def main():
    # Test configuration
    configs = {
        'orchestrator-v4': {
            'path': '/Users/zeng/project/orchestrator_v4',
            'branch': 'main',
            'remote': 'origin'  # Doesn't exist, should fall back to local
        },
        'rag-system': {
            'path': '/Users/zeng/project/rag',
            'branch': 'main',
            'remote': 'origin'
        }
    }
    
    print("Creating GitWatcher instance...")
    watcher = GitWatcher(configs)
    
    print(f"\nLoaded repositories: {watcher.list_repositories()}")
    
    for repo_name in watcher.list_repositories():
        print(f"\n{'='*60}")
        print(f"Testing repository: {repo_name}")
        print(f"{'='*60}")
        
        # Get repository info
        info = watcher.get_repository_info(repo_name)
        if info:
            print(f"Path: {info['path']}")
            print(f"Active branch: {info['active_branch']}")
            print(f"Head commit: {info['head_commit']}")
            print(f"Is dirty: {info['is_dirty']}")
        
        # Check for changes
        print("\nChecking for changes...")
        has_changes, changed_files, error = watcher.check_repository(repo_name)
        
        if error:
            print(f"❌ Error: {error}")
        else:
            if has_changes:
                print(f"✅ Changes detected: {len(changed_files)} file(s)")
                # Show first 5 files
                for i, f in enumerate(changed_files[:5], 1):
                    print(f"   {i}. {f}")
                if len(changed_files) > 5:
                    print(f"   ... and {len(changed_files) - 5} more")
                
                # Test reading file content
                if changed_files:
                    test_file = changed_files[0]
                    print(f"\nTesting content read for: {test_file}")
                    content = watcher.read_file_content(repo_name, test_file, max_lines=5)
                    if content:
                        print(f"Content (first 5 lines):\n{content}")
                    else:
                        print("Failed to read content")
            else:
                print("✅ No changes detected")
    
    print(f"\n{'='*60}")
    print("Test completed")

if __name__ == '__main__':
    main()