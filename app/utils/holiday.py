from datetime import timedelta


def calculate_actual_leave_days(from_date, to_date):
    """
    Tính số ngày nghỉ thực tế: Loại bỏ Thứ 7, Chủ Nhật và Ngày lễ trong DB.
    """
    from app.models.leave import Holiday
    actual_days = 0
    current_date = from_date
    holidays = [h.date for h in Holiday.query.filter(Holiday.date.between(from_date, to_date)).all()]

    while current_date <= to_date:
        is_weekend = current_date.weekday() >= 5
        is_holiday = current_date in holidays
        if not is_weekend and not is_holiday:
            actual_days += 1
        current_date += timedelta(days=1)
    return actual_days