"""Shared pytest fixtures for all tests."""

import pytest
from pathlib import Path


@pytest.fixture
def sample_config_dict() -> dict:
    """Sample valid configuration dictionary."""
    return {
        "server": {
            "name": "overwatch-mcp-server",
            "version": "1.0.0",
            "log_level": "info"
        },
        "datasources": {
            "graylog": {
                "enabled": True,
                "url": "https://graylog.internal:9000/api",
                "token": "test-token-123",
                "timeout_seconds": 30,
                "max_time_range_hours": 24,
                "default_time_range_hours": 1,
                "max_results": 1000,
                "default_results": 100
            },
            "prometheus": {
                "enabled": True,
                "url": "http://prometheus.internal:9090",
                "timeout_seconds": 30,
                "max_range_hours": 168,
                "max_step_seconds": 3600,
                "max_series": 10000,
                "max_metric_results": 500
            },
            "influxdb": {
                "enabled": True,
                "url": "https://influxdb.internal:8086",
                "token": "influx-token-456",
                "org": "my-org",
                "timeout_seconds": 60,
                "allowed_buckets": ["telegraf", "app_metrics", "system_metrics"],
                "max_time_range_hours": 168
            }
        },
        "cache": {
            "enabled": True,
            "default_ttl_seconds": 60,
            "ttl_overrides": {
                "prometheus_metrics": 300,
                "graylog_fields": 300
            }
        }
    }


@pytest.fixture
def minimal_config_dict() -> dict:
    """Minimal valid configuration with only required fields."""
    return {
        "server": {
            "name": "test-server",
            "version": "1.0.0",
            "log_level": "info"
        },
        "datasources": {
            "graylog": {
                "enabled": True,
                "url": "https://graylog.test:9000/api",
                "token": "test-token"
            }
        }
    }


@pytest.fixture
def tmp_config_file(tmp_path: Path, sample_config_dict: dict) -> Path:
    """Create a temporary config file."""
    import yaml

    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(sample_config_dict, f)

    return config_file
