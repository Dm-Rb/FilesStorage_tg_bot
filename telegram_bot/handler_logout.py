from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.database_crud import users_database
from telegram_bot.keyboards import logout_keyboard
from telegram_bot.messages import msgs_handler_logout
import logging


"""
This module contains handlers for deleting user data from the SQLite database 
and removing all related data from the cache (which stores user information).
"""


router = Router()
logger = logging.getLogger("telegram_bot")


class LogoutState(StatesGroup):
    confirm = State()


@router.message(Command("logout"))
async def logout_cmd(message: Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        if users_database.cash.get(user_id):
            await state.set_state(LogoutState.confirm)

            await message.answer(
                text=msgs_handler_logout['logout_confirm'],
                reply_markup=logout_keyboard()
            )
        else:
            return
    except Exception:
        logger.exception("handler_logout.logout_cmd")


@router.message(LogoutState.confirm, F.text == "Да")
async def logout_confirm_yes(message: Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        users_database.delete(user_id)
        await state.clear()
        await message.answer(
            text=msgs_handler_logout['logout_is_success'],
            parse_mode='HTML',
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception:
        logger.exception("handler_logout.logout_confirm_yes")


@router.message(LogoutState.confirm)
async def logout_confirm_no(message: Message, state: FSMContext):
    try:
        await state.clear()
        await message.answer(
            text=msgs_handler_logout['cancel'],
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception:
        logger.exception("handler_logout.logout_confirm_no")
