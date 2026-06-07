from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import PLANS

def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛒 Купить VPN"), KeyboardButton(text="👤 Личный кабинет")],
        [KeyboardButton(text="📋 Инструкция"), KeyboardButton(text="💬 Поддержка")],
    ], resize_keyboard=True)

def plans_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for key, plan in PLANS.items():
        buttons.append([InlineKeyboardButton(
            text=f"{plan['name']} — {plan['rub']}₽ / {plan['stars']}⭐",
            callback_data=f"plan:{key}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def payment_methods_keyboard(plan_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data=f"pay:stars:{plan_key}")],
        [InlineKeyboardButton(text="💳 Platega (карта)", callback_data=f"pay:platega:{plan_key}")],
        [InlineKeyboardButton(text="🤖 CryptoBot (USDT)", callback_data=f"pay:crypto:{plan_key}")],
        [InlineKeyboardButton(text="💎 TON (TonKeeper)", callback_data=f"pay:ton:{plan_key}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back:plans")],
    ])

def cabinet_keyboard(has_sub: bool, can_bonus: bool = True) -> InlineKeyboardMarkup:
    buttons = []
    if has_sub:
        buttons.append([InlineKeyboardButton(text="🔗 Получить конфиг", callback_data="cabinet:config")])
        buttons.append([InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="cabinet:extend")])
    else:
        buttons.append([InlineKeyboardButton(text="🛒 Купить подписку", callback_data="cabinet:buy")])
    buttons.append([InlineKeyboardButton(text="👥 Мои рефералы", callback_data="cabinet:referral")])
    if can_bonus:
        buttons.append([InlineKeyboardButton(text="🎁 Получить бонус (+1 день)", callback_data="cabinet:bonus")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
