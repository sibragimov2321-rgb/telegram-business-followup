from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import BusinessConnection, Client, FollowupQueue, QueueStatus
from .filters import contains_stop_word

async def cancel_client_queue(session: AsyncSession, client_id: int) -> None:
    await session.execute(update(FollowupQueue).where(FollowupQueue.client_id == client_id, FollowupQueue.status.in_([QueueStatus.pending, QueueStatus.paused])).values(status=QueueStatus.cancelled))

async def save_business_message(session: AsyncSession, message, connection_id: str) -> Client | None:
    # Business messages are only accepted from private chats, which protects group/channel users.
    if message.chat.type != "private": return None
    sender = message.from_user
    result = await session.execute(select(Client).where(Client.chat_id == message.chat.id))
    client = result.scalar_one_or_none()
    if client is None:
        client = Client(chat_id=message.chat.id, telegram_user_id=sender.id if sender else None,
            username=sender.username if sender else None, first_name=sender.first_name if sender else None,
            language=(sender.language_code if sender else "ru"), business_connection_id=connection_id)
        session.add(client)
    else:
        client.business_connection_id = connection_id
        if sender:
            client.telegram_user_id, client.username, client.first_name = sender.id, sender.username, sender.first_name
    client.last_message_text = message.text or message.caption
    date = message.date if message.date.tzinfo else message.date.replace(tzinfo=timezone.utc)
    connection = await session.get(BusinessConnection, connection_id)
    is_outgoing = bool(sender and connection and sender.id == connection.business_user_id)
    if is_outgoing:
        client.last_outgoing_at = date
    else:
        client.last_incoming_at = date
        if contains_stop_word(client.last_message_text):
            client.excluded, client.status = True, "excluded"
            await session.flush(); await cancel_client_queue(session, client.id)
        elif client.last_followup_at:
            client.replied_after_followup, client.status = True, "replied"
            await session.flush(); await cancel_client_queue(session, client.id)
    return client
