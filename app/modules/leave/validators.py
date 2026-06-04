from datetime import date
from app.utils.time import get_current_time
from app.modules.leave.dto import LeaveRequestDTO

class LeaveValidator:
    """
    Validator tập trung xử lý các logic nghiệp vụ phụ thuộc vào:
    - Thời gian hệ thống (ngày quá khứ)
    - Dữ liệu Database (số dư phép)
    - Chính sách công ty (lý do nghỉ)
    """

    @staticmethod
    def validate(dto: LeaveRequestDTO, remaining_days: float):
        """
        Hàm bao (Wrapper) để gọi tất cả các bước validate.
        Sử dụng hàm này trong Service để code ngắn gọn nhất.
        """
        LeaveValidator._validate_date_in_future(dto.from_date)
        LeaveValidator._validate_balance(dto.requested_days, remaining_days)
        LeaveValidator._validate_reason(dto.reason)

    @staticmethod
    def _validate_date_in_future(from_date: date):
        """Kiểm tra ngày xin nghỉ có phải quá khứ không"""
        now = get_current_time().date()
        if from_date < now:
            raise ValueError("❌ Không thể xin nghỉ phép cho các ngày trong quá khứ.")

    @staticmethod
    def _validate_balance(requested_days: int, remaining_days: float):
        """Kiểm tra số dư ngày phép từ DB"""
        if float(requested_days) > float(remaining_days):
            raise ValueError(
                f"❌ Bạn chỉ còn {remaining_days} ngày phép, không đủ để nghỉ {requested_days} ngày."
            )

    @staticmethod
    def _validate_reason(reason: str):
        """Kiểm tra quy định về lý do nghỉ"""
        if not reason or len(reason.strip()) < 5:
            raise ValueError("❌ Lý do nghỉ phải có ít nhất 5 ký tự.")