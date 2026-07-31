from datetime import datetime, timedelta

STOP_WORDS = ("стоп", "не пишите", "неинтересно", "удалите", "отписаться", "stop", "unsubscribe")

def contains_stop_word(text: str | None) -> bool:
    return bool(text and any(word in text.casefold() for word in STOP_WORDS))

def eligible(client, now: datetime, inactive_days: int, repeat_after_days: int) -> bool:
    """Pure predicate; database query additionally guarantees a real dialogue."""
    last_contact = max((x for x in (client.last_incoming_at, client.last_outgoing_at) if x), default=None)
    if not last_contact or not client.last_incoming_at or not client.last_outgoing_at:
        return False
    return not any((client.excluded, client.paused, client.blocked, client.deleted,
                    client.replied_after_followup)) and last_contact <= now - timedelta(days=inactive_days) and (
        client.last_followup_at is None or client.last_followup_at <= now - timedelta(days=repeat_after_days)) and (
        client.last_incoming_at <= client.last_outgoing_at)
