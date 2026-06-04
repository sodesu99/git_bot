#!/usr/bin/env python3
"""
Simple test for Git watcher functionality.
"""

import os
import sys
import yaml

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_git_watcher():
    """Test GitWatcher with test configuration."""
    try:
        # Load test config
        with open('test_config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        print("✅ Configuration loaded")
        
        # Try to import GitWatcher
        from git_watcher import GitWatcher
        
        git_watcher = GitWatcher(config['repositories'])
        
        repos = git_watcher.list_repositories()
        print(f"✅ Loaded repositories: {repos}")
        
        # Test checking a repository
        for repo_name in repos:
            print(f"\n🔍 Testing repository: {repo_name}")
            try:
                has_changes, changed_files, error = git_watcher.check_repository(repo_name)
                
                if error:
                    print(f"   ❌ Error: {error}")
                else:
                    if has_changes:
                        print(f"   ✅ Changes detected: {len(changed_files)} file(s)")
                        for i, f in enumerate(changed_files[:3], 1):
                            print(f"      {i}. {f}")
                        if len(changed_files) > 3:
                            print(f"      ... and {len(changed_files) - 3} more")
                    else:
                        print("   ✅ No changes detected")
                        
            except Exception as e:
                print(f"   ❌ Failed to check repository: {e}")
        
        print("\n✅ Git watcher test completed")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_git_watcher()
    sys.exit(0 if success else 1)