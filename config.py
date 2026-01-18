import os
from dotenv import load_dotenv


"""Load environment variables from .env"""


load_dotenv()


class Config:
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    STORAGE_DIR = os.getenv("STORAGE_DIR")
    PASSPHRASE = os.getenv("PASSPHRASE")


config_ = Config()