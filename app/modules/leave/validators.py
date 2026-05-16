from datetime import date
from app.utils.time import get_current_time

class LeaveValidator:

    @staticmethod
    def validate_date_range(from_date: date, to_date: date):
        """Kiểm tra khoảng ngày nghỉ"""
        # Lấy thời gian hiện tại từ hệ thống simulation
        now = get_current_time().date()
        
        if from_date < now:
            raise ValueError("❌ Không thể xin nghỉ phép cho các ngày trong quá khứ.")
            
        if from_date > to_date:
            raise ValueError("❌ Ngày bắt đầu không được lớn hơn ngày kết thúc.")

    @staticmethod
    def validate_reason(reason: str):
        """Kiểm tra lý do nghỉ"""
        if not reason or len(reason.strip()) < 5:
            raise ValueError("❌ Lý do nghỉ phải có ít nhất 5 ký tự.")

    @staticmethod
    def validate_leave_days_limit(remaining_days: float, requested_days: int):
        """Kiểm tra số dư ngày phép"""
        # Chuyển về float hoặc Decimal để so sánh chính xác
        if float(requested_days) > float(remaining_days):
            raise ValueError(f"❌ Bạn chỉ còn {remaining_days} ngày phép, không đủ để nghỉ {requested_days} ngày.")