from config import config_
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from telegram_bot import handler_login, handler_logout, handler_search, callbacks
from telegram_bot.middleware_ban import BanMiddleware
from service import file_manager
from multiprocessing.queues import Queue
from logging_config import setup_logging


async def start_bot():

    bot = Bot(token=config_.BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(handler_login.router)
    dp.include_router(handler_logout.router)
    dp.include_router(handler_search.router)
    dp.include_router(callbacks.router)
    dp.update.middleware(BanMiddleware())  # This connected middleware contains the logic for ignoring banned users

    # Set commands
    await bot.set_my_commands([
        BotCommand(command="start", description="Старт/Вход"),
        BotCommand(command="search", description="Поиск"),
        BotCommand(command="logout", description="Выход"),

    ])

    try:
        await dp.start_polling(bot)
    finally:
        # Close API client after end of work
        await bot.session.close()


async def process_watchdog_queue(queue):
    loop = asyncio.get_running_loop()
    while True:
        # reading from a multiprocessing.Queue in a separate thread without blocking the event loop
        file_event: dict = await loop.run_in_executor(None, queue.get)
        if file_event.get('event', '') == "new":  # new folder
            file_manager.add_folder(file_event['folder_name'])
        elif file_event.get('event', '') == 'del':  # remove folder
            file_manager.remove_folder(file_event['folder_name'])
        else:
            continue


async def main(new_folders_queue: Queue | None = None):
    # creating a task to process the Watchdog queue
    if new_folders_queue:
        asyncio.create_task(process_watchdog_queue(new_folders_queue))

    # run Bot
    await start_bot()


def start_bot_wrapper(new_folders_queue: Queue | None = None):
    # wrapper for running in a separate process at the entry point
    setup_logging()
    asyncio.run(main(new_folders_queue))
