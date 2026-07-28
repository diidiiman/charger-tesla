import pytest
from datetime import datetime, timezone, date
from unittest.mock import AsyncMock, patch, MagicMock

from app.tesla_schedule_manager import TeslaScheduleManager

def test_daily_scheduler_keeps_today_adds_tomorrow():
    now_local = datetime(2023, 10, 10, 13, 0, tzinfo=timezone.utc) # Tuesday (mask=2)
    target_date = date(2023, 10, 11) # Wednesday (mask=4)
    
    sched_list = [
        {"id": 1, "days_of_week": 2, "start_time": 60, "end_time": 120}, # Today's schedule
        {"id": 2, "days_of_week": 4, "start_time": 0, "end_time": 60},   # Some old tomorrow's schedule that should be wiped
    ]
    
    to_delete, to_update = TeslaScheduleManager.calculate_schedule_changes(
        sched_list, target_date, now_local, 0.0, 0.0
    )
    
    # We expect schedule 1 to NOT be deleted and NOT be updated. It should be kept intact.
    # We expect schedule 2 to be updated to mask=0, hence deleted.
    
    assert 1 not in to_delete
    assert 1 not in [u["id"] for u in to_update]
    
    assert 2 in to_delete

