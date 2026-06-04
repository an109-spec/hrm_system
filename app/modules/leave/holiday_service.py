from datetime import date
from app.models.leave import Holiday  
from app.constants import VN_FIXED_PUBLIC_HOLIDAYS, HolidayConfig
from app.extensions.db import db

class HolidayDTO:
    """Class chuẩn hóa kết quả trả về của HolidayService"""
    def __init__(self, name: str, is_paid: bool):
        self.name = name
        self.is_paid = is_paid

class HolidayService:

    @classmethod
    def get_holiday_for_date(cls, target_date: date) -> HolidayDTO | None:
        """
        Xác định một ngày có phải là ngày lễ hay không.
        Trả về: HolidayDTO hoặc None.
        """
        
        # 1. Kiểm tra ngày lễ cụ thể trong Database (Lễ đột xuất)
        exact_holiday = Holiday.query.filter_by(date=target_date).first()
        if exact_holiday:
            return HolidayDTO(exact_holiday.name, exact_holiday.is_paid)

        # 2. Kiểm tra ngày lễ lặp lại hàng năm trong Database
        recurring_holiday = (
            Holiday.query.filter(
                Holiday.is_recurring.is_(True),
                db.extract("month", Holiday.date) == target_date.month,
                db.extract("day", Holiday.date) == target_date.day,
            )
            .order_by(Holiday.id.asc())
            .first()
        )
        if recurring_holiday:
            return HolidayDTO(recurring_holiday.name, recurring_holiday.is_paid)

        # 3. Tra cứu ngày lễ Dương lịch cố định
        fixed_name = VN_FIXED_PUBLIC_HOLIDAYS.get(target_date.strftime("%m-%d"))
        if fixed_name:
            return HolidayDTO(fixed_name, True)

        # 4. Tra cứu ngày lễ Âm lịch
        lunar_lookup = HolidayConfig.get_lunar_holidays(target_date.year)
        lunar_name = lunar_lookup.get(target_date.strftime("%m-%d"))
        if lunar_name:
            return HolidayDTO(lunar_name, True)

        return None