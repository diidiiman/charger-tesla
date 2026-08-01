import zoneinfo
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from . import prices

TESLA_MASKS = [1, 2, 4, 8, 16, 32, 64]  # MON, TUE, WED, THU, FRI, SAT, SUN
DAYS_MAP_STR = ["MON", "TUES", "WED", "THURS", "FRI", "SAT", "SUN"]

class ScheduleCalculator:
    @staticmethod
    def get_cheap_prices(
        region_prices: List[prices.RegionPrice], threshold: float, multiplier: float
    ) -> List[prices.RegionPrice]:
        return [p for p in region_prices if float(p.price) * multiplier <= threshold]

    @staticmethod
    def group_into_blocks(
        cheap_hours: List[prices.RegionPrice], tz: zoneinfo.ZoneInfo
    ) -> List[List[prices.RegionPrice]]:
        blocks = []
        if not cheap_hours:
            return blocks
            
        current_block = [cheap_hours[0]]
        for i in range(1, len(cheap_hours)):
            prev = current_block[-1]
            curr = cheap_hours[i]
            
            prev_local = prev.valid_from.astimezone(tz)
            curr_local = curr.valid_from.astimezone(tz)
            
            if curr.valid_from == prev.valid_to and prev_local.date() == curr_local.date():
                current_block.append(curr)
            else:
                blocks.append(current_block)
                current_block = [curr]
        blocks.append(current_block)
        return blocks

    @staticmethod
    def blocks_to_time_windows(
        blocks: List[List[prices.RegionPrice]], tz: zoneinfo.ZoneInfo,
        now_local: datetime, target_date: Optional[datetime.date]
    ) -> List[Dict[str, Any]]:
        desired_blocks = []
        for block in blocks:
            start_dt = block[0].valid_from.astimezone(tz)
            end_dt = block[-1].valid_to.astimezone(tz)
            
            if target_date is None and end_dt <= now_local:
                continue

            start_minutes = start_dt.hour * 60 + start_dt.minute
            end_minutes = end_dt.hour * 60 + end_dt.minute
            
            if target_date is None and start_dt.date() == now_local.date():
                now_minutes = now_local.hour * 60 + now_local.minute
                if start_minutes < now_minutes:
                    start_minutes = now_minutes + 2
                    if end_minutes <= start_minutes:
                        continue
            
            block_mask = TESLA_MASKS[start_dt.weekday()]
            block_day_str = DAYS_MAP_STR[start_dt.weekday()]
            
            desired_blocks.append({
                "start": start_minutes, 
                "end": end_minutes, 
                "dt": start_dt, 
                "end_dt": end_dt,
                "mask": block_mask,
                "day_str": block_day_str
            })
        return desired_blocks
