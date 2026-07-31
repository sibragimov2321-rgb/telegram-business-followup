import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo
from aiogram import Bot, Dispatcher, Router
from aiogram.types import BusinessConnection, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker
from .config import get_settings
from .database import SessionLocal
from .handlers.admin import admin_router
from .models import BusinessConnection as BusinessConnectionModel
from .services.business import save_business_message
from .services.scheduler import build_daily_queue, dispatch_due

settings=get_settings()
bot: Bot | None = None
scheduler=AsyncIOScheduler(timezone=settings.timezone)

def business_router(session_factory: async_sessionmaker) -> Router:
    router=Router(name="business")
    @router.business_connection()
    async def connection(update: BusinessConnection):
        async with session_factory() as s:
            row=await s.get(BusinessConnectionModel, update.id)
            if row is None: row=BusinessConnectionModel(id=update.id, business_user_id=update.user.id, is_enabled=update.is_enabled); s.add(row)
            else: row.business_user_id, row.is_enabled=update.user.id, update.is_enabled
            await s.commit()
    @router.business_message()
    async def message_handler(message: Message):
        if not message.business_connection_id: return
        async with session_factory() as s:
            client=await save_business_message(s,message,message.business_connection_id)
            event = client.status if client else None
            await s.commit()
        if event in {"replied","excluded"}:
            for admin_id in settings.admins:
                try: await bot.send_message(admin_id, f"Клиент {client.telegram_user_id or client.chat_id}: {event}. Очередь отменена.")
                except Exception: pass
    return router

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot
    if not settings.bot_token: raise RuntimeError("BOT_TOKEN is required")
    bot=Bot(settings.bot_token)
    dp=Dispatcher()
    dp.include_router(admin_router(SessionLocal, settings)); dp.include_router(business_router(SessionLocal))
    scheduler.add_job(build_daily_queue, "cron", hour=10, minute=0, args=[SessionLocal, settings], id="daily_queue", replace_existing=True)
    scheduler.add_job(dispatch_due, "interval", minutes=1, args=[SessionLocal, bot, settings], id="dispatcher", replace_existing=True)
    scheduler.start()
    poller=asyncio.create_task(dp.start_polling(bot, allowed_updates=["business_connection", "business_message", "message"]))
    try: yield
    finally:
        scheduler.shutdown(wait=False); poller.cancel()
        try: await poller
        except asyncio.CancelledError: pass
        await bot.session.close()

app=FastAPI(title="Telegram Business Follow-up", lifespan=lifespan)
@app.get("/health")
async def health(): return {"ok": True, "automation_enabled": settings.automation_enabled}
