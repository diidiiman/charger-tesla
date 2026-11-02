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

        mock_tesla.remove_charge_schedule.assert_called_once_with(
            "fake_token", "fake_vehicle_id", 1
        )


def test_remove_today_window_deletes_single_day_placeholder():
    sched_list = [
        {"id": 5, "days_of_week": 4, "start_time": 18 * 60, "end_time": 19 * 60}
    ]
    to_delete = []
    to_update = []

    TeslaScheduleManager.remove_today_window(
        sched_list, to_delete, to_update, 4, 18 * 60, 19 * 60, 59.0, 10.0
    )

    assert to_delete == [5]
    assert to_update == []


def test_remove_today_window_strips_today_from_shared_schedule():
    sched_list = [
        {
            "id": 5,
            "days_of_week": 36,  # Tuesday (4) + Friday (32)
            "start_time": 18 * 60,
            "end_time": 19 * 60,
            "latitude": 1.0,
            "longitude": 2.0,
        }
    ]
    to_delete = []
    to_update = []

    TeslaScheduleManager.remove_today_window(
        sched_list, to_delete, to_update, 4, 18 * 60, 19 * 60, 59.0, 10.0
    )

    assert to_delete == []
    assert len(to_update) == 1
    assert to_update[0]["id"] == 5
    assert to_update[0]["days_of_week"] == 32
    assert to_update[0]["lat"] == 1.0
    assert to_update[0]["lon"] == 2.0


def test_remove_today_window_deletes_when_remaining_mask_is_today():
    sched_list = [
        {"id": 5, "days_of_week": 12, "start_time": 18 * 60, "end_time": 19 * 60}
    ]
    to_delete = []
    to_update = [
        {
            "id": 5,
            "days_of_week": 4,
            "start_time": 18 * 60,
            "end_time": 19 * 60,
            "lat": 59.0,
            "lon": 10.0,
        }
    ]

    TeslaScheduleManager.remove_today_window(
        sched_list, to_delete, to_update, 4, 18 * 60, 19 * 60, 59.0, 10.0
    )

    assert to_delete == [5]
    assert to_update == []


def test_calculate_schedule_changes():
    sched_list = [{"id": 1, "days_of_week": 24}]  # 8 (Wed) + 16 (Thu)
    target_date = date(2023, 10, 11)  # Wednesday, mask=8
    now_local = datetime(2023, 10, 10, 12, tzinfo=timezone.utc)  # Tuesday, mask=4

    to_delete, to_update = TeslaScheduleManager.calculate_schedule_changes(
        sched_list, target_date, now_local, 59.0, 10.0
    )

    assert to_delete == []
    assert len(to_update) == 1
    assert to_update[0]["id"] == 1
    assert to_update[0]["days_of_week"] == 16  # Strip Wed


@pytest.mark.asyncio
async def test_execute_deletions(manager):
    with patch("app.tesla_schedule_manager.tesla") as mock_tesla:
        manager.ensure_awake = AsyncMock()
        mock_tesla.remove_charge_schedule = AsyncMock()

        await manager.execute_deletions([1])
        mock_tesla.remove_charge_schedule.assert_called_once_with(
            "fake_token", "fake_vehicle_id", 1
        )


@pytest.mark.asyncio
async def test_execute_updates(manager):
    with patch("app.tesla_schedule_manager.tesla") as mock_tesla:
        manager.ensure_awake = AsyncMock()
        mock_tesla.add_charge_schedule = AsyncMock()

        updates = [
            {
                "id": 1,
                "days_of_week": 8,
                "start_time": 0,
                "end_time": 60,
                "lat": 1.0,
                "lon": 2.0,
            }
        ]
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

        blocks = [
            {
                "start": 0,
                "end": 60,
                "day_str": "WED",
                "dt": datetime.now(),
                "end_dt": datetime.now(),
            }
        ]

        with patch("asyncio.sleep", AsyncMock()):
            with patch("time.time", return_value=1700000000.0):
                await manager.execute_additions(blocks, [{"id": 1}], user, 0.5)

        mock_tesla.add_charge_schedule.assert_called_once()
        kwargs = mock_tesla.add_charge_schedule.call_args[1]
        assert kwargs["id"] == 1700000000  # 1700000000 + 0
        assert kwargs["days_of_week"] == "WED"


def test_has_surviving_schedule_for_day_kept_today():
    sched_list = [{"id": 1, "days_of_week": 4}]  # Tuesday
    assert (
        TeslaScheduleManager.has_surviving_schedule_for_day(sched_list, [], [], 4)
        is True
    )


def test_has_surviving_schedule_for_day_deleted_yesterday():
    sched_list = [{"id": 1, "days_of_week": 2}]  # Monday
    assert (
        TeslaScheduleManager.has_surviving_schedule_for_day(sched_list, [1], [], 4)
        is False
    )


def test_has_surviving_schedule_for_day_updated_keeps_today():
    sched_list = [{"id": 1, "days_of_week": 12}]  # Tue (4) + Wed (8)
    updates = [{"id": 1, "days_of_week": 4}]
    assert (
        TeslaScheduleManager.has_surviving_schedule_for_day(sched_list, [], updates, 4)
        is True
    )
    assert (
        TeslaScheduleManager.has_surviving_schedule_for_day(sched_list, [], updates, 8)
        is False
    )


@pytest.mark.asyncio
async def test_execute_additions_skips_push_for_placeholder(manager):
    with patch("app.tesla_schedule_manager.tesla") as mock_tesla:
        with patch("app.tesla_schedule_manager.send_push_notification") as mock_push:
            manager.ensure_awake = AsyncMock()
            mock_tesla.add_charge_schedule = AsyncMock()
            mock_push.return_value = None

            user = MagicMock(spec=User)
            user.home_latitude = 1.0
            user.home_longitude = 2.0
            user.push_token = "token"
            user.price_change_reminder = True
            user.currency = "EUR"

            blocks = [
                {
                    "start": 180,
                    "end": 240,
                    "day_str": "TUES",
                    "dt": datetime.now(),
                    "end_dt": datetime.now(),
                    "placeholder": True,
                }
            ]

            with patch("asyncio.sleep", AsyncMock()):
                with patch("time.time", return_value=1700000000.0):
                    await manager.execute_additions(blocks, [], user, 0.5)

            mock_tesla.add_charge_schedule.assert_called_once()
            mock_push.assert_not_called()
