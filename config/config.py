import threading
import yaml
import os

# Cached configuration with thread safety and validation
_config_cache = None
_config_last_modified = 0
_config_lock = threading.Lock()


def _load_config():
    """Load and cache the configuration file with thread safety and validation

    Returns:
        dict: Parsed configuration

    Raises:
        RuntimeError: If config file is missing or invalid
        ValueError: If config is malformed
    """
    global _config_cache, _config_last_modified

    try:
        mod_time = os.path.getmtime("config/config.yaml")
    except OSError as e:
        raise RuntimeError(f"Failed to access config file: {str(e)}")

    with _config_lock:
        if _config_cache is not None and mod_time <= _config_last_modified:
            return _config_cache

        try:
            with open("config/config.yaml", "r", encoding="utf-8") as file:
                config = yaml.safe_load(file)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config: {str(e)}")
        except OSError as e:
            raise RuntimeError(f"Failed to read config file: {str(e)}")

        if not isinstance(config, dict):
            raise ValueError("Config must be a dictionary")

        if "output" not in config:
            raise ValueError("Missing required config section: output")

        if "stacks" not in config:
            print(
                "Warning: no 'stacks' defined in config, files will not be classified. Only analyzers with tech_stacks set to 'All' will be applied."
            )
        if "analyzers" not in config:
            print(
                "Warning: no 'analyzers' defined in config, no analysis will be applied."
            )

        _config_cache = config
        _config_last_modified = mod_time
        return _config_cache


def load_output_config():
    config = _load_config()
    return config["output"]


def load_stacks_config():
    """Load stacks configuration from cached config"""
    config = _load_config()
    return config.get("stacks", [])


def load_analyzer_config():
    """Load analyzer configuration from cached config"""
    config = _load_config()
    return config.get("analyzers", [])
