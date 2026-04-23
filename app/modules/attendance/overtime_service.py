from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal


class OvertimeService:
    OT_START = time(19, 0, 0)
    OT_END = time(22, 0, 0)
    REGULAR_END = time(17, 0, 0)

    @staticmethod
    def is_weekend(target_date: date) -> bool:
        return target_date.weekday() >= 5

    @staticmethod
    def should_suggest_overtime(current_time: datetime, target_date: date) -> bool:
        return OvertimeService.is_weekend(target_date) or current_time.time() > OvertimeService.REGULAR_END

    @staticmethod
    def calculate_overtime(start: datetime, end: datetime) -> Decimal:
        ot_window_start = datetime.combine(start.date(), OvertimeService.OT_START)
        ot_window_end = datetime.combine(start.date(), OvertimeService.OT_END)

        effective_start = max(start, ot_window_start)
        effective_end = min(end, ot_window_end)

        if effective_end <= effective_start:
            return Decimal("0.00")

        seconds = Decimal((effective_end - effective_start).total_seconds())
        return (seconds / Decimal("3600")).quantize(Decimal("0.01"))