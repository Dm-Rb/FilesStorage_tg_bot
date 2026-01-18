from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from telegram_bot.handler_search import PaginationState
from telegram_bot.keyboards import build_keyboard_with_pagination
from service import file_manager
from aiogram.types import InputMediaPhoto, BufferedInputFile
from aiogram import Bot


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


@router.callback_query(F.data.startswith('item_'))
async def handle_press_btn(callback: types.CallbackQuery, bot: Bot):
    folder_id = int(callback.data.lstrip('item_'))
    caption = file_manager.get_text_description(folder_id)  # Описание для группы
    # Читаем файлы в каталоге игнорируя НЕ-изображения, преобразуем в байты
    images_bytes = file_manager.prepare_images(folder_id)
    if not images_bytes:
        #  закрываем кнопку (убираем часики)
        await callback.answer()

        # отправляем сообщение пользователю
        await bot.send_message(
            chat_id=callback.from_user.id,
            text="В этом разделе отсутствуют какие либо файлы"
        )
        return

    # если файлы есть
    await callback.answer()
    media_group = []
    # Telegram API обязательно требует имя файла, даже если это байты, поэтому необходимо задать <filename> для BufferedInputFile
    for i, img_bytes in enumerate(images_bytes):
        media_group.append(
            InputMediaPhoto(
                media=BufferedInputFile(
                    img_bytes,
                    filename=f'image_{i}.jpg'
                ),
                caption=caption if i == 0 else None
            )
        )
    # send message with images and text
    await bot.send_media_group(
        chat_id=callback.from_user.id,
        media=media_group,
    )
    await callback.answer()
