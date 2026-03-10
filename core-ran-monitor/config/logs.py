"""
Logging configuration module.

This module initializes the application logger using parameters
defined in the config.ini configuration file. It configures both
console and file logging with independent log levels.
"""
from configparser import ConfigParser
import logging
import sys
import os

# Load configuration from config.ini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(BASE_DIR, 'config.ini')

parser = ConfigParser()
parser.read(config_path)

# Initialize the logger
logger = logging.getLogger(__name__)

# Set global logging level based on config
logger.setLevel(parser['debug']['maxLevel'])

# Initialize handlers: Console (stdout) and File
stream_handler = logging.StreamHandler(sys.stdout)
file_handler = logging.FileHandler(filename=parser['debug']['file'], encoding='utf-8')

# Set specific logging levels for each handler
stream_handler.setLevel(parser['debug']['mode'])
file_handler.setLevel(parser['debug']['filemode'])

# Define log message format
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(filename)s - %(lineno)d - %(message)s'
)
stream_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

# Add handlers to the logger instance
logger.addHandler(stream_handler)
logger.addHandler(file_handler)
