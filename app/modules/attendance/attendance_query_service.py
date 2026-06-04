from datetime import datetime, date, time, timedelta
from calendar import monthrange
from decimal import Decimal
from types import SimpleNamespace
from app.constants.leave import LeaveStatus
from app.utils.time import get_current_time
from app import db
from app.common.exceptions import ValidationError

from app.models.attendance import AttendanceType, Attendance, AttendanceStatus, AttendanceShiftStatus
from app.models.leave import LeaveRequest
from app.models.leave import Holiday
from app.models.employee import Employee
from app.models.notification import Notification

from app.models import (
    Employee,
    Holiday,
    OvertimeRequest,
    LeaveRequest,
    Notification,
)
from app.constants.holidays import VN_FIXED_PUBLIC_HOLIDAYS, HolidayConfig
class AttendanceCommandService:
    @staticmethod
    def normalize_status(status_name: str | None) -> str | None:
        return AttendanceStatus.validate_and_normalize(status_name)
    
    @staticmethod
    def get_status(status_name: str | None) -> AttendanceStatus | None:
        normalized = AttendanceStatus.validate_and_normalize(status_name)
        if not normalized:
            return None
        return AttendanceStatus.query.filter_by(
            status_name=normalized
        ).first()

    @staticmethod
    def _get_holiday(target_date: date) -> Holiday | dict | None:
        year = target_date.year
        month_day_str = target_date.strftime("%m-%d")
        if month_day_str in VN_FIXED_PUBLIC_HOLIDAYS:
            return {
                "name": VN_FIXED_PUBLIC_HOLIDAYS[month_day_str],
                "date": target_date,
                "is_paid": True,
                "is_recurring": True
            }
        lunar_holidays = HolidayConfig.get_lunar_holidays(year)
        if month_day_str in lunar_holidays:
            return {
                "name": lunar_holidays[month_day_str],
                "date": target_date,
                "is_paid": True,
                "is_recurring": False  # Lễ âm lịch tính theo từng năm nên không lặp ngày dương cố định
            }
        holiday = Holiday.query.filter(
            Holiday.date == target_date,
            Holiday.is_recurring.is_(False)
        ).first()
        if holiday:
            return holiday
        recurring_holiday = Holiday.query.filter(
            Holiday.is_recurring.is_(True),
            db.extract("month", Holiday.date) == target_date.month,
            db.extract("day", Holiday.date) == target_date.day
        ).first()
        if recurring_holiday:
            return recurring_holiday
        return None

    @staticmethod
    def get_today(
        employee_id: int,
        now_dt: datetime | None = None
    ) -> Attendance | None:
        if now_dt is None:
            now_dt = get_current_time()
        target_date = now_dt.date()
        record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=target_date
        ).first()
        if not record and now_dt.hour < 5:
            yesterday = target_date - timedelta(days=1)
            prev_record = Attendance.query.filter_by(
                employee_id=employee_id,
                date=yesterday
            ).first()
            if prev_record:
                status = prev_record.normalized_shift_status
                if status in [
                    Attendance.ShiftStatus.WORKING_REGULAR, 
                    Attendance.ShiftStatus.WORKING_OVERTIME,
                    Attendance.ShiftStatus.REGULAR_CHECKOUT_REQUIRED
                ]:
                    record = prev_record
        return record

    @staticmethod
    def get_history(
        employee_id: int,
        limit: int = 10,
        month: int | None = None,
        year: int | None = None,
        now_dt: datetime | None = None,
    ):
        if now_dt is None:
            now_dt = get_current_time()  # Đảm bảo hàm này trả về datetime chuẩn múi giờ VN
        today = now_dt.date()

        # TH1: Nếu không truyền tháng/năm -> Lấy danh sách chấm công thực tế gần nhất giới hạn theo limit
        if not month or not year:
            return (
                Attendance.query.filter(
                    Attendance.employee_id == employee_id,
                    Attendance.date <= today,
                    Attendance.is_deleted.is_(False)  # ĐỒNG BỘ: Loại bỏ các bản ghi đã xóa
                )
                .order_by(Attendance.date.desc())
                .limit(limit)
                .all()
            )

        # Kiểm tra tính hợp lệ của tháng đầu vào
        if month < 1 or month > 12:
            raise ValidationError("Tháng không hợp lệ")

        # Xác định khoảng ngày trong tháng cần tính toán công
        last_day = monthrange(year, month)[1]
        month_start = date(year, month, 1)
        month_end = date(year, month, last_day)

        # Ngày kết thúc hiệu lực: Không vượt quá ngày hôm nay nếu xem tháng hiện tại
        effective_end = (
            month_end
            if (year, month) < (today.year, today.month)
            else min(month_end, today)
        )

        if effective_end < month_start:
            return []

        # 1. Lấy tất cả dữ liệu chấm công thực tế trong tháng
        attendance_rows = Attendance.query.filter(
            Attendance.employee_id == employee_id,
            Attendance.date >= month_start,
            Attendance.date <= effective_end,
            Attendance.is_deleted.is_(False)  # ĐỒNG BỘ: Đảm bảo không lấy thực thể đã bị soft-delete
        ).all()
        
        attendance_by_date = {r.date: r for r in attendance_rows}

        # 2. Lấy tất cả đơn xin nghỉ phép đã được phê duyệt giao thoa với tháng này
        leave_rows = LeaveRequest.query.filter(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status == LeaveStatus.APPROVED,  # ĐỒNG BỘ: Sử dụng hằng số chuẩn từ constants
            LeaveRequest.is_deleted.is_(False),
            LeaveRequest.from_date <= effective_end,
            LeaveRequest.to_date >= month_start,
        ).all()

        leave_dates = set()
        for leave in leave_rows:
            start = max(leave.from_date, month_start)
            end = min(leave.to_date, effective_end)
            cur = start
            while cur <= end:
                leave_dates.add(cur)
                cur = date.fromordinal(cur.toordinal() + 1)

        # 3. Lấy dữ liệu ngày lễ (Cố định và lặp lại hàng năm)
        fixed_holidays = Holiday.query.filter(
            Holiday.is_recurring.is_(False),
            Holiday.date >= month_start,
            Holiday.date <= effective_end,
        ).all()

        recurring_holidays = Holiday.query.filter(
            Holiday.is_recurring.is_(True)
        ).all()

        holiday_dates = {h.date for h in fixed_holidays}
        for h in recurring_holidays:
            try:
                # Đưa ngày lễ lặp lại về năm và tháng đang xét để đối chiếu
                hd = date(year, month, h.date.day)
                if month_start <= hd <= effective_end:
                    holiday_dates.add(hd)
            except ValueError:
                # Tránh crash nếu cấu hình ngày lặp lại không hợp lệ (ví dụ ngày 29/02 vào năm không nhuận)
                continue

        # 4. Duyệt ngược từ ngày effective_end về đầu tháng để dựng dòng lịch sử công
        history = []
        current = effective_end
        while current >= month_start:
            if current in attendance_by_date:
                # Nếu đã có bản ghi chấm công thực tế trong DB, ưu tiên lấy trực tiếp bản ghi đó
                history.append(attendance_by_date[current])
            else:
                # Nếu trống lịch sử, tiến hành giả lập trạng thái ngày dựa trên đơn phép, ngày lễ, ngày nghỉ tuần
                is_weekend = current.weekday() >= 5
                is_holiday = current in holiday_dates
                is_leave = current in leave_dates

                if is_leave:
                    shift_status = Attendance.ShiftStatus.LEAVE
                    attendance_type = Attendance.Type.LEAVE_APPROVED
                elif is_holiday:
                    shift_status = Attendance.ShiftStatus.HOLIDAY_OFF
                    attendance_type = Attendance.Type.HOLIDAY
                elif is_weekend:
                    shift_status = Attendance.ShiftStatus.WEEKEND_OFF
                    attendance_type = Attendance.Type.WEEKEND
                else:
                    shift_status = Attendance.ShiftStatus.ABSENT
                    attendance_type = Attendance.Type.ABSENT

                # Mock object thông qua SimpleNamespace đồng bộ hoàn chỉnh cấu trúc thuộc tính với Model Attendance
                history.append(
                    SimpleNamespace(
                        id=None,
                        date=current,
                        check_in=None,
                        check_out=None,
                        overtime_check_in=None,
                        overtime_check_out=None,
                        regular_hours=Decimal("0.00"),
                        overtime_hours=Decimal("0.00"),
                        working_hours=Decimal("0.00"),
                        # Sử dụng hàm chuẩn hóa normalize của Model để sinh chuỗi trạng thái đồng nhất
                        shift_status=Attendance.ShiftStatus.normalize(shift_status),
                        attendance_type=attendance_type,
                        late_minutes=0,
                        is_half_day=False,
                        is_weekend=is_weekend,
                        is_holiday=is_holiday,
                    )
                )
            current = date.fromordinal(current.toordinal() - 1)
        return history
    
    @staticmethod
    def delete_attendance(
        employee_id: int,
        date_str: str
    ) -> date | None:
        from app.utils.time import _normalize
        try:
            parsed_dt = _normalize(date_str)
            if not parsed_dt:
                raise ValueError
            target_date = parsed_dt.date()
        except (TypeError, ValueError):
            raise ValidationError("Ngày không hợp lệ. Định dạng yêu cầu: YYYY-MM-DD")
        record = Attendance.query.filter_by(
            employee_id=employee_id,
            date=target_date
        ).filter(Attendance.is_deleted.is_(False)).first()
        if not record:
            raise ValidationError(f"Không tìm thấy dữ liệu chấm công ngày {target_date}")
        OvertimeRequest.query.filter(
            OvertimeRequest.employee_id == employee_id,
            OvertimeRequest.overtime_date == target_date,
            OvertimeRequest.is_deleted.is_(False)
        ).update({"is_deleted": True}, synchronize_session=False)
        employee = Employee.query.get(employee_id)
        if employee and employee.user_id:
            start_of_day = datetime.combine(target_date, time.min)
            end_of_day = datetime.combine(target_date, time.max)
            Notification.query.filter(
                Notification.user_id == employee.user_id,
                Notification.type.in_(["attendance", "overtime"]),
                Notification.created_at >= start_of_day,
                Notification.created_at <= end_of_day,
                Notification.is_deleted.is_(False)
            ).update({"is_deleted": True}, synchronize_session=False)
        record.is_deleted = True
        db.session.commit()
        last_record = (
            Attendance.query
            .filter_by(employee_id=employee_id)
            .filter(Attendance.is_deleted.is_(False))  # Quan trọng: Loại bỏ bản ghi vừa xóa mềm
            .order_by(Attendance.date.desc())
            .first()
        )
        return last_record.date if last_record else None
    
    @staticmethod
    def delete_notification_cascade(
        notification_id: int,
        user_id: int,
    ) -> dict:
        # 1. Tìm thông báo còn hoạt động của user cụ thể
        noti = Notification.query.filter_by(
            id=notification_id,
            user_id=user_id,
        ).filter(Notification.is_deleted.is_(False)).first()
        
        if not noti:
            raise ValidationError("Không tìm thấy thông báo")

        # Thực hiện xóa mềm thông báo chính
        noti.is_deleted = True
        cascaded = []

        # 2. Xử lý xóa dây chuyền nếu thông báo thuộc nhóm tăng ca (overtime)
        if noti.type == "overtime":
            target_date = noti.created_at.date() if noti.created_at else None
            
            if target_date:
                # Tìm nhân viên sở hữu thông qua tài khoản liên kết user_id
                employee = Employee.query.filter_by(user_id=user_id).first()

                if employee:
                    # a. Tìm và xóa mềm toàn bộ các đơn yêu cầu tăng ca trong ngày hôm đó
                    ot_requests = OvertimeRequest.query.filter(
                        OvertimeRequest.employee_id == employee.id,
                        OvertimeRequest.overtime_date == target_date,
                        OvertimeRequest.is_deleted.is_(False),
                    ).all()
                    
                    for ot in ot_requests:
                        ot.is_deleted = True
                        cascaded.append( f"OT request #{ot.id}" )

                    # b. Cập nhật và tính toán lại bảng công (Attendance) tương ứng
                    att = Attendance.query.filter_by(
                        employee_id=employee.id,
                        date=target_date,
                    ).filter(Attendance.is_deleted.is_(False)).first()
                    
                    if att:
                        # Reset toàn bộ các thông số liên quan đến tăng ca về giá trị mặc định
                        att.overtime_hours = Decimal("0.00")
                        att.overtime_check_in = None
                        att.overtime_check_out = None
                        
                        # Đồng bộ lại tổng số giờ làm việc thực tế bằng đúng số giờ hành chính
                        regular_hours = Decimal(str(att.regular_hours or 0))
                        att.working_hours = regular_hours.quantize(Decimal("0.01"))
                        
                        # Cập nhật loại hình chấm công về ngày thường (Hủy bỏ trạng thái OVERTIME)
                        att.set_attendance_type(AttendanceType.NORMAL)

                        # c. Khôi phục trạng thái ca (shift_status) dựa trên lịch sử check-in hành chính
                        if att.check_in and att.check_out:
                            att.set_shift_status(AttendanceShiftStatus.REGULAR_DONE)
                        elif att.check_in:
                            att.set_shift_status(AttendanceShiftStatus.WORKING_REGULAR)
                        else:
                            if att.is_holiday:
                                att.set_shift_status(AttendanceShiftStatus.HOLIDAY_OFF)
                            elif att.is_weekend:
                                att.set_shift_status(AttendanceShiftStatus.WEEKEND_OFF)
                            else:
                                att.set_shift_status(AttendanceShiftStatus.NOT_STARTED)
                                
                        cascaded.append(
                            f"Attendance overtime reset ({target_date})"
                        )

        # 3. Đẩy toàn bộ thay đổi xuống Database trong cùng một Transaction
        db.session.commit()
        
        return {
            "deleted": True,
            "notification_id": notification_id,
            "cascaded": cascaded,
        }
    
    @staticmethod
    def _get_approved_ot(employee_id: int, target_date: date) -> OvertimeRequest | None:
        query = OvertimeRequest.query.filter(
            OvertimeRequest.employee_id == employee_id,
            OvertimeRequest.overtime_date == target_date,
            OvertimeRequest.status == "approved"  # Hoặc "approved_manager" tùy chuỗi bạn lưu khi bấm nút Duyệt
        )
        if hasattr(OvertimeRequest, 'is_deleted'):
            query = query.filter(OvertimeRequest.is_deleted.is_(False))
        return query.first()