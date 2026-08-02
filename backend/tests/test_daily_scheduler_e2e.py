import pytest
from datetime import datetime, timezone, timedelta, date
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
import zoneinfo

from app.models import User, TeslaAccount, Subscription
from app.scheduler import sync_charge_schedule
from app.prices import RegionPrice

@pytest.fixture
def mock_tesla():
    with patch("app.tesla_schedule_manager.tesla") as mock:
        mock.get_access_token = AsyncMock(return_value="fake_token")
        yield mock

def create_mock_user():
    user = MagicMock(spec=User)
    user.id = 1
    user.auto_charge_enabled = True
    user.region = "NO1"
    user.threshold_price = 0.5
    user.vat_included = False
    user.home_latitude = 59.0
    user.home_longitude = 10.0
    user.push_token = None
    user.price_change_reminder = False
    user.currency = "NOK"

    sub = MagicMock(spec=Subscription)
    sub.active = True
    user.subscription = sub

    tesla = MagicMock(spec=TeslaAccount)
    tesla.vehicle_id = "fake_vehicle_id"
    user.tesla = tesla

    return user

@pytest.mark.asyncio
async def test_daily_scheduler_flow():
    session = AsyncMock()
    user = create_mock_user()
    
    # Run at 13:00 UTC on a Tuesday
    now = datetime(2023, 10, 10, 13, 0, 0, tzinfo=timezone.utc) 
    target_date = date(2023, 10, 11) # Wednesday
    
    # Prices for tomorrow
    p1 = RegionPrice(region="NO1", valid_from=datetime(2023, 10, 11, 2, 0, tzinfo=timezone.utc), valid_to=datetime(2023, 10, 11, 3, 0, tzinfo=timezone.utc), price=0.1)
    
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [p1]
    session.execute.return_value = mock_result
    
    with patch("app.scheduler.tesla") as mock_tesla_scheduler:
        mock_tesla_scheduler.get_access_token = AsyncMock(return_value="token")
        
        with patch("app.tesla_schedule_manager.tesla") as mock_tesla:
            mock_tesla.get_charge_schedules = AsyncMock(return_value=[
                {"id": 1, "days_of_week": 4, "start_time": 60, "end_time": 120}, # Today (Tue)
                {"id": 2, "days_of_week": 8, "start_time": 0, "end_time": 60},   # Tomorrow old (Wed)
            ])
            mock_tesla.remove_charge_schedule = AsyncMock()
            mock_tesla.add_charge_schedule = AsyncMock()
            mock_tesla.wake_up = AsyncMock()

            with patch("asyncio.sleep", AsyncMock()):
                await sync_charge_schedule(session, user, now=now, target_date=target_date)

            # Assertions
            # We expect schedule 1 to be untouched (not deleted, not updated)
            # We expect schedule 2 to be deleted
            # We expect a new schedule for Wednesday to be added
            
            # Assert delete was called only for id=2
            mock_tesla.remove_charge_schedule.assert_called_once_with("token", "fake_vehicle_id", 2)
            
            # Assert add was called for Wednesday
            mock_tesla.add_charge_schedule.assert_called_once()
            kwargs = mock_tesla.add_charge_schedule.call_args[1]
            assert kwargs["days_of_week"] == "WED"
