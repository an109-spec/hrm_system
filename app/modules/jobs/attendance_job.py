from __future__ import annotations
 
from datetime import datetime
from decimal import Decimal

from sqlalchemy import and_
 
from app.constants.attendance import WorkConfig
from app.constants.leave import LeaveStatus
from app.extensions.db import db
from app.models import Attendance, Employee, OvertimeRequest, Notification, AttendanceType
from app.models.attendance import AttendanceShiftStatus
from app.models.leave import LeaveRequest, LeaveType
from app.modules.attendance import attendance_calculation_service
from app.modules.attendance.attendance_query_service import AttendanceCommandService
from app.modules.attendance.service import AttendanceService
from app.utils.time import VN_TIMEZONE, get_current_time

 
class AttendanceJob:
 
    # =========================================================
    # HELPER: tạo notification cho nhân viên
    # =========================================================
    @staticmethod
    def _create_notification(
        employee_id: int,
        title: str,
        content: str,
        notification_type: str = "attendance",
    ) -> None:
        employee = Employee.query.get(employee_id)
        if not employee or not employee.user_id:
            return
        db.session.add(
            Notification(
                user_id=employee.user_id,
                title=title,
                content=content,
                type=notification_type,
                is_read=False,
            )
        )
 
    # =========================================================
    # JOB 17:00 — Nhắc checkout ca chính
    # =========================================================
    @staticmethod
    def run_17h_notification() -> dict:
        now = get_current_time()
        today = now.date()
        records = Attendance.query.filter(
            Attendance.date == today,
            Attendance.check_in.isnot(None),
            Attendance.check_out.is_(None),
            Attendance.shift_status == AttendanceShiftStatus.WORKING_REGULAR 
        ).all()
        for record in records:
            AttendanceJob._create_notification(
                employee_id=record.employee_id,
                title="Nhắc nhở checkout",
                content="Đã 17:00, vui lòng checkout ca làm việc để hoàn tất ngày công.",
                notification_type="attendance"
            )
        db.session.commit()
        return {"message": f"Đã gửi {len(records)} thông báo checkout 17h ngày {today}"}
    
    # =========================================================
    # JOB 19:00 — Nhắc check-in OT
    # =========================================================
    @staticmethod
    def run_19h_ot_notification() -> dict:
        now = get_current_time()
        today = now.date()
        approved_requests = OvertimeRequest.query.filter_by(
            overtime_date=today,
            status="approved",
        ).all()
        count = 0
        for ot_req in approved_requests:
            attendance = Attendance.query.filter_by(
                employee_id=ot_req.employee_id, 
                date=today
            ).first()
            # Nếu chưa có bản ghi chấm công (nghĩa là hôm nay không đi làm ca chính) -> Bỏ qua
            if not attendance:
                continue
            # Bỏ qua nếu chưa checkout ca chính (quy định: phải xong việc chính mới được OT)
            if not attendance.check_out:
                continue
            # Bỏ qua nếu nhân viên đã bấm check-in OT rồi
            if attendance.overtime_check_in:
                continue
            # Tận dụng property is_flow_terminal ông đã viết trong Model Attendance
            # Bỏ qua nếu trạng thái đã kết thúc (Vắng mặt, Nghỉ phép, hoặc đã Hoàn tất ngày công)
            if attendance.is_flow_terminal:
                continue
            # --- GỬI THÔNG BÁO ---
            AttendanceJob._create_notification(
                employee_id=ot_req.employee_id,
                title="Nhắc bắt đầu tăng ca",
                content="Đã 19:00. Bạn có đơn tăng ca đã được duyệt. Vui lòng check-in OT để bắt đầu tính giờ.",
                notification_type="overtime",
            )
            count += 1
        db.session.commit()
        return {"message": f"Đã gửi {count} thông báo bắt đầu OT lúc 19h ngày {today}"}

    # =========================================================
    # JOB 22:00 — Nhắc checkout OT
    # =========================================================
    @staticmethod
    def run_22h_ot_checkout_notification() -> dict:
        # 1. Lấy ngày hiện tại thông qua logic Simulation
        now = get_current_time()
        today = now.date()
        # 2. Lọc các bản ghi đang trong trạng thái Tăng ca mà chưa checkout
        records = Attendance.query.filter(
            Attendance.date == today,
            Attendance.overtime_check_in.isnot(None),
            Attendance.overtime_check_out.is_(None),
            Attendance.shift_status == AttendanceShiftStatus.WORKING_OVERTIME # Đang làm tăng ca
        ).all()
        for record in records:
            AttendanceJob._create_notification(
                employee_id=record.employee_id,
                title="Nhắc checkout tăng ca",
                content="Đã 22:00. Vui lòng thực hiện checkout OT để hệ thống chốt giờ làm thêm ngày hôm nay.",
                notification_type="overtime",
            )
        db.session.commit()
        return {"message": f"Đã gửi {len(records)} thông báo nhắc checkout OT lúc 22h ngày {today}"}
    
    # =========================================================
    # JOB 22:00 — Tự động chốt OT
    # =========================================================
    @staticmethod
    def run_22h_ot_auto_close() -> dict:
        now = get_current_time()
        today = now.date()
        ot_cutoff = datetime.combine(today, AttendanceService.OT_END).replace(tzinfo=now.tzinfo)
        records = Attendance.query.filter(
            Attendance.date == today,
            Attendance.overtime_check_in.isnot(None),
            Attendance.overtime_check_out.is_(None),
            Attendance.shift_status == AttendanceShiftStatus.WORKING_OVERTIME
        ).all()
        closed_count = 0
        for record in records:
            approved_ot = OvertimeRequest.query.filter(
                OvertimeRequest.employee_id == record.employee_id,
                OvertimeRequest.overtime_date == today,
                OvertimeRequest.status == "approved"
            ).order_by(OvertimeRequest.updated_at.desc()).first()
            if not approved_ot:
                continue
            record.overtime_check_out = ot_cutoff
            raw_hours = AttendanceService.calculate_overtime_hours(
                record.overtime_check_in, 
                record.overtime_check_out
            )
            multiplier = Decimal(str(approved_ot.holiday_multiplier or 1))
            record.overtime_hours = (raw_hours * multiplier).quantize(Decimal("0.01"))
            AttendanceService.finalize_attendance(record, finalize_status=True)
            AttendanceJob._create_notification(
                employee_id=record.employee_id,
                title="Hệ thống tự động chốt tăng ca",
                content=f"Đã qua 22:00, hệ thống đã tự động checkout OT và chốt công ngày {today.strftime('%d/%m')} cho bạn.",
                notification_type="overtime",
            )
            closed_count += 1
        db.session.commit()
        return {"message": f"Đã tự động chốt {closed_count} bản ghi OT ngày {today}"}
 
    # =========================================================
    # JOB CUỐI NGÀY — Finalize toàn bộ
    # ========================================================
    @staticmethod
    def run_daily() -> dict:
        current_dt = get_current_time()
        today = current_dt.date()
        
        # 1. Xác định bối cảnh ngày hôm nay
        holiday_info = AttendanceCommandService._get_holiday(today)
        is_holiday = holiday_info is not None
        is_weekend = today.weekday() >= 5
        
        # 2. Lấy danh sách nhân viên cần chấm công
        employees = Employee.query.filter(
            Employee.working_status == 'active',
            Employee.is_attendance_required == True
        ).all()

        summary = {
            "processed": 0,
            "new_absents": 0,
            "new_leaves": 0,
            "auto_fixed_checkin": 0,
            "auto_fixed_checkout": 0,
            "auto_closed_ot": 0
        }

        for employee in employees:
            attendance = Attendance.query.filter_by(
                employee_id=employee.id, 
                date=today
            ).first()

            # --- TH1: CHƯA CÓ BẢN GHI CHẤM CÔNG ---
            if not attendance:
                # 1.1 Kiểm tra đơn nghỉ phép (LeaveRequest) được duyệt
                leave_req = LeaveRequest.query.filter(
                    LeaveRequest.employee_id == employee.id,
                    LeaveRequest.status == LeaveStatus.APPROVED,
                    and_(LeaveRequest.from_date <= today, LeaveRequest.to_date >= today)
                ).first()

                new_record = Attendance(employee_id=employee.id, date=today, is_weekend=is_weekend, is_holiday=is_holiday)

                if leave_req:
                    # Lấy thông tin loại nghỉ để xem có tính lương không
                    l_type = LeaveType.query.get(leave_req.leave_type_id)
                    new_record.set_attendance_type(AttendanceType.LEAVE_APPROVED)
                    new_record.set_shift_status(AttendanceShiftStatus.COMPLETED)
                    # Nếu là loại nghỉ có lương (ANNUAL, PERSONAL...) thì tính 1 công
                    new_record.units = Decimal("1.00") if (l_type and l_type.is_paid) else Decimal("0.00")
                    new_record.regular_hours = Decimal("8.00")
                    summary["new_leaves"] += 1
                elif is_holiday:
                    new_record.set_shift_status(AttendanceShiftStatus.HOLIDAY_OFF)
                    new_record.set_attendance_type(AttendanceType.HOLIDAY)
                elif is_weekend:
                    new_record.set_shift_status(AttendanceShiftStatus.WEEKEND_OFF)
                    new_record.set_attendance_type(AttendanceType.WEEKEND)
                else:
                    new_record.set_shift_status(AttendanceShiftStatus.ABSENT)
                    new_record.set_attendance_type(AttendanceType.ABSENT)
                    new_record.units = Decimal("0.00")
                    summary["new_absents"] += 1
                
                db.session.add(new_record)
                summary["processed"] += 1
                continue

            # --- TH2: ĐÃ CÓ BẢN GHI NHƯNG CHƯA KẾT THÚC (QUÊN QUẸT THẺ) ---
            if attendance.is_flow_terminal:
                continue

            # A. Xử lý "Ca gãy" - Quên quẹt một trong hai đầu
            if not attendance.check_in and attendance.check_out:
                # Quên check-in: Bù bằng giờ bắt đầu chuẩn
                attendance.check_in = datetime.combine(today, WorkConfig.WORKDAY_START).replace(tzinfo=VN_TIMEZONE)
                attendance.note = (attendance.note or "") + " [Hệ thống tự động bù Check-in]"
                summary["auto_fixed_checkin"] += 1

            if attendance.check_in and not attendance.check_out:
                # Quên check-out: Bù bằng giờ kết thúc chuẩn
                attendance.check_out = datetime.combine(today, WorkConfig.WORKDAY_END).replace(tzinfo=VN_TIMEZONE)
                attendance.note = (attendance.note or "") + " [Hệ thống tự động bù Check-out]"
                summary["auto_fixed_checkout"] += 1

            # B. Cập nhật số công (units) và giờ làm việc chính thức qua Service
            if attendance.check_in and attendance.check_out:
                work_dto = attendance_calculation_service.calculate_regular_work_units(attendance)
                attendance.units = work_dto.units
                attendance.regular_hours = work_dto.worked_hours
                attendance.late_minutes = work_dto.late_minutes
                attendance.early_leave_minutes = work_dto.early_leave_minutes

            # C. Xử lý quên Check-out Tăng ca (OT)
            if attendance.overtime_check_in and not attendance.overtime_check_out:
                attendance.overtime_check_out = datetime.combine(today, WorkConfig.OT_END).replace(tzinfo=VN_TIMEZONE)
                
                raw_ot_hours = attendance_calculation_service.calculate_overtime_hours_raw(
                    attendance.overtime_check_in, attendance.overtime_check_out
                )
                
                # Tìm đơn OT để lấy hệ số multiplier
                approved_ot = OvertimeRequest.query.filter(
                    OvertimeRequest.employee_id == employee.id,
                    OvertimeRequest.overtime_date == today,
                    OvertimeRequest.status == "approved"
                ).first()

                multiplier = Decimal(str(approved_ot.holiday_multiplier)) if approved_ot else \
                             attendance_calculation_service._day_multiplier(is_holiday, is_weekend)
                
                attendance.overtime_hours = (raw_ot_hours * multiplier).quantize(Decimal("0.01"))
                summary["auto_closed_ot"] += 1

            # D. Tổng hợp và chốt trạng thái
            attendance.working_hours = (attendance.regular_hours or 0) + (attendance.overtime_hours or 0)
            attendance.set_shift_status(AttendanceShiftStatus.COMPLETED)
            summary["processed"] += 1

        db.session.commit()
        return {"status": "success", "date": today.isoformat(), "summary": summary}