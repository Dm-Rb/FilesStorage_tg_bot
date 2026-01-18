from aiogram import Router, F
from aiogram.types import Message
from service import file_manager
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from telegram_bot.keyboards import build_keyboard_with_pagination
from database.database_crud import users_database
from telegram_bot.messages import msgs_handler_search
import logging


router = Router()
logger = logging.getLogger("telegram_bot")


class PaginationState(StatesGroup):
    viewing_list = State()


@router.message(F.text)
async def base_search(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not users_database.cash.get(user_id):
        return None

    try:
        folders_list: list[dict] = file_manager.match_search(message.text)
        if not bool(folders_list):
            await message.answer(text=msgs_handler_search["not_found"], parse_mode='HTML')
            return
        else:
            await state.set_state(PaginationState.viewing_list)
            await state.update_data(current_page=0, items=folders_list)  # Save in FSM)
            await message.answer(
                text=f'{msgs_handler_search["was_found"]}{str(len(folders_list))}',
                parse_mode="HTML",
                reply_markup=await build_keyboard_with_pagination(folders_list)  # Shows pagination
            )
    except Exception:
        logger.exception("handler_search.base_search")


