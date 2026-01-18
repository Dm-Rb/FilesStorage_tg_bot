from aiogram import types
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


ITEMS_PER_PAGE = 10  # Keyboard button limit on "page"


async def build_keyboard_with_pagination(dir_names_array: list[dict], page: int = 0) -> InlineKeyboardMarkup:
    """Build inline keyboard with pagination"""

    start_idx = page * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    current_page_items = dir_names_array[start_idx:end_idx]

    keyboard = InlineKeyboardBuilder()

    # Add buttons
    for item in current_page_items:
        button_name = f"📂 {item['folder_name']}"
        if len(button_name) > 62:
            button_name = f"{button_name[:62]}..."

        keyboard.add(
            InlineKeyboardButton(
                text=button_name,
                callback_data=f"item_{str(item['id'])}"
            )
        )

    navigation_buttons = []

    # Button "Back" (if current page not first)
    if page > 0:
        navigation_buttons.append(
            types.InlineKeyboardButton(text="⬅️ Назад", callback_data="prev_page")
        )

    # Button "Next" (if current page not last)
    if end_idx < len(dir_names_array):
        navigation_buttons.append(
            types.InlineKeyboardButton(text="Далее ➡️", callback_data="next_page")
        )

    # Arrange elements
    keyboard.adjust(1)  # One element per row
    if navigation_buttons:
        keyboard.row(*navigation_buttons)
    return keyboard.as_markup()

def logout_keyboard():
    # build logout keyboard
    logout_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Да"), KeyboardButton(text="Нет")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return logout_kb
