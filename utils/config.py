"""Project configuration loader for logging and runtime defaults."""

import logging
from configparser import ConfigParser

_log_level = logging.INFO

class CustomConfigParser(ConfigParser):
    """Config parser that bootstraps defaults and auto-creates local config."""

    def __init__(self):
        """Initialize parser with default values and ensure config file exists."""
        super().__init__()
        self.read_dict({
            'default': {
                'log_level': _log_level
            }
        })
        if not self.read('config.ini'):
            self.write_config()

    @property
    def log_level(self):
        """Return configured log level as integer value."""
        return self.getint('default', 'log_level')

    def write_config(self):
        """Persist current configuration to ``config.ini``."""
        with open('config.ini', 'w') as config_file:
            self.write(config_file)


config = CustomConfigParser()