import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import BotCommand, BusinessConnection, MenuButtonCommands, Message, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import async_sessionmaker
from .config import get_settings
from .database import SessionLocal
from .handlers.admin import admin_router
from .models import BusinessConnection as BusinessConnectionModel
from .services.business import save_business_message
from .services.scheduler import build_daily_queue, dispatch_due
from .webapp import router as webapp_router

settings=get_settings()
WEBAPP_URL = settings.webapp_url.rstrip("/")
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

def public_router() -> Router:
    router = Router(name="public")
    @router.message(Command("start"))
    async def public_start(message: Message):
        if not WEBAPP_URL:
            await message.answer("Приложение временно не настроено.")
            return
        await message.answer(
            "🚀 Откройте Partners Portal",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 Открыть приложение", web_app=WebAppInfo(url=WEBAPP_URL))]]),
        )
    return router

@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot
    if not settings.bot_token: raise RuntimeError("BOT_TOKEN is required")
    bot=Bot(settings.bot_token)
    await bot.set_my_commands([
        BotCommand(command="start", description="Панель управления"),
        BotCommand(command="status", description="Статус автоматизации"),
        BotCommand(command="today", description="Результаты за сегодня"),
        BotCommand(command="queue", description="Очередь follow-up"),
        BotCommand(command="clients", description="Количество клиентов"),
        BotCommand(command="stats", description="Статистика отправок"),
        BotCommand(command="scripts", description="Активные скрипты"),
    ])
    for admin_id in settings.admins:
        try:
            await bot.set_chat_menu_button(chat_id=admin_id, menu_button=MenuButtonCommands())
        except Exception:
            pass
    dp=Dispatcher()
    dp.include_router(admin_router(SessionLocal, settings)); dp.include_router(public_router()); dp.include_router(business_router(SessionLocal))
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
if (Path(__file__).parent / "web").exists():
    app.mount("/miniapp", StaticFiles(directory=Path(__file__).parent / "web", html=True), name="miniapp")
app.include_router(webapp_router)
@app.get("/health")
async def health(): return {"ok": True, "automation_enabled": settings.automation_enabled}
