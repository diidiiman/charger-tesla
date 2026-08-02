import pytest
import zoneinfo
from datetime import datetime, timezone, date

from app.prices import RegionPrice
from app.schedule_calculator import ScheduleCalculator

def test_get_cheap_prices():
    prices = [
        RegionPrice(price=0.5),
        RegionPrice(price=0.2),
        RegionPrice(price=0.8),
    ]
    cheap = ScheduleCalculator.get_cheap_prices(prices, threshold=0.6, multiplier=1.0)
    assert len(cheap) == 2
    assert cheap[0].price == 0.5
    assert cheap[1].price == 0.2

    cheap = ScheduleCalculator.get_cheap_prices(prices, threshold=0.6, multiplier=1.2) # threshold 0.6, 0.5*1.2=0.6, 0.2*1.2=0.24, 0.8*1.2=0.96
    assert len(cheap) == 2
    
def test_group_into_blocks():
    tz = zoneinfo.ZoneInfo("UTC")
    p1 = RegionPrice(valid_from=datetime(2023, 1, 1, 10, tzinfo=timezone.utc), valid_to=datetime(2023, 1, 1, 11, tzinfo=timezone.utc))
    p2 = RegionPrice(valid_from=datetime(2023, 1, 1, 11, tzinfo=timezone.utc), valid_to=datetime(2023, 1, 1, 12, tzinfo=timezone.utc))
    p3 = RegionPrice(valid_from=datetime(2023, 1, 1, 14, tzinfo=timezone.utc), valid_to=datetime(2023, 1, 1, 15, tzinfo=timezone.utc))
    
    blocks = ScheduleCalculator.group_into_blocks([p1, p2, p3], tz)
    assert len(blocks) == 2
    assert len(blocks[0]) == 2
    assert len(blocks[1]) == 1

def test_blocks_to_time_windows():
    tz = zoneinfo.ZoneInfo("UTC")
    now = datetime(2023, 1, 1, 8, tzinfo=timezone.utc)
    target_date = date(2023, 1, 1) # Sunday, mask=64
    
    p1 = RegionPrice(valid_from=datetime(2023, 1, 1, 10, tzinfo=timezone.utc), valid_to=datetime(2023, 1, 1, 12, tzinfo=timezone.utc))
    blocks = [[p1]]
    
    windows = ScheduleCalculator.blocks_to_time_windows(blocks, tz, now, target_date)
    assert len(windows) == 1
    assert windows[0]["start"] == 10 * 60
    assert windows[0]["end"] == 12 * 60
    assert windows[0]["mask"] == 1
    assert windows[0]["day_str"] == "SUN"
