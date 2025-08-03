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


def _make_dir(path: str):
    path_dir = os.path.dirname(path)
    if path_dir and not os.path.exists(path_dir):
        os.makedirs(path_dir, exist_ok=True)

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
        if not os.path.exists(logger_config_path):
            _make_dir(logger_config_path)
            try:
                with open(logger_config_path, "w", encoding="utf-8") as f:
                    f.write(_LOGGING_CONFIG_TEMPLATE.strip())
                logging.warning(
                    f"No logging config yaml found - created new logging config file from template at: {logger_config_path}"
                )
            except Exception as e:
                raise RuntimeError(f"Failed to create logging config file: {str(e)}")

        with open(logger_config_path, "r", encoding="utf-8") as f:
            logging_config = yaml.safe_load(f)

        # Ensure all FileHandler paths have existing directories
        for handler in logging_config.get("handlers", {}).values():
            if handler.get("class") == "logging.FileHandler":
                log_file = handler.get("filename")
                if log_file:
                    _make_dir(log_file)

        # Apply logging configuration
        logging.config.dictConfig(logging_config)

        _logger_config_loaded = True

    if not os.path.exists(config_path):
        _make_dir(config_path)
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(_CONFIG_TEMPLATE.strip())
            logging.warning(
                f"No config yaml found - created new config file from template at: {config_path}"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to create config file: {str(e)}")

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


_CONFIG_TEMPLATE = """# Git2Base 配置文件模板
input:
  include: []
  exclude: [".vscode", "data", "doc"]

output:
  type: "csv"  # 支持postgresql或sqlite或者csv
  csv:
    path: "data"  # 默认为项目的data相对路径
  postgresql:
    host: "localhost"
    port: 5432
    database: "gitbase"
    user: "gituser"
    password: "giko"
  sqlite:
    database: "gitbase.db"  # SQLite数据库文件路径 - 默认为项目的根路径

stacks:
  - name: XML
    paths: []
    extensions: ["xml"]
  - name: Script
    paths: []
    extensions: ["sh", "bat"]
  - name: Python
    paths: ["config", "database", "git", "notebooks"]
    extensions: ["py"]
  - name: PyTest
    paths: ["tests"]
    extensions: ["py"]
  - name: Yaml
    paths: []
    extensions: ["yaml"]
  - name: Jupyter
    paths: [notebooks]
    extensions: ["ipynb"]

analyzers:
  - name: FileLineCount
    class: "FileLineCountAnalyzer"
    tech_stacks: ["All"]
  - name: FileCharCount
    class: "FileCharCountAnalyzer"
    tech_stacks: ["All"]
  - name: XMLElementCount
    class: "XMLElementCountAnalyzer"
    tech_stacks: ["XML"]
"""

_LOGGING_CONFIG_TEMPLATE = """
version: 1
disable_existing_loggers: False

formatters:
  simple:
    format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: simple
    stream: ext://sys.stdout

  git2base:
    class: logging.FileHandler
    level: DEBUG
    formatter: simple
    filename: logs/git2base.log
    encoding: utf-8

  no_techstack_identified:
    class: logging.FileHandler
    level: INFO
    formatter: simple
    filename: logs/no_techstack_identified.log
    encoding: utf-8

  analyzer_test:
    class: logging.FileHandler
    level: INFO
    formatter: simple
    filename: logs/analyzer_test.log
    encoding: utf-8

loggers:
  git2base:
    level: DEBUG
    handlers: [console, git2base]
    propagate: true

  no_techstack_identified:
    level: INFO
    handlers: [console, no_techstack_identified]
    propagate: true

  analyzer_test:
    level: INFO
    handlers: [console, analyzer_test]
    propagate: true

root:
  level: WARNING
  handlers: [console]
"""
