from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, CommandObject

import database as db
from keyboards.main import main_menu, plans_keyboard
from services.xui import add_client
from config import TRIAL_DAYS

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    ref_code = None
    if command.args and command.args.startswith("ref_"):
        ref_code = command.args[4:]

    user, is_new = db.get_or_create_user(
        message.from_user.id,
        message.from_user.username,
        referred_by_code=ref_code
    )

    await message.answer(
        "👋 Добро пожаловать в VPN Bot!\n\n"
        "🔒 Быстрый, надёжный и безопасный VPN\n"
        "📍 Сервер: Нидерланды 🇳🇱\n"
        "⚡ Протокол: VLESS + Reality\n\n"
        "Выберите действие:",
        reply_markup=main_menu()
    )

    # Пробный период для новых пользователей
    if is_new and not user["trial_used"]:
        db.mark_trial_used(message.from_user.id)
        xui_uuid = db.create_subscription(message.from_user.id, "Пробный", TRIAL_DAYS)
        await add_client(xui_uuid, message.from_user.id, TRIAL_DAYS)
        await message.answer(
            f"🎁 <b>Подарок от нас!</b>\n\n"
            f"Мы дали тебе <b>{TRIAL_DAYS} день</b> бесплатного VPN!\n\n"
            f"👤 Перейди в «Личный кабинет» чтобы получить конфиг и подключиться.",
            parse_mode="HTML"
        )

@router.message(F.text == "🛒 Купить VPN")
async def buy_vpn(message: Message):
    await message.answer(
        "💰 Выберите тариф:",
        reply_markup=plans_keyboard()
    )

@router.message(F.text == "📋 Инструкция")
async def instruction(message: Message):
    await message.answer(
        "📱 <b>Как подключиться к VPN:</b>\n\n"
        "1️⃣ Купите подписку\n"
        "2️⃣ Получите конфиг в «Личном кабинете»\n"
        "3️⃣ Установите <b>v2rayNG</b> (Android) или <b>Streisand</b> (iOS)\n"
        "4️⃣ Нажмите «+» и вставьте конфиг\n"
        "5️⃣ Подключайтесь!\n\n"
        "❓ Есть вопросы? Напишите в поддержку.",
        parse_mode="HTML"
    )

@router.message(F.text == "💬 Поддержка")
async def support(message: Message):
    support_username = db.get_setting("support_username", "@support")
    await message.answer(
        f"💬 По всем вопросам пишите: {support_username}\n\n"
        f"⏰ Отвечаем в течение 1 часа"
    )

@router.callback_query(F.data == "back:plans")
async def back_to_plans(callback: CallbackQuery):
    await callback.message.edit_text(
        "💰 Выберите тариф:",
        reply_markup=plans_keyboard()
    )
