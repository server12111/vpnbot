import time
from aiogram import Router, F
from aiogram.types import (
    CallbackQuery, Message, LabeledPrice,
    PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton
)

import database as db
from keyboards.main import payment_methods_keyboard, plans_keyboard
from services.xui import add_client, get_least_loaded_server
from services.cryptobot import create_invoice
from config import PLANS, TON_WALLET, REFERRAL_BONUS_DAYS

router = Router()

async def _activate_subscription(bot, tg_id: int, plan_key: str, currency: str, amount: str, payload: str):
    """Активирует подписку после успешной оплаты."""
    plan = PLANS[plan_key]

    # Проверяем ДО подтверждения оплаты
    is_first_purchase = not db.has_ever_paid(tg_id)

    db.save_payment(tg_id, amount, currency, plan_key, payload)
    db.confirm_payment(payload)
    server = get_least_loaded_server()
    xui_uuid, server_id = db.create_subscription(tg_id, plan["name"], plan["days"], server["id"])
    ok = await add_client(xui_uuid, tg_id, plan["days"], server_id)

    # Реферальный бонус — только за первую покупку
    if is_first_purchase:
        user = db.get_user(tg_id)
        if user and user["referred_by"]:
            given = db.give_referral_bonus(user["referred_by"], tg_id, REFERRAL_BONUS_DAYS)
            if given:
                try:
                    await bot.send_message(
                        user["referred_by"],
                        f"🎉 Ваш реферал купил подписку!\n"
                        f"Вам начислен +{REFERRAL_BONUS_DAYS} день к подписке."
                    )
                except Exception:
                    pass

    if ok:
        await bot.send_message(
            tg_id,
            f"✅ <b>Оплата прошла успешно!</b>\n\n"
            f"📦 Тариф: {plan['name']}\n"
            f"📅 Дней: {plan['days']}\n\n"
            f"Перейдите в 👤 Личный кабинет чтобы получить конфиг.",
            parse_mode="HTML"
        )
    else:
        await bot.send_message(
            tg_id,
            "✅ Оплата получена, но возникла ошибка при создании конфига.\n"
            "Обратитесь в поддержку — мы всё исправим!"
        )

# --- Выбор тарифа ---
@router.callback_query(F.data.startswith("plan:"))
async def choose_plan(callback: CallbackQuery):
    plan_key = callback.data.split(":")[1]
    plan = PLANS[plan_key]
    await callback.message.edit_text(
        f"📦 <b>{plan['name']}</b>\n\n"
        f"⭐ {plan['stars']} Telegram Stars\n"
        f"💳 {plan['rub']}₽ (карта)\n"
        f"🤖 {plan['usdt']} USDT (CryptoBot)\n"
        f"💎 {plan['ton']} TON\n\n"
        f"Выберите способ оплаты:",
        parse_mode="HTML",
        reply_markup=payment_methods_keyboard(plan_key)
    )

# --- Telegram Stars ---
@router.callback_query(F.data.startswith("pay:stars:"))
async def pay_stars(callback: CallbackQuery):
    plan_key = callback.data.split(":")[2]
    plan = PLANS[plan_key]
    await callback.message.delete()
    await callback.message.answer_invoice(
        title=f"VPN — {plan['name']}",
        description=f"Подписка на VPN на {plan['days']} дней. Сервер: Нидерланды 🇳🇱",
        payload=f"stars:{plan_key}:{callback.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label=plan["name"], amount=plan["stars"])],
    )

@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)

@router.message(F.successful_payment)
async def successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    parts = payload.split(":")
    plan_key = parts[1]
    tg_id = int(parts[2])
    plan = PLANS[plan_key]
    await _activate_subscription(
        message.bot, tg_id, plan_key, "XTR", str(plan["stars"]), payload
    )

# --- CryptoBot ---
@router.callback_query(F.data.startswith("pay:crypto:"))
async def pay_crypto(callback: CallbackQuery):
    plan_key = callback.data.split(":")[2]
    plan = PLANS[plan_key]
    payload = f"crypto:{plan_key}:{callback.from_user.id}:{int(time.time())}"

    invoice = await create_invoice(
        amount=plan["usdt"],
        payload=payload,
        description=f"VPN {plan['name']} — {plan['days']} дней"
    )

    if not invoice:
        await callback.answer("Ошибка создания счёта. Попробуйте позже.", show_alert=True)
        return

    db.save_payment(callback.from_user.id, str(plan["usdt"]), "USDT", plan_key, payload)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить в CryptoBot", url=invoice["pay_url"])],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"check:crypto:{payload}")],
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="back:plans")],
    ])
    await callback.message.edit_text(
        f"🤖 <b>Оплата через CryptoBot</b>\n\n"
        f"📦 Тариф: {plan['name']}\n"
        f"💵 Сумма: {plan['usdt']} USDT\n\n"
        f"1. Нажмите кнопку ниже и оплатите\n"
        f"2. Вернитесь и нажмите «Я оплатил»",
        parse_mode="HTML",
        reply_markup=kb
    )

@router.callback_query(F.data.startswith("check:crypto:"))
async def check_crypto(callback: CallbackQuery):
    payload = callback.data[len("check:crypto:"):]
    parts = payload.split(":")
    if len(parts) < 3:
        await callback.answer("Неверный формат.", show_alert=True)
        return

    plan_key = parts[1]
    tg_id = int(parts[2])

    from services.cryptobot import check_invoice
    paid = await check_invoice(payload)

    if paid:
        plan = PLANS[plan_key]
        await _activate_subscription(
            callback.bot, tg_id, plan_key, "USDT", str(plan["usdt"]), payload
        )
        await callback.answer("✅ Оплата подтверждена!")
    else:
        await callback.answer("❌ Оплата не найдена. Подождите немного и попробуйте снова.", show_alert=True)

# --- TON ---
@router.callback_query(F.data.startswith("pay:ton:"))
async def pay_ton(callback: CallbackQuery):
    plan_key = callback.data.split(":")[2]
    plan = PLANS[plan_key]
    comment = f"VPN-{callback.from_user.id}-{plan_key}-{int(time.time())}"

    db.save_payment(callback.from_user.id, str(plan["ton"]), "TON", plan_key, comment)

    ton_link = f"ton://transfer/{TON_WALLET}?amount={int(plan['ton'] * 1e9)}&text={comment}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Открыть TonKeeper", url=ton_link)],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"check:ton:{comment}")],
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="back:plans")],
    ])
    await callback.message.edit_text(
        f"💎 <b>Оплата через TON</b>\n\n"
        f"📦 Тариф: {plan['name']}\n"
        f"💎 Сумма: <code>{plan['ton']} TON</code>\n"
        f"👛 Кошелёк: <code>{TON_WALLET}</code>\n"
        f"💬 Комментарий (обязательно!): <code>{comment}</code>\n\n"
        f"⚠️ Отправьте точную сумму с указанным комментарием!\n\n"
        f"1. Нажмите «Открыть TonKeeper» и оплатите\n"
        f"2. Вернитесь и нажмите «Я оплатил»",
        parse_mode="HTML",
        reply_markup=kb
    )

@router.callback_query(F.data.startswith("check:ton:"))
async def check_ton(callback: CallbackQuery):
    comment = callback.data[len("check:ton:"):]
    parts = comment.split("-")
    if len(parts) < 3:
        await callback.answer("Неверный формат.", show_alert=True)
        return

    tg_id = int(parts[1])
    plan_key = parts[2]
    plan = PLANS.get(plan_key)
    if not plan:
        await callback.answer("Тариф не найден.", show_alert=True)
        return

    await callback.answer("🔍 Проверяем транзакцию...")

    from services.ton import find_transaction_by_comment
    paid = await find_transaction_by_comment(comment, plan["ton"])

    if paid:
        await _activate_subscription(
            callback.bot, tg_id, plan_key, "TON", str(plan["ton"]), comment
        )
    else:
        await callback.message.answer(
            "❌ Транзакция не найдена.\n\n"
            "Убедитесь что:\n"
            "• Отправили правильную сумму\n"
            "• Указали комментарий точно как показано\n"
            "• Транзакция подтверждена в блокчейне (1-2 мин)\n\n"
            "Попробуйте снова через минуту."
        )

# --- Platega ---
@router.callback_query(F.data.startswith("pay:platega:"))
async def pay_platega(callback: CallbackQuery):
    await callback.answer("💳 Оплата картой — скоро будет доступна!", show_alert=True)
