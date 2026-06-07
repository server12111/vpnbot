import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from config import ADMIN_IDS

router = Router()

class AdminStates(StatesGroup):
    waiting_broadcast = State()
    waiting_new_admin = State()
    waiting_support = State()
    waiting_channel = State()

def is_admin(tg_id: int) -> bool:
    return tg_id in ADMIN_IDS or tg_id in db.get_admin_ids()

def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="adm:stats"),
            InlineKeyboardButton(text="👥 Пользователи", callback_data="adm:users"),
        ],
        [
            InlineKeyboardButton(text="📣 Рассылка", callback_data="adm:broadcast"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="adm:settings"),
        ],
        [
            InlineKeyboardButton(text="➕ Добавить админа", callback_data="adm:add_admin"),
            InlineKeyboardButton(text="🚫 Удалить админа", callback_data="adm:del_admin"),
        ],
    ])

@router.message(Command("admin"))
async def admin_panel(message: Message):
    # Если нет ни одного админа — первый запустивший становится админом
    if not ADMIN_IDS and not db.get_admin_ids():
        db.add_admin(message.from_user.id, message.from_user.username)
        await message.answer(
            f"✅ Вы добавлены как первый администратор!\nID: <code>{message.from_user.id}</code>",
            parse_mode="HTML"
        )

    if not is_admin(message.from_user.id):
        await message.answer(f"❌ У вас нет доступа.\nВаш ID: <code>{message.from_user.id}</code>", parse_mode="HTML")
        return
    await message.answer("🔧 <b>Панель администратора</b>", parse_mode="HTML", reply_markup=admin_menu_kb())

@router.callback_query(F.data == "adm:stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    s = db.get_stats()
    earnings_text = ""
    for currency, amount in s["earnings"].items():
        label = {"XTR": "⭐ Stars", "USDT": "🤖 CryptoBot", "TON": "💎 TON"}.get(currency, currency)
        earnings_text += f"  {label}: {amount}\n"

    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"👤 Всего пользователей: {s['total_users']}\n"
        f"✅ Активных подписок: {s['active_subs']}\n"
        f"🆕 Новых сегодня: {s['new_today']}\n"
        f"📅 Новых за неделю: {s['new_week']}\n"
        f"💰 Всего оплат: {s['total_paid']}\n"
        f"👥 Рефералов выдано: {s['total_referrals']}\n\n"
        f"💵 <b>Доходы:</b>\n{earnings_text or '  Нет данных'}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data == "adm:users")
async def admin_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    s = db.get_stats()
    text = (
        f"👥 <b>Пользователи</b>\n\n"
        f"Всего: {s['total_users']}\n"
        f"С активной подпиской: {s['active_subs']}\n"
        f"Без подписки: {s['total_users'] - s['active_subs']}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")]
    ])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data == "adm:broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.waiting_broadcast)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="adm:cancel")]
    ])
    await callback.message.edit_text(
        "📣 <b>Рассылка</b>\n\nВведите текст сообщения (поддерживается HTML):",
        parse_mode="HTML",
        reply_markup=kb
    )

@router.message(AdminStates.waiting_broadcast)
async def admin_broadcast_send(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    users = db.get_all_users()
    sent = 0
    failed = 0
    status_msg = await message.answer(f"📣 Начинаю рассылку {len(users)} пользователям...")
    for user in users:
        try:
            await message.bot.send_message(user["tg_id"], message.text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await status_msg.edit_text(
        f"✅ Рассылка завершена!\n\n"
        f"📨 Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}"
    )

@router.callback_query(F.data == "adm:settings")
async def admin_settings(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    support = db.get_setting("support_username", "не задан")
    channel = db.get_setting("required_channel", "не задан")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Изменить поддержку", callback_data="adm:set_support")],
        [InlineKeyboardButton(text="📢 Обязательный канал", callback_data="adm:set_channel")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")],
    ])
    await callback.message.edit_text(
        f"⚙️ <b>Настройки</b>\n\n"
        f"💬 Поддержка: {support}\n"
        f"📢 Обязательный канал: {channel}",
        parse_mode="HTML",
        reply_markup=kb
    )

@router.callback_query(F.data == "adm:set_support")
async def admin_set_support_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.waiting_support)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="adm:cancel")]
    ])
    await callback.message.edit_text(
        "✏️ Введите юзернейм поддержки (например @my_support):",
        reply_markup=kb
    )

@router.message(AdminStates.waiting_support)
async def admin_set_support_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    db.set_setting("support_username", message.text.strip())
    await message.answer(f"✅ Поддержка обновлена: {message.text.strip()}", reply_markup=admin_menu_kb())

@router.callback_query(F.data == "adm:set_channel")
async def admin_set_channel_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.waiting_channel)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Отключить канал", callback_data="adm:disable_channel")],
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="adm:cancel")],
    ])
    await callback.message.edit_text(
        "📢 Введите @username канала (например @mychannel):\n\n"
        "⚠️ Бот должен быть администратором в этом канале!",
        reply_markup=kb
    )

@router.message(AdminStates.waiting_channel)
async def admin_set_channel_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    channel = message.text.strip()
    db.set_setting("required_channel", channel)
    await message.answer(f"✅ Обязательный канал установлен: {channel}", reply_markup=admin_menu_kb())

@router.callback_query(F.data == "adm:disable_channel")
async def admin_disable_channel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    db.set_setting("required_channel", "")
    await callback.answer("✅ Обязательный канал отключён!")
    await callback.message.edit_text("🔧 <b>Панель администратора</b>", parse_mode="HTML", reply_markup=admin_menu_kb())

@router.callback_query(F.data == "adm:add_admin")
async def admin_add_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AdminStates.waiting_new_admin)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Отмена", callback_data="adm:cancel")]
    ])
    await callback.message.edit_text(
        "➕ Введите Telegram ID нового администратора:",
        reply_markup=kb
    )

@router.message(AdminStates.waiting_new_admin)
async def admin_add_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    try:
        new_id = int(message.text.strip())
        db.add_admin(new_id)
        await message.answer(f"✅ Админ {new_id} добавлен!", reply_markup=admin_menu_kb())
    except ValueError:
        await message.answer("❌ Неверный формат ID. Введите число.")

@router.callback_query(F.data == "adm:del_admin")
async def admin_del_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    admins = db.get_all_admins()
    if not admins:
        await callback.answer("Нет администраторов в базе.", show_alert=True)
        return
    buttons = []
    for a in admins:
        name = a["username"] or str(a["tg_id"])
        buttons.append([InlineKeyboardButton(
            text=f"🚫 {name} ({a['tg_id']})",
            callback_data=f"adm:del:{a['tg_id']}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm:back")])
    await callback.message.edit_text(
        "🚫 Выберите администратора для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.callback_query(F.data.startswith("adm:del:"))
async def admin_del_confirm(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    admin_id = int(callback.data.split(":")[2])
    db.remove_admin(admin_id)
    await callback.answer(f"✅ Админ {admin_id} удалён!")
    await callback.message.edit_text("🔧 <b>Панель администратора</b>", parse_mode="HTML", reply_markup=admin_menu_kb())

@router.callback_query(F.data == "adm:back")
async def admin_back(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("🔧 <b>Панель администратора</b>", parse_mode="HTML", reply_markup=admin_menu_kb())

@router.callback_query(F.data == "adm:cancel")
async def admin_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🔧 <b>Панель администратора</b>", parse_mode="HTML", reply_markup=admin_menu_kb())
