import logging
from datetime import datetime, timezone


class UTCFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.strftime(datefmt or "%Y-%m-%d %H:%M:%S UTC")


class Logger:
    def __init__(self, log_file="service.log", log_level=logging.DEBUG):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)

        console_handler = logging.StreamHandler()
        file_handler = logging.FileHandler(log_file)

        formatter = UTCFormatter(
            '{asctime} | {levelname} | {pathname} | {module}:{funcName}:{lineno} | {message}',
            style='{',
        )

        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)


    def get_logger(self):
        return self.logger
    

custom_logger = Logger()
logger = custom_logger.get_logger()