"""Deliver persisted image bytes; only definitive format errors allow fallback."""
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile

FORMAT_ERRORS = ('photo_invalid_dimensions', 'photo_ext_invalid', 'image_process_failed')


async def send_saved_image(bot, chat, image, filename, **kwargs):
    if filename == 'result.bin':
        return await bot.send_document(chat, BufferedInputFile(image, filename='result.bin'), **kwargs)
    try:
        return await bot.send_photo(chat, BufferedInputFile(image, filename=filename), **kwargs)
    except TelegramBadRequest as error:
        if not any(code in str(error).lower() for code in FORMAT_ERRORS):
            raise
    return await bot.send_document(chat, BufferedInputFile(image, filename=filename), **kwargs)
