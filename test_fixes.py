#!/usr/bin/env python3
"""
Test fixes for directory filtering and extension counting.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from git_watcher import GitWatcher
from diff_analyzer import DiffAnalyzer

def test_directory_filtering():
    """Test that directories are filtered from changed files."""
    print("🧪 Testing directory filtering")
    print("="*60)
    
    configs = {
        'test-repo': {
            'path': '/Users/zeng/project/orchestrator_v4',
            'branch': 'main',
            'remote': 'origin'
        }
    }
    
    watcher = GitWatcher(configs)
    has_changes, changed_files, error = watcher.check_repository('test-repo')
    
    if error:
        print(f"❌ Error: {error}")
        return
    
    print(f"Total changed files: {len(changed_files)}")
    
    # Check for directories in the list
    directories = [f for f in changed_files if f.endswith('/')]
    print(f"Directories in list: {len(directories)}")
    if directories:
        print(f"Directories found (should be 0): {directories[:5]}")
    
    # Test reading directory content (should return None)
    for dir_path in directories[:3]:
        content = watcher.read_file_content('test-repo', dir_path)
        print(f"Reading directory '{dir_path}': {content}")
        assert content is None, f"Directory '{dir_path}' should return None"
    
    print("✅ Directory filtering test passed")

def test_extension_counting():
    """Test improved extension counting."""
    print(f"\n{'='*60}")
    print("🧪 Testing extension counting")
    print("="*60)
    
    analyzer = DiffAnalyzer(None)  # Pass None since we don't need GitWatcher for this test
    
    # Test cases
    test_files = [
        'test.py',
        'README.md',
        'src/main.js',
        'Dockerfile',
        '.env',
        'docs/api.txt',
        'backup.txt.backup',
        'temp.py.bak',
        'newfile.new',
        'config.yaml',
        'path/to/file.with.dots.tar.gz',
        '"quoted/file.md"',
        'directory/',  # Should be filtered
        'tmp_pytest/',  # Should be filtered
    ]
    
    extensions = analyzer.get_file_extensions(test_files)
    print(f"Extensions counted: {extensions}")
    
    # Verify expectations
    assert extensions.get('py', 0) == 1, "Should count .py files"
    assert extensions.get('md', 0) == 2, "Should count .md files (README.md and quoted/file.md)"
    assert extensions.get('js', 0) == 1, "Should count .js files"
    assert extensions.get('txt', 0) == 1, "Should count .txt files"
    assert extensions.get('yaml', 0) == 1, "Should count .yaml files"
    assert extensions.get('backup', 0) == 3, "Should count backup files (.backup, .bak, .new)"
    assert extensions.get('no_extension', 0) == 1, "Should count files without extension (Dockerfile only, .env has extension 'env')"
    assert extensions.get('env', 0) == 1, "Should count .env files"
    assert 'tmp_pytest/' not in extensions, "Should not count directory as extension"
    
    print("✅ Extension counting test passed")

def test_actual_repository():
    """Test with actual repository data."""
    print(f"\n{'='*60}")
    print("🧪 Testing with actual repository")
    print("="*60)
    
    configs = {
        'test-repo': {
            'path': '/Users/zeng/project/orchestrator_v4',
            'branch': 'main',
            'remote': 'origin'
        }
    }
    
    watcher = GitWatcher(configs)
    analyzer = DiffAnalyzer(watcher)
    
    has_changes, changed_files, error = watcher.check_repository('test-repo')
    
    if error:
        print(f"❌ Error: {error}")
        return
    
    # Get extensions
    extensions = analyzer.get_file_extensions(changed_files)
    print(f"Actual repository extensions: {extensions}")
    
    # Check that no directories are in extensions
    for ext in extensions.keys():
        assert '/' not in ext, f"Extension '{ext}' contains slash (likely a directory)"
    
    # Check that backup extensions are grouped
    backup_count = extensions.get('backup', 0)
    print(f"Backup files: {backup_count}")
    
    print("✅ Actual repository test passed")

def main():
    try:
        test_directory_filtering()
        test_extension_counting()
        test_actual_repository()
        
        print(f"\n{'='*60}")
        print("✅ All fixes tests passed!")
        print(f"{'='*60}")
        return 0
    except AssertionError as e:
        print(f"\n❌ Assertion failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())