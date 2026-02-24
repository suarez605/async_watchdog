import logging


class WatchdogFormatter(logging.Formatter):
    def format(self, record):
        original_msg = super().format(record)
        return f"[Watchdog] {original_msg}"


def get_logger(name=__name__, level=logging.INFO):
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        formatter = WatchdogFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level)
    return logger
