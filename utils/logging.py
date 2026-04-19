import logging
from logging.handlers import RotatingFileHandler
from utils.config import config
logger = logging.getLogger()
logger.setLevel(config.log_level)
handler = RotatingFileHandler('mas-fail-attr.log', maxBytes=50_000_000,
                              backupCount=3, encoding='utf-8')
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

console = logging.StreamHandler()
console.setLevel(config.log_level)
console.setFormatter(formatter)
logger.addHandler(console)