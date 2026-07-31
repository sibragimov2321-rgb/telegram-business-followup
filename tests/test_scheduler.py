from datetime import datetime
from zoneinfo import ZoneInfo
from app.config import Settings
from app.services.scheduler import schedule_times

def test_schedule_times_are_sequential_and_in_window():
    settings=Settings(send_start_hour=10,send_end_hour=19,min_delay_minutes=20,max_delay_minutes=20)
    times=schedule_times(datetime(2026,1,1,10,tzinfo=ZoneInfo("Europe/Moscow")),3,settings)
    assert len(times)==3
    assert [x.minute for x in times]==[20,40,0]
    assert all(10 <= x.hour < 19 for x in times)
