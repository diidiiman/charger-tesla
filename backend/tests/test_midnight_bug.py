import zoneinfo
from datetime import datetime, timezone, timedelta
from app.schedule_calculator import ScheduleCalculator
from app.prices import RegionPrice

def test_midnight_bug():
    tz = zoneinfo.ZoneInfo("UTC")
    # Simulate now = 22:00
    now_local = datetime(2023, 10, 10, 22, 0, tzinfo=timezone.utc)
    
    # Block goes from 18:00 to 00:00 (next day)
    p1 = RegionPrice(
        region="NO1", 
        valid_from=datetime(2023, 10, 10, 18, 0, tzinfo=timezone.utc), 
        valid_to=datetime(2023, 10, 11, 0, 0, tzinfo=timezone.utc), 
        price=0.1
    )
    blocks = [[p1]]
    
    # manual sync, target_date = None
    windows = ScheduleCalculator.blocks_to_time_windows(blocks, tz, now_local, None)
    print(windows)

test_midnight_bug()
