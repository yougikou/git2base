import os
import threading
import yaml

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
        mod_time = os.path.getmtime('config.yaml')
        with _config_lock:
            if _config_cache is None or mod_time > _config_last_modified:
                try:
                    with open('config.yaml', 'r', encoding='utf-8') as file:
                        config = yaml.safe_load(file)
                        if not isinstance(config, dict):
                            raise ValueError("Config must be a dictionary")
                            
                        # Validate required sections
                        required_sections = ['database', 'analyzers', 'stacks']
                        for section in required_sections:
                            if section not in config:
                                raise ValueError(f"Missing required config section: {section}")
                                
                        _config_cache = config
                        _config_last_modified = mod_time
                except yaml.YAMLError as e:
                    raise ValueError(f"Invalid YAML in config: {str(e)}")
                except OSError as e:
                    raise RuntimeError(f"Failed to read config file: {str(e)}")
                    
            return _config_cache
            
    except Exception as e:
        raise RuntimeError(f"Configuration error: {str(e)}")

def load_stacks_config():
    """Load stacks configuration from cached config"""
    config = _load_config()
    return config.get('stacks', [])

def load_analyzer_config():
    """Load analyzer configuration from cached config"""
    config = _load_config()
    return config.get('analyzers', [])