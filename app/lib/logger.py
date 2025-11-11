import logging
from datetime import datetime as dt, timezone as tz

# Configure the logger
logging.basicConfig(
    format='[%(asctime)s] [%(levelname)s] [%(filename)s] [%(funcName)s] %(message)s',
    datefmt='%m/%d %H:%M:%S',
    level=logging.INFO
)

logger = logging.getLogger("default")
