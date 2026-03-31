"""
Configuration loading utilities for nodes.
Eliminates duplicate config loading logic.
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


# Default configurations for each node
# 模型从环境变量读取，默认使用 Kimi 的 moonshot-v1-8k
DEFAULT_MODEL = os.getenv("LLM_MODEL", "moonshot-v1-8k")

DEFAULT_CONFIGS: Dict[str, Dict[str, Any]] = {
    "risk_assessment": {
        "model": DEFAULT_MODEL,
        "temperature": 0.2,
        "max_tokens": 1500,
        "timeout": 30,
    },
    "intervention": {
        "model": DEFAULT_MODEL,
        "temperature": 0.3,
        "max_tokens": 2000,
        "timeout": 30,
    },
    "report_generation": {
        "model": DEFAULT_MODEL,
        "temperature": 0.3,
        "max_tokens": 2000,
        "timeout": 30,
    },
}


def load_node_config(node_name: str, default_config: Optional[dict] = None) -> Dict[str, Any]:
    """
    Load configuration for a node from JSON file or use defaults.

    Args:
        node_name: Name of the node (e.g., 'risk_assessment')
        default_config: Optional override for default config

    Returns:
        Merged configuration dict
    """
    # Start with built-in defaults
    config = DEFAULT_CONFIGS.get(node_name, {}).copy()

    # Override with provided defaults if any
    if default_config:
        config.update(default_config)

    # Try to load from config file
    config_path = Path("config") / f"{node_name}_cfg.json"

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                file_config = json.load(f)
                config.update(file_config)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[警告] 无法加载配置文件 {config_path}: {e}")

    # 根据模型调整 temperature (kimi-k2.5 只支持 temperature=1)
    model = config.get("model", "")
    if "kimi-k2.5" in model:
        config["temperature"] = 1
        print(f"[配置] 模型 {model} 只支持 temperature=1，已自动调整")

    return config


def get_prompt_template(node_name: str, template_name: str = "user_prompt") -> str:
    """
    Get a prompt template for a node.

    Args:
        node_name: Name of the node
        template_name: Name of the template (e.g., 'system_prompt', 'user_prompt')

    Returns:
        Template string or empty string if not found
    """
    config = load_node_config(node_name)
    return config.get(template_name, "")


def get_model_config(node_name: str) -> Dict[str, Any]:
    """
    Get model-specific configuration for a node.

    Args:
        node_name: Name of the node

    Returns:
        Dict with model, temperature, max_tokens, timeout
    """
    config = load_node_config(node_name)
    return {
        "model": config.get("model", DEFAULT_MODEL),
        "temperature": config.get("temperature", 0.3),
        "max_tokens": config.get("max_tokens", 1500),
        "timeout": config.get("timeout", 30),
    }
