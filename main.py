import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN
import database as db
from handlers import start, cabinet, payment, admin
from middlewares.channel import ChannelSubscriptionMiddleware

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Middleware для проверки подписки на канал
dp.message.middleware(ChannelSubscriptionMiddleware())
dp.callback_query.middleware(ChannelSubscriptionMiddleware())

dp.include_router(admin.router)
dp.include_router(start.router)
dp.include_router(cabinet.router)
dp.include_router(payment.router)

async def notify_expiring():
    subs = db.get_expiring_soon(hours=24)
    for sub in subs:
        try:
            await bot.send_message(
                sub["tg_id"],
                "⚠️ Ваша подписка истекает через 24 часа!\n\n"
                "Перейдите в 👤 Личный кабинет чтобы продлить."
            )
        except Exception:
            pass

async def check_ton_payments():
    from services.ton import find_transaction_by_comment
    from services.xui import add_client
    from config import PLANS

    with db.get_conn() as conn:
        pending = conn.execute(
            "SELECT * FROM payments WHERE status = 'pending' AND currency = 'TON'"
        ).fetchall()

    for p in pending:
        plan = PLANS.get(p["plan"])
        if not plan:
            continue
        try:
            paid = await find_transaction_by_comment(p["payload"], plan["ton"])
            if paid:
                db.confirm_payment(p["payload"])
                xui_uuid = db.create_subscription(p["tg_id"], plan["name"], plan["days"])
                await add_client(xui_uuid, p["tg_id"], plan["days"])
                await bot.send_message(
                    p["tg_id"],
                    f"✅ <b>TON оплата подтверждена!</b>\n\n"
                    f"📦 Тариф: {plan['name']}\n"
                    f"Перейдите в 👤 Личный кабинет чтобы получить конфиг.",
                    parse_mode="HTML"
                )
        except Exception:
            pass

async def main():
    db.init_db()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(notify_expiring, "interval", hours=12)
    scheduler.add_job(check_ton_payments, "interval", seconds=60)
    scheduler.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
