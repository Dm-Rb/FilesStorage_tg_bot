from aiogram import Bot
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from telegram_bot.handler_search import PaginationState, SearchState
from telegram_bot.messages import info_message, msgs_callbacks
from telegram_bot.keyboards import build_keyboard_with_pagination
from service import file_manager
from aiogram.types import InputMediaPhoto, BufferedInputFile


router = Router()


@router.callback_query(F.data.in_(["prev_page", "next_page"]), StateFilter(PaginationState.viewing_list))
async def handle_pagination(callback: types.CallbackQuery, state: FSMContext):
    # state -> {current_page: int, items: list}
    data = await state.get_data()
    current_page = data.get("current_page", 0)
    items = data.get("items", [])

    if callback.data == "prev_page":
        current_page = max(0, current_page - 1)  # do not decrement the value below 0
    elif callback.data == "next_page":
        current_page += 1

    await state.update_data(current_page=current_page)

    # generate keyboard object
    keyboard = await build_keyboard_with_pagination(items, current_page)

    # editing the message (to avoid creating a new one)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith('folderId'))
async def handle_press_btn(callback: types.CallbackQuery, bot: Bot):

    folder_id = int(callback.data.lstrip('folderId_')) # callback_data=f"folderId_{str(item['folder_id'])}"
    # caption - text description for a group of images
    caption: str | None = info_message(file_manager.get_data_from_info_file(folder_id))
    # find all image files in the folder and convert them to bytes
    images_bytes = file_manager.prepare_images(folder_id)
    if not images_bytes:
        #  сlose the inline button (remove the loading spinner).
        await callback.answer()

        # send message to user
        await bot.send_message(
            chat_id=callback.from_user.id,
            text="В этом разделе отсутствуют какие либо файлы. Возможно сам раздел был удалён"
        )
        return

    # if files exist
    await callback.answer()
    media_group = []
    # telegram API always requires a filename, even for bytes, so <filename> must be specified for BufferedInputFile
    for i, img_bytes in enumerate(images_bytes):
        media_group.append(
            InputMediaPhoto(
                media=BufferedInputFile(
                    img_bytes,
                    filename=f'image_{i}.jpg'
                ),
                caption=caption if i == 0 else None,
                parse_mode="HTML"
            )
        )
    # send message with images and text
    await bot.send_media_group(
        chat_id=callback.from_user.id,
        media=media_group,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("search:"))
async def search_type_callback(callback: types.CallbackQuery, state: FSMContext):

    search_type = callback.data.split(":")[1]

    match search_type:
        case "contract":
            await state.set_state(SearchState.by_contract)
            text = msgs_callbacks["contract"]
        case "phone":
            await state.set_state(SearchState.by_phone)
            text = msgs_callbacks["phone"]
        case "address":
            await state.set_state(SearchState.by_address)
            text = msgs_callbacks["address"]
        case "partial":
            await state.clear()
            text = msgs_callbacks["partial"]
        case _:
            await state.clear()
            text = "Unknown error"
    await callback.message.edit_text(
        text=text,
        reply_markup=None  # remove kb
    )

    await callback.answer()
