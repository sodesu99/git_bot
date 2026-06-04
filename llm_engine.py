#!/usr/bin/env python3
"""
LLM Engine for AI Router + Context System.

Supports multiple LLM providers via OpenAI‑compatible API.
Configuration via llm.config.json and environment variables.
No mock fallback – fails cleanly if configuration is missing.
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from enum import Enum

try:
    from openai import OpenAI
    from openai.types.chat import ChatCompletionMessageParam
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

import llm_config

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    DEEPSEEK = "deepseek"


class LLMEngine:
    """
    LLM engine for decision making.
    """
    
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None, 
                 api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize LLM engine.
        
        Args:
            provider: LLM provider ("openai", "deepseek"). If None, inferred from base_url.
            model: Model name (overrides config)
            api_key: API key (overrides config)
            base_url: Custom API base URL (overrides config)
        """
        # Determine provider from base_url or config
        if provider is None:
            provider = self._infer_provider(base_url)
        self.provider = LLMProvider(provider.lower())
        
        # Load configuration
        self.model = model or llm_config.get_llm_model()
        self.base_url = base_url or llm_config.get_llm_base_url()
        
        # Get API keys (list)
        self.api_keys = llm_config.get_llm_api_keys()
        if api_key is not None:
            self.api_keys = [api_key.strip()]
        
        if not self.api_keys:
            raise RuntimeError(
                "No LLM API keys configured. "
                "Set LLM_API_KEYS environment variable or configure in llm.config.json."
            )
        
        self.client = None
        self._setup_client()
    
    @staticmethod
    def _infer_provider(base_url: Optional[str]) -> str:
        """Infer provider from base URL."""
        if base_url:
            if "openai" in base_url:
                return "openai"
            elif "deepseek" in base_url:
                return "deepseek"
        # Default to deepseek (most common for this project)
        return "deepseek"
        
    def _setup_client(self):
        """Setup the OpenAI‑compatible API client."""
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "OpenAI package not installed. Install with: pip install openai"
            )
        
        # Use first API key for client initialization (pooling not implemented here)
        api_key = self.api_keys[0]
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=self.base_url
        )
    
    def generate_decision(self, ai_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a decision based on AI input.
        
        Args:
            ai_input: Structured input as defined in System._build_ai_input()
            
        Returns:
            Decision dictionary with keys: action, target, reason
        """
        # Prepare prompt for LLM
        prompt = self._build_prompt(ai_input)
        
        # Call LLM (exceptions will propagate)
        response = self._call_llm(prompt)
        decision = self._parse_response(response)
        return decision
    
    def _build_prompt(self, ai_input: Dict[str, Any]) -> str:
        """Build a prompt for the LLM."""
        # Format the input into a readable prompt
        user_input = ai_input.get("user_input", "")
        short_context = ai_input.get("short_context", [])
        available_actions = ai_input.get("available_actions", [])
        file_mappings = ai_input.get("file_mappings", {})
        
        prompt_lines = [
            "You are an AI assistant controlling a system via a restricted interface.",
            "Your task is to decide which action to take based on the user's request.",
            "",
            "=== CONTEXT ==="
        ]
        
        # Add short context
        for entry in short_context[-5:]:  # Last 5 entries
            role = "USER" if entry["role"] == "user" else "SYSTEM"
            prompt_lines.append(f"{role}: {entry['text']}")
        
        prompt_lines.extend([
            "",
            "=== CURRENT REQUEST ===",
            f"USER: {user_input}",
            "",
            "=== AVAILABLE ACTIONS ==="
        ])
        
        for action in available_actions:
            prompt_lines.append(f"- {action}")
        
        if file_mappings:
            prompt_lines.extend([
                "",
                "=== FILE MAPPINGS ==="
            ])
            for file_id, path in file_mappings.items():
                prompt_lines.append(f"{file_id}: {path}")
        
        prompt_lines.extend([
            "",
            "=== INSTRUCTIONS ===",
            "Choose the most appropriate action from the available actions list.",
            "If the user wants to execute a command, use 'execute_safe' action.",
            "If the user wants to view a file, use 'view_file' action.",
            "If the user mentions git operations, choose appropriate git action.",
            "",
            "Respond with a JSON object containing exactly these three fields:",
            "1. 'action': the action name from available actions",
            "2. 'target': target of the action (e.g., file path, command string, repository name)",
            "3. 'reason': brief explanation of why this action was chosen",
            "",
            "Example response:",
            '{"action": "git_status", "target": "current", "reason": "User asked for git status"}',
            "",
            "Now respond with JSON:"
        ])
        
        return "\n".join(prompt_lines)
    
    def _call_llm(self, prompt: str) -> str:
        """Call the LLM API and return the response text."""
        if self.client is None:
            raise RuntimeError("LLM client not initialized")
        
        # Prepare messages
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": "You are a helpful assistant that responds with JSON."},
            {"role": "user", "content": prompt}
        ]
        
        # For OpenAI provider, we can use response_format parameter
        extra_params = {}
        if self.provider == LLMProvider.OPENAI:
            extra_params["response_format"] = {"type": "json_object"}
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.1,
            max_tokens=500,
            **extra_params
        )

        response_text = response.choices[0].message.content.strip()

        # Optional raw trace logging for debugging (JSONL)
        # Enabled by default; disable with LLM_TRACE_ENABLED=false
        trace_enabled = os.getenv("LLM_TRACE_ENABLED", "true").lower() not in {"0", "false", "no"}
        if trace_enabled:
            default_trace_path = Path(__file__).resolve().parent / "llm_raw.log"
            trace_path = Path(os.getenv("LLM_TRACE_PATH", str(default_trace_path)))
            try:
                trace_record = {
                    "ts": datetime.now().isoformat(),
                    "model": self.model,
                    "base_url": self.base_url,
                    "request": {
                        "messages": messages,
                        "temperature": 0.1,
                        "max_tokens": 500,
                        "extra_params": extra_params,
                    },
                    "response": response_text,
                }
                with trace_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(trace_record, ensure_ascii=False) + "\n")
            except Exception as e:
                logger.warning(f"Failed to write LLM trace log: {e}")
        
        return response_text
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse LLM response into decision dictionary."""
        try:
            # Try to extract JSON from response (might have extra text)
            text = response_text.strip()
            # Find first { and last }
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = text[start:end]
                data = json.loads(json_str)
            else:
                data = json.loads(text)
            
            # Ensure required fields
            if not all(key in data for key in ["action", "target", "reason"]):
                raise ValueError("Missing required fields in LLM response")
            
            return {
                "action": str(data["action"]),
                "target": str(data["target"]),
                "reason": str(data["reason"])
            }
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse LLM response: {e}\nResponse: {response_text}")
            # Return a safe default
            return {
                "action": "check_repo",
                "target": "default",
                "reason": "Fallback due to parsing error"
            }
    



# Singleton instance for default usage
_default_engine = None

def get_default_engine() -> LLMEngine:
    """Get or create default LLM engine instance using centralized config."""
    global _default_engine
    if _default_engine is None:
        # Configuration is read via llm_config module
        # No mock fallback – will raise if configuration is missing
        _default_engine = LLMEngine()
        logger.info(f"Initialized default LLM engine with model: {_default_engine.model}, base_url: {_default_engine.base_url}")
    
    return _default_engine

def call_ai(ai_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to call AI with default engine.
    
    This maintains compatibility with the original System._call_ai interface.
    """
    engine = get_default_engine()
    return engine.generate_decision(ai_input)