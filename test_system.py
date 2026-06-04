#!/usr/bin/env python3
"""Quick test for System class."""

import sys
sys.path.insert(0, '.')

from unittest.mock import patch

def mock_call_ai(ai_input):
    """Mock LLM call for testing."""
    user_input = ai_input.get("user_input", "").lower()
    if "log" in user_input or "logs" in user_input:
        return {"action": "check_logs", "target": "service", "reason": "User requested log check"}
    elif "status" in user_input or "check" in user_input:
        return {"action": "git_status", "target": "current", "reason": "User requested status check"}
    else:
        return {"action": "check_repo", "target": "default", "reason": "Fallback"}

# Patch llm_engine.call_ai before importing System
with patch('llm_engine.call_ai', side_effect=mock_call_ai):
    from system import System

def test_system():
    print("Testing AI Router + Context System...")
    system = System()
    
    # Test config
    print("\n1. Config:")
    print(system.route("/config"))
    
    # Test file search (no files maybe)
    print("\n2. File search @system:")
    print(system.route("@system"))
    
    # Test AI decision (will use mock)
    print("\n3. AI decision (check logs):")
    print(system.route("check logs"))
    
    # Test direct command
    print("\n4. Direct command !pwd:")
    print(system.route("!pwd"))

    # Test explicit /cmd route
    print("\n5. /cmd !pwd:")
    print(system.route("/cmd !pwd"))

    # Test full-width exclamation route
    print("\n6. Full-width command ！pwd:")
    print(system.route("！pwd"))
    
    # Test special commands
    print("\n7. Special command !reset:")
    print(system.route("!reset"))
    
    print("\n8. Special command !clear_files:")
    print(system.route("!clear_files"))
    
    print("\nTest completed.")

if __name__ == "__main__":
    test_system()