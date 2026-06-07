from typing import Callable, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

import database as db

EXEMPT_CALLBACKS = {"check_sub"}

class ChannelSubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, dict], Awaitable[Any]],
        event: Any,
        data: dict,
    ) -> Any:
        channel = db.get_setting("required_channel")
        if not channel:
            return await handler(event, data)

        # Определяем user_id
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            if event.data in EXEMPT_CALLBACKS:
                return await handler(event, data)
            user_id = event.from_user.id if event.from_user else None
        else:
            return await handler(event, data)

        if not user_id:
            return await handler(event, data)

        # Проверяем подписку
        bot = data["bot"]
        try:
            from handlers.admin import is_admin
            if is_admin(user_id):
                return await handler(event, data)

            member = await bot.get_chat_member(channel, user_id)
            if member.status in ("left", "kicked", "banned"):
                await _send_subscribe_required(event, channel)
                return
        except Exception:
            pass  # При ошибке — разрешаем доступ

        return await handler(event, data)


async def _send_subscribe_required(event, channel: str):
    channel_link = channel if channel.startswith("http") else f"https://t.me/{channel.lstrip('@')}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться на канал", url=channel_link)],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")],
    ])
    text = (
        "⚠️ <b>Для использования бота необходимо подписаться на наш канал!</b>\n\n"
        "После подписки нажмите кнопку «Я подписался»."
    )
    if isinstance(event, Message):
        await event.answer(text, parse_mode="HTML", reply_markup=kb)
    elif isinstance(event, CallbackQuery):
        await event.answer("Сначала подпишитесь на канал!", show_alert=True)
        await event.message.answer(text, parse_mode="HTML", reply_markup=kb)
