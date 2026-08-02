import asyncio
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

from . import tesla
from .models import User
from .notifications import send_push_notification

log = logging.getLogger(__name__)

TESLA_MASKS = [2, 4, 8, 16, 32, 64, 1]  # MON, TUE, WED, THU, FRI, SAT, SUN
DAYS_MAP_STR = ["MON", "TUES", "WED", "THURS", "FRI", "SAT", "SUN"]

class TeslaScheduleManager:
    def __init__(self, token: str, vehicle_id: str):
        self.token = token
        self.vehicle_id = vehicle_id
        self.woke_up = False

    async def ensure_awake(self, force: bool = False) -> None:
        if not self.woke_up or force:
            try:
                await tesla.wake_up(self.token, self.vehicle_id)
                await asyncio.sleep(5)
                self.woke_up = True
            except Exception:
                pass

    @staticmethod
    def parse_schedules(raw_schedules: Any) -> List[Dict[str, Any]]:
        if isinstance(raw_schedules, list):
            return raw_schedules
        elif isinstance(raw_schedules, dict):
            sched_list = []
            for k, v in raw_schedules.items():
                if isinstance(v, dict):
                    v["id"] = int(k)
                    sched_list.append(v)
                else:
                    sched_list.append({"id": int(k)})
            return sched_list
        return []

    async def fetch_schedules(self, retries: int = 4) -> List[Dict[str, Any]]:
        for _ in range(retries):
            try:
                schedules = await tesla.get_charge_schedules(self.token, self.vehicle_id)
                return self.parse_schedules(schedules)
            except ValueError:
                await self.ensure_awake(force=True)
        raise ValueError("Vehicle remained asleep after wake attempts")

    async def clear_all_schedules(self) -> None:
        try:
            schedules = await self.fetch_schedules(retries=2)
            if not schedules:
                return
            await self.ensure_awake()
            for sched in schedules:
                if "id" in sched:
                    await tesla.remove_charge_schedule(self.token, self.vehicle_id, int(sched["id"]))
        except Exception as e:
            log.warning("failed to clear all schedules for vehicle %s: %s", self.vehicle_id, e)

    @staticmethod
    def calculate_schedule_changes(
        sched_list: List[Dict[str, Any]], 
        target_date: Optional[datetime.date],
        now_local: datetime,
        user_lat: float,
        user_lon: float
    ) -> Tuple[List[int], List[Dict[str, Any]]]:
        schedules_to_delete = []
        schedules_to_update = []
        
        target_mask = TESLA_MASKS[target_date.weekday()] if target_date else 0
        today_mask = TESLA_MASKS[now_local.weekday()]
        
        for sched in sched_list:
            if "id" not in sched:
                continue
            sched_id = int(sched["id"])
            raw_days = sched.get("days_of_week", 0)
            
            mask = 0
            if isinstance(raw_days, int):
                mask = raw_days
            elif isinstance(raw_days, str):
                try:
                    mask = int(raw_days)
                except ValueError:
                    for idx, d_str in enumerate(DAYS_MAP_STR):
                        if d_str in str(raw_days).upper():
                            mask |= TESLA_MASKS[idx]

            has_target = (mask & target_mask) != 0
            has_today = (mask & today_mask) != 0
            
            if target_date is not None:
                new_mask = mask
                if has_target:
                    new_mask = mask & ~target_mask
                
                if not has_today and not has_target:
                    new_mask = 0

                if new_mask == 0:
                    schedules_to_delete.append(sched_id)
                elif new_mask != mask:
                    schedules_to_update.append({
                        "id": sched_id,
                        "days_of_week": new_mask,
                        "start_time": sched.get("start_time"),
                        "end_time": sched.get("end_time"),
                        "lat": sched.get("latitude") or user_lat,
                        "lon": sched.get("longitude") or user_lon
                    })
            else:
                schedules_to_delete.append(sched_id)
                
        return schedules_to_delete, schedules_to_update

    async def execute_deletions(self, schedules_to_delete: List[int]) -> None:
        if not schedules_to_delete:
            return
        await self.ensure_awake()
        for sched_id in schedules_to_delete:
            for _ in range(6):
                try:
                    await tesla.remove_charge_schedule(self.token, self.vehicle_id, int(sched_id))
                    break
                except ValueError:
                    await self.ensure_awake(force=True)
                except Exception as e:
                    log.warning("Non-retryable error removing schedule %s: %s", sched_id, e)
                    break

    async def execute_updates(self, schedules_to_update: List[Dict[str, Any]]) -> None:
        if not schedules_to_update:
            return
        await self.ensure_awake()
        for update in schedules_to_update:
            days_list = [DAYS_MAP_STR[i] for i in range(7) if update["days_of_week"] & TESLA_MASKS[i]]
            days_of_week_str = ",".join(days_list)
            
            for _ in range(6):
                try:
                    await tesla.add_charge_schedule(
                        access_token=self.token,
                        vehicle_id=self.vehicle_id,
                        days_of_week=days_of_week_str,
                        enabled=True,
                        lat=float(update["lat"]),
                        lon=float(update["lon"]),
                        start_time=update["start_time"],
                        end_time=update["end_time"],
                        one_time=False,
                        id=update["id"]
                    )
                    break
                except ValueError:
                    await self.ensure_awake(force=True)
                except Exception as e:
                    log.error("Failed to update schedule %s: %s", update["id"], e)
                    break

    async def execute_additions(
        self, 
        desired_blocks: List[Dict[str, Any]], 
        sched_list: List[Dict[str, Any]], 
        user: User, 
        threshold: float
    ) -> None:
        if not desired_blocks:
            return
        await self.ensure_awake()

        for i, block in enumerate(desired_blocks):
            next_id = int(time.time()) + i
                
            success = False
            for _ in range(6):
                try:
                    await tesla.add_charge_schedule(
                        access_token=self.token,
                        vehicle_id=self.vehicle_id,
                        days_of_week=block["day_str"],
                        enabled=True,
                        lat=float(user.home_latitude),
                        lon=float(user.home_longitude),
                        start_time=block["start"],
                        end_time=block["end"],
                        one_time=False,
                        id=next_id
                    )
                    success = True
                    break
                except ValueError:
                    await self.ensure_awake(force=True)
                except Exception as e:
                    log.error("add_charge_schedule fatal error: %s", e)
                    break
                    
            if success:
                if user.push_token and user.price_change_reminder:
                    msg_title = "Charging Schedule Set"
                    msg_body = f"Scheduled to charge on {block['dt'].strftime('%A')} from {block['dt'].strftime('%H:%M')} to {block['end_dt'].strftime('%H:%M')} (Price <= {threshold:.4f} {user.currency}/kWh)."
                    asyncio.create_task(send_push_notification(user.push_token, msg_title, msg_body))
                
                if len(desired_blocks) > 1 and i < len(desired_blocks) - 1:
                    await asyncio.sleep(1)
