import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramBadRequest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from ..config import Settings
from ..models import BusinessConnection, Client, FollowupQueue, QueueStatus, Script, SendLog
from .business import cancel_client_queue
from .filters import eligible

def schedule_times(now: datetime, count: int, settings: Settings) -> list[datetime]:
    tz = ZoneInfo(settings.timezone); base = now.astimezone(tz).replace(hour=settings.send_start_hour, minute=0, second=0, microsecond=0)
    times=[]
    for _ in range(count):
        base += timedelta(minutes=random.randint(settings.min_delay_minutes, settings.max_delay_minutes))
        if base.hour >= settings.send_end_hour: break
        times.append(base)
    return times

async def build_daily_queue(session: AsyncSession, settings: Settings, now: datetime | None = None) -> int:
    now = now or datetime.now(ZoneInfo(settings.timezone)); today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    already = (await session.scalar(select(func.count()).select_from(FollowupQueue).where(FollowupQueue.run_date == today))) or 0
    slots = max(0, settings.daily_limit - already)
    if not settings.automation_enabled or not slots: return 0
    enabled_ids=set((await session.scalars(select(BusinessConnection.id).where(BusinessConnection.is_enabled.is_(True)))).all())
    clients = (await session.scalars(select(Client).where(Client.excluded.is_(False), Client.paused.is_(False), Client.blocked.is_(False), Client.deleted.is_(False), Client.business_connection_id.in_(enabled_ids)))).all()
    candidates = [c for c in clients if eligible(c, now, settings.inactive_days, settings.repeat_after_days)]
    random.shuffle(candidates)
    wanted = min(slots, len(candidates), random.randint(min(settings.daily_min, settings.daily_limit), settings.daily_limit))
    times = schedule_times(now, wanted, settings)
    for client, scheduled_at in zip(candidates[:len(times)], times):
        scripts=(await session.scalars(select(Script).where(Script.active.is_(True), Script.language == (client.language or "ru"), Script.category.in_([client.category or "general", "general"])))).all()
        if scripts: session.add(FollowupQueue(client_id=client.id, script_id=random.choice(scripts).id, run_date=today, scheduled_at=scheduled_at))
    await session.commit(); return len(times)

async def dispatch_due(session_factory: async_sessionmaker[AsyncSession], bot: Bot, settings: Settings) -> None:
    if not settings.automation_enabled: return
    now=datetime.now(ZoneInfo(settings.timezone))
    if not settings.send_start_hour <= now.hour < settings.send_end_hour: return
    async with session_factory() as session:
        rows=(await session.execute(select(FollowupQueue, Client, Script).join(Client, Client.id==FollowupQueue.client_id).join(Script, Script.id==FollowupQueue.script_id).where(FollowupQueue.status==QueueStatus.pending, FollowupQueue.scheduled_at<=now).order_by(FollowupQueue.scheduled_at).limit(1))).all()
        if not rows: return
        q,c,s=rows[0]
        connection=await session.get(BusinessConnection, c.business_connection_id)
        if not connection or not connection.is_enabled or not eligible(c, now, settings.inactive_days, settings.repeat_after_days):
            q.status=QueueStatus.cancelled; await session.commit(); return
        try:
            await bot.send_message(c.chat_id, s.text, business_connection_id=c.business_connection_id)
            q.status=QueueStatus.sent; c.last_outgoing_at=now; c.last_followup_at=now; c.used_script_id=s.id; c.sends_count+=1
            session.add(SendLog(client_id=c.id, chat_id=c.chat_id, script_id=s.id, status="sent", business_connection_id=c.business_connection_id))
        except TelegramRetryAfter as e:
            error=f"Flood control: retry after {e.retry_after}"
            await session.execute(update(FollowupQueue).where(FollowupQueue.status==QueueStatus.pending).values(status=QueueStatus.paused, error=error))
            q.status=QueueStatus.paused; q.error=error; q.scheduled_at=now+timedelta(seconds=e.retry_after)
            for admin_id in settings.admins:
                try: await bot.send_message(admin_id, f"Flood control: автоматическая очередь поставлена на паузу на {e.retry_after} сек.")
                except Exception: pass
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            q.status=QueueStatus.failed; q.error=str(e); c.blocked=True
            await cancel_client_queue(session, c.id)
            session.add(SendLog(client_id=c.id, chat_id=c.chat_id, script_id=s.id, status="failed", error=str(e), business_connection_id=c.business_connection_id))
        await session.commit()
