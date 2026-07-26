import pytest
import asyncio
from datetime import datetime, timezone, timedelta, date
from unittest.mock import AsyncMock, patch, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, TeslaAccount, Subscription
from app.scheduler import (
    sync_charge_schedule,
    _sync_all_users,
    REGION_TIMEZONES,
    fetch_daily_prices_forever,
    verify_expired_subscriptions_forever
)
from app.prices import RegionPrice

@pytest.fixture
def mock_tesla():
    with patch("app.scheduler.tesla") as mock:
        mock.get_access_token = AsyncMock(return_value="fake_token")
        yield mock

@pytest.fixture
def mock_prices():
    with patch("app.scheduler.prices") as mock:
        mock.get_vat_multiplier.return_value = 1.0
        mock.fetch_and_store_prices = AsyncMock()
        mock.RegionPrice = RegionPrice
        yield mock

def create_mock_user(auto_charge=True, is_pro=True, has_tesla=True):
    user = MagicMock(spec=User)
    user.id = 1
    user.auto_charge_enabled = auto_charge
    user.region = "NO1"
    user.threshold_price = 0.5
    user.vat_included = False
    user.home_latitude = 59.0
    user.home_longitude = 10.0
    user.push_token = "fake_push_token"
    user.price_change_reminder = True
    user.currency = "NOK"

    sub = MagicMock(spec=Subscription)
    sub.active = is_pro
    user.subscription = sub if is_pro else None

    tesla = MagicMock(spec=TeslaAccount)
    tesla.vehicle_id = "fake_vehicle_id"
    user.tesla = tesla if has_tesla else None

    return user

@pytest.mark.asyncio
async def test_sync_no_tesla(mock_tesla):
    session = AsyncMock()
    user = create_mock_user(has_tesla=False)
    await sync_charge_schedule(session, user)
    mock_tesla.get_access_token.assert_not_called()

@pytest.mark.asyncio
async def test_sync_token_failure(mock_tesla):
    session = AsyncMock()
    user = create_mock_user()
    mock_tesla.get_access_token.side_effect = Exception("Auth error")
    with patch("app.scheduler.TeslaScheduleManager") as MockManager:
        await sync_charge_schedule(session, user)
        MockManager.assert_not_called()

@pytest.mark.asyncio
async def test_sync_no_auto_charge(mock_tesla):
    session = AsyncMock()
    user = create_mock_user(auto_charge=False)
    
    with patch("app.scheduler.TeslaScheduleManager") as MockManager:
        mock_instance = MockManager.return_value
        mock_instance.clear_all_schedules = AsyncMock()
        
        await sync_charge_schedule(session, user)
        
        mock_instance.clear_all_schedules.assert_called_once()

@pytest.mark.asyncio
async def test_sync_create_schedules(mock_tesla, mock_prices):
    session = AsyncMock()
    user = create_mock_user()
    
    now = datetime(2023, 10, 10, 12, 0, 0, tzinfo=timezone.utc) # Tuesday
    
    p1 = RegionPrice(region="NO1", valid_from=datetime(2023, 10, 10, 22, 0, tzinfo=timezone.utc), valid_to=datetime(2023, 10, 10, 23, 0, tzinfo=timezone.utc), price=0.1)
    
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [p1]
    session.execute.return_value = mock_result
    
    with patch("app.scheduler.TeslaScheduleManager") as MockManager:
        MockManager.calculate_schedule_changes.return_value = ([], [])
        mock_instance = MockManager.return_value
        mock_instance.fetch_schedules = AsyncMock(return_value=[])
        mock_instance.execute_deletions = AsyncMock()
        mock_instance.execute_updates = AsyncMock()
        mock_instance.execute_additions = AsyncMock()
        
        await sync_charge_schedule(session, user, now=now)
        
        mock_instance.fetch_schedules.assert_called_once()
        mock_instance.execute_additions.assert_called_once()
        # Assert desired blocks calculated properly and passed down
        args = mock_instance.execute_additions.call_args[0]
        assert len(args[0]) == 1 # 1 block
        assert args[0][0]["day_str"] == "WED"

@pytest.mark.asyncio
async def test_sync_all_users():
    session = AsyncMock()
    user = create_mock_user()
    mock_result = MagicMock()
    mock_result.scalars().unique().all.return_value = [user]
    session.execute.return_value = mock_result
    
    with patch("app.scheduler.sync_charge_schedule") as mock_sync:
        await _sync_all_users(session, date(2023, 10, 11))
        mock_sync.assert_called_once()
        assert mock_sync.call_args[0][1] == user

@pytest.mark.asyncio
async def test_verify_expired_subscriptions():
    with patch("app.scheduler.SessionLocal") as mock_session_local:
        with patch("app.subscriptions.verify_receipt") as mock_verify:
            session = AsyncMock()
            mock_session_local.return_value.__aenter__.return_value = session
            
            sub = MagicMock()
            sub.user_id = 1
            sub.platform = "apple"
            sub.receipt = "fake"
            
            user = MagicMock()
            sub.user = user
            
            mock_result = MagicMock()
            mock_result.scalars().all.return_value = [sub]
            session.execute.return_value = mock_result
            
            mock_verify.return_value = {"active": False, "expires_at": datetime.now()}
            
            with patch("app.scheduler.datetime") as mock_dt:
                mock_dt.now.return_value = datetime(2023, 10, 10, 2, 0, 0, tzinfo=timezone.utc)
                mock_dt.timezone = timezone
                
                with patch("asyncio.sleep", side_effect=[None, Exception("Stop loop")]):
                    try:
                        await verify_expired_subscriptions_forever()
                    except Exception as e:
                        if str(e) != "Stop loop":
                            raise
            
            assert sub.active is False
            assert user.auto_charge_enabled is False

@pytest.mark.asyncio
async def test_fetch_daily_prices():
    with patch("app.scheduler.SessionLocal") as mock_session_local:
        with patch("app.scheduler.prices.fetch_and_store_prices") as mock_fetch:
            with patch("app.scheduler._sync_all_users") as mock_sync:
                session = AsyncMock()
                mock_session_local.return_value.__aenter__.return_value = session
                
                with patch("app.scheduler.datetime") as mock_dt:
                    mock_dt.now.return_value = datetime(2023, 10, 10, 13, 0, 0, tzinfo=timezone.utc)
                    mock_dt.timezone = timezone
                    mock_dt.combine = datetime.combine
                    mock_dt.min = datetime.min
                    mock_dt.max = datetime.max
                    
                    with patch("asyncio.sleep", side_effect=[Exception("Stop loop")]):
                        try:
                            await fetch_daily_prices_forever()
                        except Exception as e:
                            if str(e) != "Stop loop":
                                raise
                
                mock_fetch.assert_called_once()
                mock_sync.assert_called_once()
