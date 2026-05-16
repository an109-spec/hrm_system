from datetime import time
from decimal import Decimal

REGULAR_START = time(8, 0, 0)
REGULAR_END = time(17, 0, 0)

LUNCH_START = time(12, 0, 0)
LUNCH_END = time(13, 0, 0)

GRACE_PERIOD_MINUTES = 15

# sau 09:00 tính half-day
HALF_DAY_THRESHOLD = time(9, 0, 0)

# nhân viên được xác thực OT từ 19h
OT_CHECKIN_OPEN = time(19, 0, 0)

# OT tối đa tới 22h
OT_END_LIMIT = time(22, 0, 0)

# dưới 30 phút không tính OT
MIN_OT_HOURS = Decimal("0.5")

REGULAR_DAY_RATE = Decimal("1.0")

# cuối tuần
WEEKEND_RATE = Decimal("1.5")

# lễ
HOLIDAY_RATE = Decimal("3.0")

OT_NORMAL_DAY_RATE = Decimal("1.5")
OT_WEEKEND_RATE = Decimal("2.0")
OT_HOLIDAY_RATE = Decimal("3.0")

SYSTEM_TIMEZONE = "Asia/Ho_Chi_Minh"

OT_APPROVED_REQUIRED_STATES = {
    "PRE_OT_REST",
    "OT_CHECKIN_REQUIRED",
    "WORKING_OVERTIME",
}

IMMUTABLE_OFFDAY_STATES = {
    "HOLIDAY_OFF",
    "WEEKEND_OFF",
}

FINAL_SHIFT_STATES = {
    "COMPLETED",
    "HOLIDAY_OFF",
    "WEEKEND_OFF",
    "LEAVE",
}