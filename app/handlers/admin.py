from datetime import datetime, timedelta, timezone
from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker
from ..config import Settings
from ..models import Client, FollowupQueue, QueueStatus, Script, SendLog
from ..services.business import cancel_client_queue

def admin_router(session_factory: async_sessionmaker, settings: Settings) -> Router:
    router=Router(name="admin")
    def allowed(m: Message): return bool(m.from_user and m.from_user.id in settings.admins)
    async def reply(m: Message, text: str):
        if allowed(m): await m.answer(text)
    @router.message(Command("status"))
    async def status(m: Message): await reply(m, f"automation={settings.automation_enabled}; limit={settings.daily_limit}; inactive={settings.inactive_days}d")
    @router.message(Command("today"))
    async def today(m: Message):
        async with session_factory() as s:
            n=await s.scalar(select(func.count()).select_from(FollowupQueue).where(FollowupQueue.status==QueueStatus.sent))
        await reply(m, f"Отправлено: {n or 0}")
    @router.message(Command("queue"))
    async def queue(m: Message):
        async with session_factory() as s:
            rows=(await s.scalars(select(FollowupQueue).where(FollowupQueue.status.in_([QueueStatus.pending,QueueStatus.paused])).limit(30))).all()
        await reply(m, "Очередь: " + (", ".join(f"#{x.id} {x.status} {x.scheduled_at:%H:%M}" for x in rows) or "пуста"))
    @router.message(Command("clients"))
    async def clients(m: Message): await reply(m, f"Клиентов: {await _client_count(session_factory)}")
    @router.message(Command("inactive"))
    async def inactive(m: Message, command: CommandObject):
        days=int(command.args or "7"); cutoff=datetime.now(timezone.utc)-timedelta(days=days)
        async with session_factory() as s: n=await s.scalar(select(func.count()).select_from(Client).where(Client.last_incoming_at < cutoff))
        await reply(m, f"Неактивны более {days} дней: {n or 0}")
    @router.message(Command(commands=["exclude","include","pause","resume"]))
    async def client_action(m: Message, command: CommandObject):
        if not allowed(m): return
        try: uid=int(command.args or "")
        except ValueError: await m.answer("Укажите USER_ID"); return
        field={"exclude":"excluded","include":"excluded","pause":"paused","resume":"paused"}[command.command]
        value=command.command in {"exclude","pause"}
        async with session_factory() as s:
            c=await s.scalar(select(Client).where(Client.telegram_user_id==uid))
            if not c: await m.answer("Клиент не найден"); return
            setattr(c,field,value)
            if value: await s.flush(); await cancel_client_queue(s,c.id)
            await s.commit()
        await m.answer("Готово")
    @router.message(Command(commands=["pause_all","resume_all","stop_all"]))
    async def all_action(m: Message, command: CommandObject):
        if not allowed(m): return
        async with session_factory() as s:
            if command.command=="pause_all": await s.execute(update(Client).values(paused=True)); await s.execute(update(FollowupQueue).where(FollowupQueue.status==QueueStatus.pending).values(status=QueueStatus.paused))
            elif command.command=="resume_all": await s.execute(update(Client).values(paused=False)); await s.execute(update(FollowupQueue).where(FollowupQueue.status==QueueStatus.paused).values(status=QueueStatus.pending))
            else: await s.execute(update(FollowupQueue).where(FollowupQueue.status.in_([QueueStatus.pending,QueueStatus.paused])).values(status=QueueStatus.cancelled))
            await s.commit()
        await m.answer("Готово")
    @router.message(Command("stats"))
    async def stats(m: Message): await reply(m, f"Успешных: {await _log_count(session_factory, 'sent')}; исключено: {await _client_count(session_factory, Client.excluded.is_(True))}")
    @router.message(Command("scripts"))
    async def scripts(m: Message):
        async with session_factory() as s: rows=(await s.scalars(select(Script).where(Script.active.is_(True)))).all()
        await reply(m, "\n".join(f"{x.id}: {x.title} [{x.language}/{x.category}]" for x in rows) or "Нет активных скриптов")
    @router.message(Command(commands=["set_limit","set_days"]))
    async def change_setting(m: Message, command: CommandObject):
        if not allowed(m): return
        try: value=int(command.args or "")
        except ValueError: await m.answer("Укажите целое число"); return
        if command.command=="set_limit": settings.daily_limit=max(1,value)
        else: settings.repeat_after_days=max(1,value)
        await m.answer("Настройка применена до перезапуска. Для постоянного значения измените Railway variable.")
    return router

async def _client_count(factory, clause=None):
    async with factory() as s:
        q=select(func.count()).select_from(Client)
        if clause is not None: q=q.where(clause)
        return await s.scalar(q) or 0

async def _log_count(factory, status):
    async with factory() as s:
        return await s.scalar(select(func.count()).select_from(SendLog).where(SendLog.status==status)) or 0
