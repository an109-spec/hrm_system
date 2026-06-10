from decimal import Decimal
from app.constants.attendance import AttendanceConstants
from app.constants.overtime import OvertimeConfig
from .dto import WorkUnitDTO
from app.models.attendance import Attendance
from app.constants.attendance import WorkConfig
from datetime import datetime
from app.utils.time import VN_TIMEZONE
from typing import Optional
class attendance_calculation_service:
    @staticmethod
    def _get_day_rate(attendance_type: str | None) -> Decimal:
        normalized_type = AttendanceConstants.normalize(attendance_type)
        RATE_MAP = {
            AttendanceConstants.TYPE_NORMAL: OvertimeConfig.MULTIPLIERS["normal"],
            AttendanceConstants.TYPE_WEEKEND: OvertimeConfig.MULTIPLIERS["weekend"],
            AttendanceConstants.TYPE_HOLIDAY: OvertimeConfig.MULTIPLIERS["holiday"],
            AttendanceConstants.TYPE_LEAVE_APPROVED: OvertimeConfig.MULTIPLIERS["leave_approved"],
        }
        # 3. Tập hợp các loại ngày vắng mặt không được tính lương (trả về 0)
        ABSENT_TYPES = {
            AttendanceConstants.TYPE_ABSENT,
            AttendanceConstants.TYPE_ABSENT_UNEXCUSED,
            AttendanceConstants.TYPE_ABNORMAL_REJECTED,
        }
        # 4. Kiểm tra điều kiện vắng mặt trước
        if normalized_type in ABSENT_TYPES:
            return Decimal("0.00")
        # 5. Trả về tỷ lệ tương ứng, mặc định là ngày thường nếu truyền loại lạ
        return RATE_MAP.get(
            normalized_type,
            OvertimeConfig.MULTIPLIERS["normal"]
        )
    '''
    tính toán công hàng ngày
    '''
    @staticmethod
    def calculate_regular_work_units(attendance: Attendance) -> WorkUnitDTO:
        # 1. Trường hợp thiếu dữ liệu check-in/out cơ bản
        if not attendance.check_in or not attendance.check_out:
            return WorkUnitDTO(
                units=Decimal("0.00"),
                is_half_day=False,
                worked_hours=Decimal("0.00"),
                late_minutes=0,
                early_leave_minutes=0
            )

        # Chuẩn hóa loại hình chấm công
        normalized_type = AttendanceConstants.normalize(attendance.attendance_type)
        
        ABSENT_TYPES = {
            AttendanceConstants.TYPE_ABSENT,
            AttendanceConstants.TYPE_ABSENT_UNEXCUSED,
            AttendanceConstants.TYPE_ABNORMAL_REJECTED,
        }

        # 2. Trường hợp thuộc nhóm Vắng mặt / Bị từ chối
        if normalized_type in ABSENT_TYPES:
            return WorkUnitDTO(
                units=Decimal("0.00"),
                is_half_day=False,
                worked_hours=Decimal("0.00"),
                late_minutes=attendance.late_minutes or 0,
                early_leave_minutes=0
            )

        # 3. Trường hợp Nghỉ phép đã được duyệt (Được tính nguyên công và giờ chuẩn)
        if normalized_type == AttendanceConstants.TYPE_LEAVE_APPROVED:
            return WorkUnitDTO(
                units=Decimal("1.00"),
                is_half_day=False,
                worked_hours=Decimal("8.00"),
                late_minutes=0,
                early_leave_minutes=0
            )

        # 4. Tính toán logic dựa trên số phút đi muộn và cấu hình WorkConfig
        raw_hours = Decimal(str(attendance.regular_hours or 0))
        late_minutes = attendance.late_minutes or 0
        early_leave_minutes = attendance.early_leave_minutes or 0

        # Chuyển đổi cấu hình thời gian sang số phút trong ngày
        start_minutes = WorkConfig.WORKDAY_START.hour * 60 + WorkConfig.WORKDAY_START.minute
        threshold_minutes = WorkConfig.LATE_THRESHOLD.hour * 60 + WorkConfig.LATE_THRESHOLD.minute
        
        # Khoảng cách tối đa cho phép trước khi bị tính nửa ngày (9:00 - 8:00 = 60 phút)
        half_day_limit = threshold_minutes - start_minutes

        # Xác định trạng thái đi muộn thành nửa ngày
        is_half_day = late_minutes >= half_day_limit

        is_late_over_limit = late_minutes >= half_day_limit
        # Trường hợp làm việc quá ít (Dưới 2 tiếng) -> Không tính công
        if raw_hours < Decimal("2.00"):
            return WorkUnitDTO(
                units=Decimal("0.00"),
                is_half_day=is_half_day,
                worked_hours=raw_hours,
                late_minutes=late_minutes,
                early_leave_minutes=early_leave_minutes
            )

        # Trường hợp bị đánh nửa ngày công (Do đi muộn > 60p hoặc tổng giờ làm < 4 tiếng)
        if is_late_over_limit or raw_hours < Decimal("4.00"):
            return WorkUnitDTO(
                units=Decimal("0.50"),
                is_half_day=is_late_over_limit, 
                worked_hours=raw_hours,
                late_minutes=late_minutes,
                early_leave_minutes=early_leave_minutes
            )

        # Trường hợp hoàn thành trọn vẹn ngày công chính thức
        return WorkUnitDTO(
            units=Decimal("1.00"),
            is_half_day=False,
            worked_hours=raw_hours,
            late_minutes=late_minutes,
            early_leave_minutes=early_leave_minutes
        )
    '''
    Tính toán giờ tăng ca (OT) thực tế
    '''
    @staticmethod
    def calculate_overtime_hours_raw(
        overtime_check_in: Optional[datetime],
        overtime_check_out: Optional[datetime]
    ) -> Decimal:
        # 1. Kiểm tra nếu thiếu một trong hai đầu dữ liệu check-in/out OT
        if not overtime_check_in or not overtime_check_out:
            return Decimal("0.00")
            
        # 2. Xử lý chuẩn hóa múi giờ an toàn cho input
        if overtime_check_in.tzinfo is None:
            overtime_check_in = overtime_check_in.replace(tzinfo=VN_TIMEZONE)
        else:
            overtime_check_in = overtime_check_in.astimezone(VN_TIMEZONE)
            
        if overtime_check_out.tzinfo is None:
            overtime_check_out = overtime_check_out.replace(tzinfo=VN_TIMEZONE)
        else:
            overtime_check_out = overtime_check_out.astimezone(VN_TIMEZONE)

        # Nếu thời gian check-out đứng trước hoặc bằng check-in -> Dữ liệu lỗi
        if overtime_check_out <= overtime_check_in:
            return Decimal("0.00")

        # 3. Kết hợp ngày điểm danh với khung giờ OT chuẩn từ WorkConfig
        day = overtime_check_in.date()
        
        # Tạo mốc bắt đầu OT (18:00:00) và kết thúc OT giới hạn (22:00:00) trong ngày
        ot_start = datetime.combine(day, WorkConfig.OT_START).replace(tzinfo=VN_TIMEZONE)
        ot_end = datetime.combine(day, WorkConfig.OT_END).replace(tzinfo=VN_TIMEZONE)
        
        # Xử lý nâng cao: Nếu cấu hình OT_END nhỏ hơn hoặc bằng OT_START, hiểu là kết thúc vào ngày hôm sau
        if WorkConfig.OT_END <= WorkConfig.OT_START:
            from datetime import timedelta
            ot_end = datetime.combine(day + timedelta(days=1), WorkConfig.OT_END).replace(tzinfo=VN_TIMEZONE)
        
        # 4. Giới hạn khung giờ làm việc thực tế nằm trong cửa sổ cấu hình OT
        actual_start = max(ot_start, overtime_check_in)
        actual_end = min(ot_end, overtime_check_out)
        
        # Nếu sau khi ép khung mà khoảng thời gian không hợp lệ
        if actual_end <= actual_start:
            return Decimal("0.00")
            
        # 5. Tính toán tổng số giờ (Làm tròn đến 4 chữ số thập phân để đảm bảo độ chính xác)
        hours = (actual_end - actual_start).total_seconds() / 3600
        return Decimal(str(round(hours, 4)))
    
    @staticmethod
    def _day_multiplier(is_holiday: bool, is_weekend: bool) -> Decimal:
        """
        Xác định hệ số nhân lương dựa trên tính chất ngày làm việc.
        Dữ liệu được chuyển đổi an toàn từ cấu hình hằng số hệ thống.
        """
        if is_holiday:
            return Decimal(str(OvertimeConfig.MULTIPLIERS["holiday"]))
        if is_weekend:
            return Decimal(str(OvertimeConfig.MULTIPLIERS["weekend"]))
        return Decimal(str(OvertimeConfig.MULTIPLIERS["normal"]))