from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from datetime import datetime

import database as db
from keyboards.main import main_menu, cabinet_keyboard, plans_keyboard
from services.xui import build_vless_link, add_client, _get_server

router = Router()

@router.message(F.text == "👤 Личный кабинет")
async def cabinet(message: Message):
    sub = db.get_active_subscription(message.from_user.id)
    ref_count = db.get_user_referrals_count(message.from_user.id)
    can_bonus = db.can_claim_bonus(message.from_user.id)

    if sub:
        expires = datetime.fromisoformat(sub["expires_at"])
        days_left = (expires - datetime.now()).days
        text = (
            f"👤 <b>Личный кабинет</b>\n\n"
            f"✅ Подписка активна\n"
            f"📦 Тариф: {sub['plan']}\n"
            f"⏳ Осталось: {days_left} дней\n"
            f"📅 До: {expires.strftime('%d.%m.%Y')}\n\n"
            f"👥 Рефералов: {ref_count}"
        )
    else:
        text = (
            f"👤 <b>Личный кабинет</b>\n\n"
            f"❌ Активной подписки нет\n\n"
            f"👥 Рефералов: {ref_count}"
        )
    await message.answer(text, parse_mode="HTML", reply_markup=cabinet_keyboard(bool(sub), can_bonus))

@router.callback_query(F.data == "cabinet:config")
async def get_config(callback: CallbackQuery):
    sub = db.get_active_subscription(callback.from_user.id)
    if not sub:
        await callback.answer("Подписка не найдена", show_alert=True)
        return
    server = _get_server(sub["server_id"] if "server_id" in sub.keys() else "s1")
    link = build_vless_link(sub["xui_uuid"], server)
    await callback.message.answer(
        f"🔗 <b>Ваш VPN конфиг:</b>\n\n"
        f"<code>{link}</code>\n\n"
        f"📱 Скопируйте ссылку и вставьте в <b>v2rayNG</b> (Android) или <b>Streisand</b> (iOS)",
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "cabinet:referral")
async def referral_info(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    ref_count = db.get_user_referrals_count(callback.from_user.id)
    bot_info = await callback.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{user['referral_code']}"
    await callback.message.answer(
        f"👥 <b>Реферальная система</b>\n\n"
        f"За каждого друга, который купит подписку,\n"
        f"вы получаете <b>+1 день</b> к своей подписке!\n\n"
        f"🔗 Ваша ссылка:\n<code>{link}</code>\n\n"
        f"👤 Приглашено: {ref_count} чел.",
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "cabinet:bonus")
async def claim_bonus(callback: CallbackQuery):
    if not db.can_claim_bonus(callback.from_user.id):
        await callback.answer("⏳ Бонус уже получен сегодня. Возвращайтесь завтра!", show_alert=True)
        return

    ok = db.claim_bonus(callback.from_user.id)
    if not ok:
        await callback.answer("Бонус недоступен.", show_alert=True)
        return

    from services.xui import get_least_loaded_server
    server = get_least_loaded_server()
    xui_uuid, server_id = db.create_subscription(callback.from_user.id, "Бонус", 1, server["id"])
    await add_client(xui_uuid, callback.from_user.id, 1, server_id)

    await callback.answer("🎁 +1 день добавлен к вашей подписке!", show_alert=True)
    await callback.message.answer(
        "🎁 <b>Бонус получен!</b>\n\n"
        "+1 день добавлен к вашей подписке.\n"
        "Возвращайтесь завтра за следующим бонусом!",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "check_sub")
async def check_subscription(callback: CallbackQuery):
    channel = db.get_setting("required_channel")
    if not channel:
        await callback.answer("✅ Всё в порядке!", show_alert=True)
        return
    try:
        member = await callback.bot.get_chat_member(channel, callback.from_user.id)
        if member.status in ("left", "kicked", "banned"):
            await callback.answer("❌ Вы ещё не подписались на канал!", show_alert=True)
        else:
            await callback.answer("✅ Подписка подтверждена! Теперь можете пользоваться ботом.", show_alert=True)
            await callback.message.delete()
    except Exception:
        await callback.answer("✅ Готово!", show_alert=True)

@router.callback_query(F.data == "cabinet:extend")
async def extend_sub(callback: CallbackQuery):
    await callback.message.edit_text(
        "🔄 Выберите тариф для продления:",
        reply_markup=plans_keyboard()
    )

@router.callback_query(F.data == "cabinet:buy")
async def buy_from_cabinet(callback: CallbackQuery):
    await callback.message.edit_text(
        "💰 Выберите тариф:",
        reply_markup=plans_keyboard()
    )
