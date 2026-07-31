from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from app.services.filters import contains_stop_word, eligible

def client(**kwargs):
    values=dict(last_incoming_at=datetime.now(timezone.utc)-timedelta(days=10),last_outgoing_at=datetime.now(timezone.utc)-timedelta(days=8),last_followup_at=None,excluded=False,paused=False,blocked=False,deleted=False,replied_after_followup=False)
    values.update(kwargs); return SimpleNamespace(**values)

def test_stop_words_case_insensitive():
    assert contains_stop_word("Пожалуйста, НЕ ПИШИТЕ мне")
    assert contains_stop_word("unsubscribe me")
    assert not contains_stop_word("Спасибо, интересно")

def test_eligibility_requires_inbound_and_no_reply_after_outbound():
    now=datetime.now(timezone.utc)
    assert eligible(client(),now,7,30)
    assert not eligible(client(last_incoming_at=now-timedelta(days=1)),now,7,30)
    assert not eligible(client(excluded=True),now,7,30)
    assert not eligible(client(last_followup_at=now-timedelta(days=3)),now,7,30)
