from aiogram import Router
from aiogram.types import Message
from database.database_crud import users_database
from config import config_
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from telegram_bot.messages import msgs_handler_login
import logging


"""
This module contains handlers for authenticating Telegram users using a password.
PASSPHRASE - a constant loaded from the .env configuration file.
MAX_ATTEMPTS_PASSPHRASE is a constant that defines the maximum allowed password attempts. If exceeded, the user is 
blacklisted and all future messages are ignored by the bot.
When a user enters the correct PASSPHRASE, their user_id is saved in the SQLite database and in the cache 
with a flag of 1, granting full access.
If the user fails to enter the correct PASSPHRASE within MAX_ATTEMPTS_PASSPHRASE attempts, 
their user_id is saved with a flag of 2, indicating a ban.
The ban mechanism itself is implemented in the <middleware_ban.py> module.
"""


router = Router()
PASSPHRASE = config_.PASSPHRASE
MAX_ATTEMPTS_PASSPHRASE = 5  # Maximum number of password attempts before a ban is issued
logger = logging.getLogger("telegram_bot")


class AuthStates(StatesGroup):
    waiting_for_password = State()  # Waiting for password


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Initializing user authentication with a passphrase. Failed attempts lead to banlist addition"""
    # -users_db.cash - dict with users work. key - int(tg_user_id), value - 1 or 2 or 3 (флаг)
    # -for example {1234: 1, 4567:2}
    # users flags: 1 - access, 2 - ban
    user_id = message.chat.id

    try:
        if users_database.cash.get(user_id, None):
            if users_database.cash.get(user_id, 0) == 1:
                await message.answer(text=msgs_handler_login['user_is_auth'], parse_mode="HTML")
                return
            elif users_database.cash.get(user_id, 0) == 2:
                await message.answer(msgs_handler_login['was_ban'], parse_mode="HTML")
                return

        # Patches the hole when spamming /start command during active FSM
        current_state = await state.get_state()
        if current_state == AuthStates.waiting_for_password:   # If the user has an active state in FSM
            await message.answer(text=msgs_handler_login['user_is_auth_process'], parse_mode="HTML")
        else:
            await state.set_state(AuthStates.waiting_for_password)  # Init FSM
            await state.update_data(attempts=0)  # Init try counter
            await message.answer(text=msgs_handler_login['demand_pass'], parse_mode="HTML")
    except Exception:
        logger.exception("handler_login.cmd_start")


@router.message(AuthStates.waiting_for_password)
async def process_password(message: Message, state: FSMContext):
    """Processing of the user-entered passphrase"""

    try:
        user_data = await state.get_data()
        attempts = user_data.get("attempts", 0) + 1  # try counter

        if message.text == PASSPHRASE:
            #  Add to user list (user cash) with flag 1 (write and edit permission)
            users_database.insert(user_tg_id=message.from_user.id, flag=1)  # record to DB
            await message.answer(msgs_handler_login['successful_auth'], parse_mode="HTML")
            await state.clear()
            return

        if attempts >= MAX_ATTEMPTS_PASSPHRASE:
            await message.answer(text=msgs_handler_login['ban'], parse_mode="HTML")
            users_database.cash[message.from_user.id] = 2  # Add to user list (user cash) with flag 3 (ban)
            users_database.insert(user_tg_id=message.from_user.id, flag=2)  # Пишем в БД
            await state.clear()
            return

        await state.update_data(attempts=attempts)
        remaining = MAX_ATTEMPTS_PASSPHRASE - attempts
        if remaining:
            await message.answer(text=f"{msgs_handler_login['invalid_pass']} {str(remaining)}", parse_mode="HTML")
    except Exception:
        logger.exception("handler_login.process_password")

