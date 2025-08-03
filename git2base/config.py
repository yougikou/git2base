import sys
import threading
import yaml
import os
import logging.config

# Cached configuration with thread safety and validation
_config_cache = None
_config_last_modified = 0
_config_lock = threading.Lock()
_logger_config_loaded = False

# Logger names used throughout the project
LOGGER_GIT2BASE = "git2base"
LOGGER_NO_TECHSTACK = "no_techstack_identified"


def get_executable_dir():
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def get_default_config_paths():
    """Return default config and logger file paths."""
    base_dir = get_executable_dir()
    config_path = os.path.join(base_dir, "config", "config.yaml")
    logger_config_path = os.path.join(base_dir, "config", "logger.yaml")
    return config_path, logger_config_path


def _load_config():
    """Load and cache the configuration file with thread safety and validation

    Returns:
        dict: Parsed configuration

    Raises:
        RuntimeError: If config file is missing or invalid
        ValueError: If config is malformed
    """
    global _config_cache, _config_last_modified, _logger_config_loaded

    config_path, logger_config_path = get_default_config_paths()

    # Load logger config once if logger.yaml exists
    if not _logger_config_loaded:
        if os.path.exists(logger_config_path):
            with open(logger_config_path, "r", encoding="utf-8") as f:
                logging_config = yaml.safe_load(f)

            # Ensure all FileHandler paths have existing directories
            for handler in logging_config.get("handlers", {}).values():
                if handler.get("class") == "logging.FileHandler":
                    log_file = handler.get("filename")
                    if log_file:
                        log_dir = os.path.dirname(log_file)
                        if log_dir and not os.path.exists(log_dir):
                            os.makedirs(log_dir, exist_ok=True)

            # Apply logging configuration
            logging.config.dictConfig(logging_config)
        else:
            logging.basicConfig(level=logging.INFO)
        _logger_config_loaded = True

    try:
        mod_time = os.path.getmtime(config_path)
    except OSError as e:
        raise RuntimeError(f"Failed to access config file: {str(e)}")

    with _config_lock:
        if _config_cache is not None and mod_time <= _config_last_modified:
            return _config_cache

        try:
            with open(config_path, "r", encoding="utf-8") as file:
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
            logging.warning(
                "Warning: no 'stacks' defined in config, files will not be classified. Only analyzers with tech_stacks set to 'All' will be applied."
            )
        if "analyzers" not in config:
            logging.warning(
                "Warning: no 'analyzers' defined in config, no analysis will be applied."
            )

        _config_cache = config
        _config_last_modified = mod_time
        return _config_cache


def load_input_config():
    config = _load_config()
    return config.get("input", {"include": [], "exclude": []})


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


def get_logger(name: str) -> logging.Logger:
    _load_config()
    return logging.getLogger(name)
