#!/usr/bin/env python3
"""
Test DiffAnalyzer module with real Git repositories.
"""

import os
import sys
import logging
import yaml

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')

from git_watcher import GitWatcher
from diff_analyzer import DiffAnalyzer

def load_test_config():
    """Load test configuration."""
    config_path = 'test_config.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config

def test_basic_analysis():
    """Test basic analysis functionality."""
    print("🧪 Testing DiffAnalyzer basic functionality")
    print("="*60)
    
    config = load_test_config()
    watcher = GitWatcher(config['repositories'])
    analyzer = DiffAnalyzer(watcher)
    
    repos = watcher.list_repositories()
    print(f"Loaded repositories: {repos}")
    
    for repo_name in repos:
        print(f"\n{'='*60}")
        print(f"Analyzing repository: {repo_name}")
        print(f"{'='*60}")
        
        # Check for changes
        has_changes, changed_files, error = watcher.check_repository(repo_name)
        
        if error:
            print(f"❌ Error checking repository: {error}")
            continue
            
        if not has_changes:
            print("✅ No changes detected")
            
            # Test with empty file list
            empty_analysis = analyzer.analyze_changes(repo_name, [])
            print(f"Empty analysis: {empty_analysis['summary']}")
            
            telegram_msg, truncated = analyzer.format_message_for_telegram(empty_analysis)
            print(f"Telegram message (empty): {telegram_msg}")
            print(f"Truncated: {truncated}")
            
            continue
        
        print(f"✅ Changes detected: {len(changed_files)} file(s)")
        
        # Get file extensions analysis
        extensions = analyzer.get_file_extensions(changed_files)
        print(f"File extensions: {extensions}")
        
        # Perform detailed analysis
        print(f"\n🔍 Performing detailed analysis...")
        analysis = analyzer.analyze_changes(repo_name, changed_files)
        
        print(f"Analysis summary: {analysis['summary']}")
        print(f"Total files in analysis: {analysis['file_count']}")
        
        # Show file previews
        print(f"\n📄 File previews (showing first 3 files):")
        for i, file_info in enumerate(analysis['files'][:3], 1):
            print(f"  {i}. {file_info['path']}")
            preview = file_info['content_preview']
            line_count = file_info['line_count']
            truncated = file_info['truncated']
            
            # Display preview
            preview_lines = preview.split('\n')
            display_lines = preview_lines[:5]  # Show first 5 lines
            print(f"     Content ({line_count} lines, truncated={truncated}):")
            for line in display_lines:
                print(f"       {line}")
            if len(preview_lines) > 5:
                print(f"       ... (showing 5 of {len(preview_lines)} lines)")
        
        # Test Telegram message formatting
        print(f"\n💬 Testing Telegram message formatting...")
        telegram_msg, truncated = analyzer.format_message_for_telegram(analysis)
        
        msg_length = len(telegram_msg)
        print(f"Message length: {msg_length} characters")
        print(f"Truncated: {truncated}")
        
        # Show first 500 chars of message
        print(f"\nMessage preview (first 500 chars):")
        preview = telegram_msg[:500]
        if msg_length > 500:
            preview += "..."
        print(preview)
        
        # Test compact message
        print(f"\n📦 Testing compact message format:")
        compact_msg = analyzer.format_compact_message(analysis)
        print(f"Compact message: {compact_msg}")
        
        # Test with limited files (to avoid too much output)
        if len(changed_files) > 10:
            print(f"\n🧪 Testing with limited file set (first 5 files)...")
            limited_files = changed_files[:5]
            limited_analysis = analyzer.analyze_changes(repo_name, limited_files)
            limited_msg, limited_truncated = analyzer.format_message_for_telegram(limited_analysis)
            print(f"Limited analysis ({len(limited_files)} files):")
            print(f"  Message length: {len(limited_msg)} characters")
            print(f"  Truncated: {limited_truncated}")

def test_message_truncation():
    """Test message truncation logic."""
    print(f"\n{'='*60}")
    print("🧪 Testing message truncation logic")
    print(f"{'='*60}")
    
    config = load_test_config()
    watcher = GitWatcher(config['repositories'])
    analyzer = DiffAnalyzer(watcher)
    
    # Use orchestrator-v4 for testing (has many changes)
    repo_name = 'orchestrator-v4'
    
    # Check for changes
    has_changes, changed_files, error = watcher.check_repository(repo_name)
    
    if not has_changes or error:
        print(f"⚠️ No changes or error for {repo_name}, using mock data")
        # Create mock changed files with long content
        changed_files = ['test1.py', 'test2.py', 'test3.py', 'test4.py', 'test5.py']
    
    # Test with very small max length
    print(f"\nTesting with very small max length (500 chars)...")
    analysis = analyzer.analyze_changes(repo_name, changed_files[:3])  # Use first 3 files
    
    # Force small limit
    telegram_msg, truncated = analyzer.format_message_for_telegram(analysis, max_length=500)
    
    print(f"Message length: {len(telegram_msg)} characters")
    print(f"Truncated: {truncated}")
    print(f"Message preview (first 300 chars):")
    print(telegram_msg[:300] + "..." if len(telegram_msg) > 300 else telegram_msg)

def test_edge_cases():
    """Test edge cases."""
    print(f"\n{'='*60}")
    print("🧪 Testing edge cases")
    print(f"{'='*60}")
    
    config = load_test_config()
    watcher = GitWatcher(config['repositories'])
    analyzer = DiffAnalyzer(watcher)
    
    # Test with non-existent repo
    print("\n1. Testing with non-existent repository...")
    try:
        analysis = analyzer.analyze_changes('non-existent-repo', ['test.py'])
        print(f"Result: {analysis}")
    except Exception as e:
        print(f"Expected error: {e}")
    
    # Test with empty file list
    print("\n2. Testing with empty file list...")
    analysis = analyzer.analyze_changes('orchestrator-v4', [])
    print(f"Analysis: {analysis}")
    
    telegram_msg, truncated = analyzer.format_message_for_telegram(analysis)
    print(f"Telegram message: {telegram_msg}")
    print(f"Truncated: {truncated}")
    
    # Test compact message with no changes
    print("\n3. Testing compact message with no changes...")
    compact_msg = analyzer.format_compact_message(analysis)
    print(f"Compact message: {compact_msg}")
    
    # Test file extensions
    print("\n4. Testing file extensions analysis...")
    test_files = ['test.py', 'README.md', 'src/main.js', 'Dockerfile', '.env', 'docs/api.txt']
    extensions = analyzer.get_file_extensions(test_files)
    print(f"File extensions for test files: {extensions}")

def main():
    """Main test function."""
    try:
        test_basic_analysis()
        test_message_truncation()
        test_edge_cases()
        
        print(f"\n{'='*60}")
        print("✅ All tests completed successfully!")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())