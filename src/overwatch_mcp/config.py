"""Configuration loader with YAML parsing and environment variable substitution."""

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from overwatch_mcp.models.config import Config


class ConfigError(Exception):
    """Configuration loading or validation error."""
    pass


def substitute_env_vars(data: Any) -> Any:
    """
    Recursively substitute ${VAR} patterns with environment variables.

    Raises ConfigError if a referenced environment variable is not set.
    """
    if isinstance(data, dict):
        return {key: substitute_env_vars(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [substitute_env_vars(item) for item in data]
    elif isinstance(data, str):
        # Find all ${VAR} patterns
        pattern = r'\$\{([^}]+)\}'
        matches = re.findall(pattern, data)

        result = data
        for var_name in matches:
            env_value = os.environ.get(var_name)
            if env_value is None:
                raise ConfigError(
                    f"Environment variable '{var_name}' is required but not set"
                )
            result = result.replace(f"${{{var_name}}}", env_value)

        return result
    else:
        return data


def load_config(config_path: str | Path) -> Config:
    """
    Load and validate configuration from YAML file.

    Args:
        config_path: Path to config.yaml file

    Returns:
        Validated Config object

    Raises:
        ConfigError: If file not found, YAML invalid, env vars missing, or validation fails
    """
    config_path = Path(config_path)

    # Check file exists
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    # Load YAML
    try:
        with open(config_path) as f:
            raw_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in config file: {e}")

    if raw_data is None:
        raise ConfigError("Config file is empty")

    # Substitute environment variables
    try:
        processed_data = substitute_env_vars(raw_data)
    except ConfigError:
        raise  # Re-raise ConfigError as-is

    # Validate with Pydantic
    try:
        config = Config(**processed_data)
    except ValidationError as e:
        raise ConfigError(f"Config validation failed: {e}")

    return config


def load_config_from_dict(data: dict[str, Any]) -> Config:
    """
    Load and validate configuration from dictionary (for testing).

    Args:
        data: Configuration dictionary

    Returns:
        Validated Config object

    Raises:
        ConfigError: If validation fails
    """
    try:
        config = Config(**data)
    except ValidationError as e:
        raise ConfigError(f"Config validation failed: {e}")

    return config
