import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone, date

from app.tesla_schedule_manager import TeslaScheduleManager
from app.models import User

@pytest.fixture
def manager():
    return TeslaScheduleManager("fake_token", "fake_vehicle_id")

@pytest.mark.asyncio
async def test_ensure_awake(manager):
    with patch("app.tesla_schedule_manager.tesla") as mock_tesla:
        mock_tesla.wake_up = AsyncMock()
        with patch("asyncio.sleep", AsyncMock()):
            await manager.ensure_awake()
            mock_tesla.wake_up.assert_called_once()
            assert manager.woke_up is True
            
            # Second call shouldn't wake up
            await manager.ensure_awake()
            mock_tesla.wake_up.assert_called_once()
            
            # Force call should wake up again
            await manager.ensure_awake(force=True)
            assert mock_tesla.wake_up.call_count == 2

def test_parse_schedules():
    assert TeslaScheduleManager.parse_schedules([]) == []
    assert TeslaScheduleManager.parse_schedules([{"id": 1}]) == [{"id": 1}]
    
    dict_sched = {"1": {"days_of_week": 12}, "2": {}}
    res = TeslaScheduleManager.parse_schedules(dict_sched)
    assert len(res) == 2
    assert {"id": 1, "days_of_week": 12} in res
    assert {"id": 2} in res

@pytest.mark.asyncio
async def test_fetch_schedules(manager):
    with patch("app.tesla_schedule_manager.tesla") as mock_tesla:
        mock_tesla.get_charge_schedules = AsyncMock(return_value=[{"id": 1}])
        schedules = await manager.fetch_schedules()
        assert schedules == [{"id": 1}]

@pytest.mark.asyncio
async def test_clear_all_schedules(manager):
    with patch("app.tesla_schedule_manager.tesla") as mock_tesla:
        manager.fetch_schedules = AsyncMock(return_value=[{"id": 1}])
        manager.ensure_awake = AsyncMock()
        mock_tesla.remove_charge_schedule = AsyncMock()
        
        await manager.clear_all_schedules()
        
        mock_tesla.remove_charge_schedule.assert_called_once_with("fake_token", "fake_vehicle_id", 1)

def test_calculate_schedule_changes():
    sched_list = [{"id": 1, "days_of_week": 12}] # 4 (Wed) + 8 (Thu)
    target_date = date(2023, 10, 11) # Wednesday, mask=4
    now_local = datetime(2023, 10, 10, 12, tzinfo=timezone.utc) # Tuesday, mask=2
    
    to_delete, to_update = TeslaScheduleManager.calculate_schedule_changes(
        sched_list, target_date, now_local, 59.0, 10.0
    )
    
    assert to_delete == []
    assert len(to_update) == 1
    assert to_update[0]["id"] == 1
    assert to_update[0]["days_of_week"] == 8 # Strip Wed

@pytest.mark.asyncio
async def test_execute_deletions(manager):
    with patch("app.tesla_schedule_manager.tesla") as mock_tesla:
        manager.ensure_awake = AsyncMock()
        mock_tesla.remove_charge_schedule = AsyncMock()
        
        await manager.execute_deletions([1])
        mock_tesla.remove_charge_schedule.assert_called_once_with("fake_token", "fake_vehicle_id", 1)

@pytest.mark.asyncio
async def test_execute_updates(manager):
    with patch("app.tesla_schedule_manager.tesla") as mock_tesla:
        manager.ensure_awake = AsyncMock()
        mock_tesla.add_charge_schedule = AsyncMock()
        
        updates = [{"id": 1, "days_of_week": 4, "start_time": 0, "end_time": 60, "lat": 1.0, "lon": 2.0}]
        await manager.execute_updates(updates)
        
        mock_tesla.add_charge_schedule.assert_called_once()
        kwargs = mock_tesla.add_charge_schedule.call_args[1]
        assert kwargs["days_of_week"] == "WED"
        assert kwargs["id"] == 1

@pytest.mark.asyncio
async def test_execute_additions(manager):
    with patch("app.tesla_schedule_manager.tesla") as mock_tesla:
        manager.ensure_awake = AsyncMock()
        mock_tesla.add_charge_schedule = AsyncMock()
        
        user = MagicMock(spec=User)
        user.home_latitude = 1.0
        user.home_longitude = 2.0
        user.push_token = None
        
        blocks = [{"start": 0, "end": 60, "day_str": "WED", "dt": datetime.now(), "end_dt": datetime.now()}]
        
        with patch("asyncio.sleep", AsyncMock()):
            await manager.execute_additions(blocks, [{"id": 1}], user, 0.5)
        
        mock_tesla.add_charge_schedule.assert_called_once()
        kwargs = mock_tesla.add_charge_schedule.call_args[1]
        assert kwargs["id"] == 2 # 1 is taken
        assert kwargs["days_of_week"] == "WED"
