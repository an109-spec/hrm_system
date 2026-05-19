from datetime import date
from app.models import Holiday
from app.extensions.db import db
import importlib


VN_FIXED_PUBLIC_HOLIDAYS = {
    "01-01": "Tết Dương lịch",
    "04-30": "Ngày Giải phóng miền Nam",
    "05-01": "Quốc tế Lao động",
    "09-02": "Quốc khánh",
}

VN_LUNAR_PUBLIC_HOLIDAYS = (
    (1, 1, "Tết Nguyên đán (Mùng 1)"),
    (1, 2, "Tết Nguyên đán (Mùng 2)"),
    (1, 3, "Tết Nguyên đán (Mùng 3)"),
    (1, 4, "Tết Nguyên Đán"),
    (1, 5, "Tết Nguyên Đán"),
    (3, 10, "Giỗ Tổ Hùng Vương"),
)

def _resolve_lunar_date_class():
    spec = importlib.util.find_spec("lunardate")
    if spec is None:
        return None
    module = importlib.import_module("lunardate")
    return getattr(module, "LunarDate", None)
LUNAR_DATE_CLASS = _resolve_lunar_date_class()

def _build_lunar_public_holidays_for_year(year: int) -> dict[str, str]:
    if LUNAR_DATE_CLASS is None:
        return {}
    lookup: dict[str, str] = {}
    for lunar_month, lunar_day, holiday_name in VN_LUNAR_PUBLIC_HOLIDAYS:
        try:
            lunar_date_obj = LUNAR_DATE_CLASS(year, lunar_month, lunar_day)
            solar_date = lunar_date_obj.toSolarDate()
            lookup[solar_date.strftime("%m-%d")] = holiday_name
        except Exception:
            continue
    return lookup

class HolidayConfig:
    _LUNAR_HOLIDAY_CACHE = {}
    @classmethod
    def get_lunar_holidays(cls, year: int):
        if year not in cls._LUNAR_HOLIDAY_CACHE:
            cls._LUNAR_HOLIDAY_CACHE[year] = _build_lunar_public_holidays_for_year(year)
        return cls._LUNAR_HOLIDAY_CACHE[year]

