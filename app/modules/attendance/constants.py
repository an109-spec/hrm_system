from datetime import time
from decimal import Decimal

REGULAR_START = time(8, 0, 0)
REGULAR_END = time(17, 0, 0)
LUNCH_START = time(12, 0, 0)
LUNCH_END = time(13, 0, 0)

GRACE_PERIOD_MINUTES = 15
HALF_DAY_THRESHOLD = time(9, 0, 0)

OT_CHECKIN_OPEN = time(19, 0, 0)
OT_END_LIMIT = time(22, 0, 0)
MIN_OT_HOURS = Decimal("0.5")

REGULAR_DAY_RATE = Decimal("1.0")
WEEKEND_RATE = Decimal("1.5")
HOLIDAY_RATE = Decimal("3.0")

OT_NORMAL_DAY_RATE = Decimal("1.5")
OT_WEEKEND_RATE = Decimal("2.0")
OT_HOLIDAY_RATE = Decimal("3.0")
