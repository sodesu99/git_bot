"""
LLM configuration module for Git-Telegram bot.

Reuses the configuration reading approach from orchestrator_v4:
centralized JSON config + environment variable overrides.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

_CONFIG_CACHE: Optional[Dict[str, Any]] = None


def _default_config_path() -> Path:
    # repo_root/llm_config.py -> repo_root/llm.config.json
    return Path(__file__).resolve().parent / "llm.config.json"


def load_config() -> Dict[str, Any]:
    """Load configuration from JSON file, cache result."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    config_path = Path(os.getenv("LLM_CONFIG_PATH", str(_default_config_path())))
    if not config_path.exists():
        _CONFIG_CACHE = {}
        return _CONFIG_CACHE

    try:
        _CONFIG_CACHE = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Warning: Failed to load LLM config from {config_path}: {e}")
        _CONFIG_CACHE = {}

    return _CONFIG_CACHE


def get(path: str, default: Any = None) -> Any:
    """
    Read nested config value by dot path, e.g. llm.base_url
    
    Args:
        path: Dot‑separated path to config value
        default: Default value if path does not exist
    
    Returns:
        Config value or default
    """
    cfg = load_config()
    current: Any = cfg
    for key in path.split('.'):
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def get_llm_model() -> str:
    """
    Determine the LLM model to use.
    
    Priority:
    1. LLM_MODEL environment variable
    2. llm.active_profile → llm.profiles.<profile>.model
    3. llm.model
    4. Default "deepseek-chat"
    """
    env_model = os.getenv("LLM_MODEL")
    if env_model:
        return env_model

    profile = os.getenv("LLM_PROFILE") or get("llm.active_profile", "default")
    profile_model = get(f"llm.profiles.{profile}.model")
    if profile_model:
        return str(profile_model)

    model = get("llm.model")
    if model:
        return str(model)

    return "deepseek-chat"


def get_llm_base_url() -> str:
    """
    Determine the LLM API base URL.
    
    Priority:
    1. LLM_BASE_URL environment variable
    2. llm.base_url config
    3. Default "https://api.deepseek.com/v1"
    """
    env_url = os.getenv("LLM_BASE_URL")
    if env_url:
        return env_url.rstrip("/")

    url = get("llm.base_url")
    if url:
        return str(url).rstrip("/")

    return "https://api.deepseek.com/v1"


def get_llm_api_keys() -> list[str]:
    """
    Retrieve LLM API keys.
    
    Priority:
    1. LLM_API_KEYS environment variable (comma‑separated)
    2. LLM_API_KEY environment variable (single key, legacy)
    3. DEEPSEEK_API_KEY / OPENAI_API_KEY (legacy provider env vars)
    4. llm.api_keys config (list)
    5. llm.api_key config (single key)
    6. Empty list (will cause error later)
    """
    # 1. LLM_API_KEYS
    keys_env = os.getenv("LLM_API_KEYS")
    if keys_env:
        return [k.strip() for k in keys_env.split(",") if k.strip()]

    # 2. LLM_API_KEY
    single_key = os.getenv("LLM_API_KEY")
    if single_key and single_key.strip():
        return [single_key.strip()]

    # 3. provider-specific legacy env vars (for existing deployments)
    for legacy_name in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY"):
        legacy_key = os.getenv(legacy_name)
        if legacy_key and legacy_key.strip():
            return [legacy_key.strip()]

    # 4. llm.api_keys config
    config_keys = get("llm.api_keys")
    if isinstance(config_keys, list):
        return [str(k).strip() for k in config_keys if k]

    # 5. llm.api_key config
    config_key = get("llm.api_key")
    if config_key:
        return [str(config_key).strip()]

    return []


def get_llm_timeout() -> int:
    """Get request timeout in seconds."""
    timeout = os.getenv("LLM_TIMEOUT")
    if timeout and timeout.isdigit():
        return int(timeout)
    return get("llm.request_timeout", 120)