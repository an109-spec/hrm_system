from datetime import date
from app.models import Holiday
from app.extensions.db import db
from app.constants import VN_FIXED_PUBLIC_HOLIDAYS, HolidayConfig

class HolidayService:

    @classmethod
    def get_holiday_for_date(cls, target_date: date):
        """
        Xác định một ngày có phải là ngày lễ hay không.
        Ưu tiên: Custom DB -> Recurring DB -> Hệ thống Dương lịch -> Hệ thống Âm lịch.
        """
        # 1. Kiểm tra ngày lễ cụ thể được định nghĩa trong Database (Ví dụ: Lễ đột xuất năm 2026)
        exact_holiday = Holiday.query.filter_by(date=target_date).first()
        if exact_holiday:
            return exact_holiday

        # 2. Kiểm tra ngày lễ lặp lại hàng năm lưu trong Database
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
            return recurring_holiday

        # 3. Tra cứu ngày lễ Dương lịch cố định (Cấu hình tĩnh tại app/constants/)
        fixed_name = VN_FIXED_PUBLIC_HOLIDAYS.get(target_date.strftime("%m-%d"))
        if fixed_name:
            return {"name": fixed_name, "is_paid": True}

        # 4. Tra cứu ngày lễ Âm lịch dựa trên bộ nhớ đệm Cache (Cấu hình tĩnh tại app/constants/)
        lunar_lookup = HolidayConfig.get_lunar_holidays(target_date.year)
        lunar_name = lunar_lookup.get(target_date.strftime("%m-%d"))
        if lunar_name:
            return {"name": lunar_name, "is_paid": True}

        return None