from aiogram import Router, F
from aiogram.types import Message
from service import file_manager
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from telegram_bot.keyboards import build_keyboard_with_pagination, build_search_keyboard
from database.database_crud import users_database
from telegram_bot.messages import msgs_handler_search
import logging


router = Router()
logger = logging.getLogger("telegram_bot")


class PaginationState(StatesGroup):
    viewing_list = State()


class SearchState(StatesGroup):
    choose_type = State()
    by_contract = State()
    by_phone = State()
    by_address = State()
    partial = State()


@router.message(Command("search"))
async def cmd_search(message: Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        if not users_database.cash.get(user_id):
            return None
        await state.set_state(SearchState.choose_type)
        await message.answer(
            text=msgs_handler_search['search_method'],
            parse_mode='HTML',
            reply_markup=await build_search_keyboard()
        )
    except Exception:
        logger.exception("handler_search.cmd_search")


@router.message(StateFilter(SearchState.by_contract, SearchState.by_phone, SearchState.by_address), F.text)
async def search_by_key(message: Message, state: FSMContext):
    try:
        # get the current state
        current_state = await state.get_state()  # вернёт строку "SearchState:by_contract" и т.д.

        if current_state is None:
            raise
        # extract the name of a specific state.
        search_type = current_state.split(":")[-1]  # "by_contract", "by_phone", "partial"

        folders_list: list[dict] = file_manager.search_folders_by_key(query=message.text.strip(), search_type=search_type)
        if not bool(folders_list):
            await message.answer(text=msgs_handler_search["not_found__"], parse_mode='HTML')
            return
        else:
            await state.set_state(PaginationState.viewing_list)
            await state.update_data(current_page=0, items=folders_list)  # Save in FSM)
            await message.answer(
                text=f'{msgs_handler_search["was_found"]}{str(len(folders_list))}',
                parse_mode="HTML",
                reply_markup=await build_keyboard_with_pagination(folders_list)  # Shows pagination
            )
        await state.clear()
    except Exception:
        logger.exception("handler_search.search_by_key")


@router.message(F.text)
async def search_by_partial_query(message: Message, state: FSMContext):
    print(await state.get_state())
    user_id = message.from_user.id
    if not users_database.cash.get(user_id):
        return None

    try:
        folders_list: list[dict] = file_manager.search_folders_by_partial(message.text.strip())
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
        logger.exception("handler_search.search_by_partial_query")
