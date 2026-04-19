import logging
from configparser import ConfigParser

_log_level = logging.INFO

class CustomConfigParser(ConfigParser):
    def __init__(self):
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
        return self.getint('default', 'log_level')

    def write_config(self):
        with open('config.ini', 'w') as config_file:
            self.write(config_file)


config = CustomConfigParser()