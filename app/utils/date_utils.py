# C:\HRM_TOTNGHIEP\app\utils\date_utils.py
import calendar
from datetime import date

def get_month_range(month: int, year: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year, month, calendar.monthrange(year, month)[1])
    return start, end

def get_month_window(month: int | None = None, year: int | None = None) -> tuple[date, date]:
    """Lấy range tháng hiện tại nếu month/year là None."""
    today = date.today()
    target_month = month or today.month
    target_year = year or today.year
    return get_month_range(target_month, target_year)