import multiprocessing
from folder_watcher import run_watcher
from telegram_bot.bot import start_bot_wrapper

if __name__ == "__main__":
    multiprocessing.set_start_method("fork", force=True)
    new_folders_queue = multiprocessing.Queue()
    process_monitoring = multiprocessing.Process(target=run_watcher, args=(new_folders_queue,))
    process_bot = multiprocessing.Process(target=start_bot_wrapper, args=(new_folders_queue,))
    process_monitoring.start()
    process_bot.start()
