import logging
from logging.handlers import RotatingFileHandler
from os import makedirs
from os.path import join as join_path


LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DIR = "log"


def setup_logging():
    makedirs(LOG_DIR, exist_ok=True)
    # корневой логгер — на всякий случай
    logging.basicConfig(level=logging.ERROR)

    # ===== BOT LOGGER =====
    bot_handler = RotatingFileHandler(
        join_path(LOG_DIR, "bot.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    bot_handler.setLevel(logging.ERROR)
    bot_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    bot_logger = logging.getLogger("telegram_bot")
    bot_logger.setLevel(logging.ERROR)
    bot_logger.addHandler(bot_handler)
    bot_logger.propagate = False

    # aiogram
    logging.getLogger("aiogram").addHandler(bot_handler)

    # ===== SERVICE LOGGER =====
    service_handler = RotatingFileHandler(
        join_path(LOG_DIR,"service.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    service_handler.setLevel(logging.ERROR)
    service_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    service_logger = logging.getLogger("service")
    service_logger.setLevel(logging.ERROR)
    service_logger.addHandler(service_handler)
    service_logger.propagate = False

