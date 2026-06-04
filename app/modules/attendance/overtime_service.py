from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from operator import or_
from sqlalchemy.orm import joinedload
from app.constants.holidays import VN_FIXED_PUBLIC_HOLIDAYS, HolidayConfig
from app.constants.overtime import OvertimeConfig
from app.extensions.db import db

from app.models.history import HistoryLog
from app.models.notification import Notification
from app.models.overtime_request import OvertimeRequest
from app.models.employee import Employee
from app.models.department import Department    

from app.models.attendance import Attendance, AttendanceShiftStatus
from app.common.exceptions import ValidationError
from app.models.role import Role
from app.models.user import User
from app.modules.attendance.attendance_workflow_service import Attendance_workflow_service
from app.modules.attendance.attendance_query_service import AttendanceCommandService
from app.utils.time import (
    get_current_time,
    VN_TIMEZONE,
)


class OvertimeService:
    @staticmethod
    def _get_subordinates(manager_id: int) -> list[Employee]:
        """
        Lấy toàn bộ nhân viên thuộc (các) phòng ban mà manager này quản lý.
        Ràng buộc: Chỉ lấy nhân viên trong cùng phòng ban.
        """
        manager = Employee.query.get(manager_id)
        if not manager or manager.is_deleted:
            return []
        managed_depts = manager.managed_department
        if not managed_depts:
            return []
        if not isinstance(managed_depts, list):
            managed_depts = [managed_depts]
        all_subordinates = []
        for dept in managed_depts:
            if hasattr(dept, 'employees'):
                emps = [
                    e for e in dept.employees 
                    if e.id != manager_id and not e.is_deleted
                ]
                all_subordinates.extend(emps)
        return all_subordinates
    
    @classmethod
    def get_overtime_requests(cls, manager_id: int) -> list[dict]:
        """
        Lấy danh sách các đơn tăng ca đang chờ duyệt của cấp dưới.
        """
        # 1. Lấy danh sách nhân viên cấp dưới thông qua hàm helper của class
        subordinates = cls._get_subordinates(manager_id)
        sub_ids = [e.id for e in subordinates]
        
        if not sub_ids:
            return []

        # 2. Truy vấn các đơn "pending" của nhóm nhân viên này
        rows = OvertimeRequest.query.options(
            joinedload(OvertimeRequest.employee)
        ).filter(
            OvertimeRequest.employee_id.in_(sub_ids),
            OvertimeRequest.status == "pending",
            OvertimeRequest.is_deleted.is_(False)
        ).order_by(OvertimeRequest.overtime_date.desc()).all()

        # 3. Mapping dữ liệu trả về cho Frontend
        return [
            {
                "id": x.id,
                "employee_id": x.employee_id,
                "employee_name": x.employee.full_name if x.employee else "--",
                "overtime_date": x.overtime_date.isoformat() if x.overtime_date else None,
                "requested_hours": float(x.requested_hours or 0),
                "overtime_hours": float(x.overtime_hours or 0),
                "reason": x.reason,
                "note": x.note,
                "status": x.status,
                "is_holiday_ot": x.is_holiday_ot,
                "created_at": x.created_at.isoformat() if x.created_at else None
            }
            for x in rows
        ]

    @staticmethod
    def _get_subordinates(manager_id: int) -> list[Employee]:
        """
        Lấy toàn bộ nhân viên thuộc (các) phòng ban mà manager này quản lý.
        """
        manager = Employee.query.get(manager_id)
        if not manager or manager.is_deleted:
            return []
        managed_depts = manager.managed_department
        if not managed_depts:
            return []
            
        if not isinstance(managed_depts, list):
            managed_depts = [managed_depts]
            
        all_subordinates = []
        for dept in managed_depts:
            if hasattr(dept, 'employees'):
                # Lọc nhân viên không phải chính manager và không bị xóa
                emps = [
                    e for e in dept.employees 
                    if e.id != manager_id and not e.is_deleted
                ]
                all_subordinates.extend(emps)
        return all_subordinates

    @staticmethod
    def _get_users_by_role(role_name: str) -> list[User]:
        """
        Lấy danh sách các User đang hoạt động dựa theo tên Quyền (Role Name).
        Phục vụ cho việc tìm người nhận thông báo hệ thống.
        """
        if not role_name:
            return []
        normalized = role_name.strip().lower()
        return User.query.join(User.role).filter(
            db.func.lower(Role.name) == normalized,
            User.is_active.is_(True),
            User.is_deleted.is_(False)  
        ).all()

    @classmethod
    def create_overtime_request(
        cls, 
        user_id: int, 
        payload: dict, 
        actor_user_id: int | None = None
    ) -> dict:
        """
        Hàm duy nhất xử lý đăng ký tăng ca (OT). Tự động nhận diện ngày lễ/cuối tuần,
        tự động tính số giờ đăng ký, đồng bộ hóa trạng thái Chấm công và gửi thông báo cho Quản lý.
        """
        emp = Employee.query.filter_by(user_id=user_id, is_deleted=False).first()
        if not emp:
            raise ValueError("Không tìm thấy hồ sơ nhân viên hợp lệ.")

        # 2. Xử lý và chuẩn hóa ngày đăng ký OT
        now_dt = get_current_time()
        ot_date_raw = payload.get("overtime_date")
        if ot_date_raw:
            ot_date = date.fromisoformat(str(ot_date_raw).strip())
        else:
            ot_date = now_dt.date()
        existing_request = OvertimeRequest.query.filter(
            OvertimeRequest.employee_id == emp.id,
            OvertimeRequest.overtime_date == ot_date,
            OvertimeRequest.is_deleted.is_(False)
        ).first()
        if existing_request:
            raise ValueError(f"Nhân viên đã tồn tại đơn đăng ký tăng ca vào ngày {ot_date.strftime('%d/%m/%Y')}.")

        # 4. Kiểm tra Ngày lễ / Cuối tuần để áp Hệ số lương (Multiplier)
        is_holiday = False
        holiday_name = ""
        
        # Check ngày lễ cố định
        md_key = ot_date.strftime("%m-%d")
        if md_key in VN_FIXED_PUBLIC_HOLIDAYS:
            is_holiday = True
            holiday_name = VN_FIXED_PUBLIC_HOLIDAYS[md_key]
        else:
            # Check ngày lễ âm lịch qua bộ đệm cache
            lunar_holidays = HolidayConfig.get_lunar_holidays(ot_date.year)
            if md_key in lunar_holidays:
                is_holiday = True
                holiday_name = lunar_holidays[md_key]

        is_weekend = ot_date.weekday() >= 5  # Thứ 7 = 5, Chủ Nhật = 6

        # Xác định khung loại hình tăng ca và lấy hệ số từ OvertimeConfig
        if is_holiday:
            type_key = "holiday"
            default_reason = f"Tăng ca vào ngày lễ công cộng: {holiday_name}"
        elif is_weekend:
            type_key = "weekend"
            default_reason = "Tăng ca vào ngày nghỉ cuối tuần"
        else:
            type_key = "after_shift"
            default_reason = "Tăng ca sau giờ làm việc hành chính"

        multiplier = OvertimeConfig.MULTIPLIERS.get(type_key, Decimal("1.00"))

        # 5. Xử lý mốc thời gian Start/End dựa trên múi giờ Việt Nam (VN_TIMEZONE)
        try:
            start_time_obj = time.fromisoformat(payload.get("start_time", "18:00").strip())
            end_time_obj = time.fromisoformat(payload.get("end_time", "22:00").strip())
        except (ValueError, TypeError):
            raise ValueError("Định dạng giờ bắt đầu hoặc giờ kết thúc không hợp lệ (Chuẩn phải là HH:MM).")

        start_ot_time = datetime.combine(ot_date, start_time_obj, tzinfo=VN_TIMEZONE)
        end_ot_time = datetime.combine(ot_date, end_time_obj, tzinfo=VN_TIMEZONE)

        if end_ot_time <= start_ot_time:
            raise ValueError("Thời gian kết thúc ca tăng ca phải sau thời gian bắt đầu ca.")

        if type_key == "after_shift":
            official_pay_start = datetime.combine(ot_date, OvertimeConfig.OFFICIAL_PAY_START_TIME, tzinfo=VN_TIMEZONE)
            calculation_start = max(start_ot_time, official_pay_start)
        else:
            calculation_start = start_ot_time

        billable_seconds = max((end_ot_time - calculation_start).total_seconds(), 0)
        calculated_hours = Decimal(str(billable_seconds / 3600)).quantize(Decimal("0.01"))

        if calculated_hours <= 0:
            raise ValueError("Khoảng thời gian đăng ký chưa đạt mốc tối thiểu để tính công làm thêm.")

        # 7. Khởi tạo thực thể đơn đăng ký OvertimeRequest mới
        reason = str(payload.get("reason", "")).strip() or default_reason
        note = str(payload.get("note", "")).strip() or None

        new_request = OvertimeRequest(
            employee_id=emp.id,
            overtime_date=ot_date,
            requested_hours=calculated_hours,
            overtime_hours=Decimal("0.00"),  # Thực tế tích lũy khi check-out ca làm việc
            start_ot_time=start_ot_time,
            end_ot_time=end_ot_time,
            reason=reason,
            note=note,
            is_holiday_ot=is_holiday,
            holiday_multiplier=multiplier,
            status="pending",
            created_at=now_dt,
            updated_at=now_dt
        )
        db.session.add(new_request)
        db.session.flush()  # Sinh ID tạm thời cho đơn nhằm phục vụ log lịch sử

        # 8. Đồng bộ hóa logic trạng thái của bảng Chấm công (Attendance) trong ngày
        attendance_record = Attendance.query.filter_by(employee_id=emp.id, date=ot_date).first()
        if attendance_record:
            # Nếu nhân viên đã hoàn thành ca chính, chuyển sang trạng thái chờ quyết định duyệt OT để mở luồng check-in ca làm thêm
            if attendance_record.normalized_shift_status == AttendanceShiftStatus.REGULAR_DONE:
                attendance_record.set_shift_status(AttendanceShiftStatus.REGULAR_DONE_PENDING_OT_DECISION)

        # 9. Phát thông báo hệ thống (Notification) tới toàn bộ cấp quản lý quản trị
        managers = cls._get_users_by_role("manager")
        for manager in managers:
            db.session.add(Notification(
                user_id=manager.id,
                title="🔔 Đơn đăng ký tăng ca mới",
                content=f"Nhân viên {emp.full_name} đã tạo đơn đăng ký tăng ca vào ngày {ot_date.strftime('%d/%m/%Y')} ({calculated_hours} giờ).",
                type="overtime",
                link=f"/manager/overtime-requests?id={new_request.id}",
                is_read=False,
                created_at=now_dt,
                updated_at=now_dt
            ))

        db.session.add(HistoryLog(
            employee_id=emp.id,
            action="OVERTIME_REQUEST_CREATED",
            entity_type="overtime_requests",
            entity_id=new_request.id,
            description=f"Đăng ký tăng ca ngày {ot_date} từ {start_time_obj.strftime('%H:%M')} đến {end_time_obj.strftime('%H:%M')} (Hệ số x{multiplier})",
            performed_by=actor_user_id or user_id
        ))
        db.session.commit()

        return {
            "success": True,
            "message": "Gửi đơn đăng ký tăng ca thành công, đang chờ Quản lý phê duyệt.",
            "data": {
                "request_id": new_request.id,
                "employee_id": emp.id,
                "overtime_date": str(ot_date),
                "requested_hours": float(calculated_hours),
                "multiplier": float(multiplier),
                "status": new_request.status
            }
        }
    
    @staticmethod
    def approve_overtime(
        request_id: int,
        approver_id: int,
        approved_hours: float | Decimal | None = None,
    ) -> dict:
        # 1. Kiểm tra đơn tăng ca có tồn tại không
        ot_req = db.session.get(OvertimeRequest, request_id)
        if not ot_req:
            raise ValidationError("Không tìm thấy đơn tăng ca.")
            
        if (ot_req.status or "").strip().lower() != "pending":
            raise ValidationError(f"Đơn này không ở trạng thái chờ duyệt (Hiện tại: {ot_req.status})")

        # 2. 🛡️ KIỂM TRA ĐIỀU KIỆN PHÒNG BAN ĐÚNG MODEL
        # Lấy thông tin nhân viên làm đơn
        subordinate = db.session.get(Employee, ot_req.employee_id)
        if not subordinate:
            raise ValidationError("Không tìm thấy thông tin nhân viên làm đơn.")
            
        if not subordinate.department_id:
            raise ValidationError("Nhân viên tạo đơn hiện không thuộc bất kỳ phòng ban nào.")

        # Lấy thông tin phòng ban của nhân viên đó dựa theo department_id
        dept = db.session.get(Department, subordinate.department_id)
        
        # Kiểm tra xem manager_id của phòng ban đó có khớp với ID của người duyệt hay không
        if not dept or dept.manager_id != approver_id:
            raise ValidationError("Bạn không có quyền phê duyệt đơn của nhân viên thuộc phòng ban khác.")

        # 3. Ép kiểu dữ liệu Decimal cho số giờ phê duyệt
        now_dt = get_current_time()
        if approved_hours is None:
            approved_hours = Decimal(str(ot_req.requested_hours or 0))
        else:
            approved_hours = Decimal(str(approved_hours))
            
        approved_hours = approved_hours.quantize(Decimal("0.01"))
        if approved_hours < Decimal("0"):
            raise ValidationError("Số giờ duyệt không hợp lệ.")

        # 4. Tiến hành cập nhật trạng thái và ghi vết (Audit Trail)
        ot_req.status = "approved" 
        ot_req.approved_by = approver_id
        ot_req.approved_at = now_dt
        ot_req.hr_decision_by = approver_id
        ot_req.hr_decision_at = now_dt
        ot_req.approved_hours = approved_hours
        
        # Kích hoạt cập nhật bảng chấm công
        from app.modules.attendance.attendance_workflow_service import Attendance_workflow_service
        Attendance_workflow_service.handle_ot_approved(ot_req)
        
        db.session.commit()
        
        return {
            "message": "Đã duyệt đơn tăng ca thành công.",
            "request_id": ot_req.id,
            "overtime_status": ot_req.status,
            "approved_hours": str(ot_req.approved_hours),
            "approved_at": ot_req.approved_at.isoformat() if ot_req.approved_at else None,
            "server_time": now_dt.isoformat(),
        }

    @staticmethod
    def reject_overtime(
        request_id: int,
        reject_reason: str = "",
        approver_id: int | None = None,
    ) -> dict:
        ot_req = db.session.get(OvertimeRequest, request_id)
        if not ot_req:
            raise ValidationError("Không tìm thấy đơn tăng ca.")
        if approver_id:
            subordinate = db.session.get(Employee, ot_req.employee_id)
            if not subordinate:
                raise ValidationError("Không tìm thấy thông tin nhân viên làm đơn.")
                
            if not subordinate.department_id:
                raise ValidationError("Nhân viên tạo đơn hiện không thuộc bất kỳ phòng ban nào.")
            dept = db.session.get(Department, subordinate.department_id)
            if not dept or dept.manager_id != approver_id:
                raise ValidationError("Bạn không có quyền từ chối đơn của nhân viên thuộc phòng ban khác.")

        current_status = (ot_req.status or "").strip().lower()
        valid_pending_states = {"pending", "pending_hr", "pending_admin"}
        
        if current_status not in valid_pending_states:
            raise ValidationError(
                f"Đơn này đã được xử lý hoặc không ở trạng thái chờ duyệt. (Hiện tại: {ot_req.status})"
            )
            
        now_dt = get_current_time()
        reject_reason = (reject_reason or "").strip()
        ot_req.status = "rejected"  
        ot_req.rejection_reason = reject_reason if reject_reason else "Từ chối yêu cầu tăng ca."
        ot_req.approved_by = approver_id
        ot_req.approved_at = now_dt
        ot_req.hr_decision_by = approver_id
        ot_req.hr_decision_at = now_dt
        ot_req.hr_note = (
            f"Từ chối với lý do: {reject_reason}"
            if reject_reason
            else "Từ chối yêu cầu tăng ca."
        )
        Attendance_workflow_service.handle_ot_rejected(ot_req, reason=reject_reason)
        
        db.session.commit()
        
        return {
            "message": "Đã từ chối đơn tăng ca.",
            "request_id": ot_req.id,
            "overtime_status": ot_req.status,
            "rejection_reason": ot_req.rejection_reason,
            "processed_at": now_dt.isoformat(),
            "server_time": now_dt.isoformat(),
        }

    @staticmethod
    def can_start_ot(
        employee_id: int,
        target_date: date,
    ) -> bool:
        attendance = Attendance.query.filter_by(
            employee_id=employee_id,
            date=target_date,
        ).first()
        
        if not attendance:
            raise ValidationError("Chưa có dữ liệu chấm công ngày hôm nay.")
        current_state = attendance.normalized_shift_status
        allowed_states = {
            Attendance.ShiftStatus.REGULAR_DONE,
            Attendance.ShiftStatus.OT_CHECKIN_REQUIRED,
            Attendance.ShiftStatus.REGULAR_DONE_PENDING_OT_DECISION,
            Attendance.ShiftStatus.PRE_OT_REST,
        }
        if current_state not in allowed_states:
            if not attendance.check_out:
                raise ValidationError(
                    "Bạn chưa checkout ca hành chính. Vui lòng hoàn thành ca chính trước."
                )
            raise ValidationError(
                f"Trạng thái hiện tại ({attendance.shift_status_label}) không cho phép bắt đầu OT."
            )
        if attendance.overtime_check_in:
            raise ValidationError("Bạn đã thực hiện check-in tăng ca trước đó rồi.")
            
        if attendance.overtime_check_out:
            raise ValidationError("Bạn đã hoàn thành tăng ca hôm nay.")
        approved_ot = AttendanceCommandService._get_approved_ot(
            employee_id=employee_id,
            target_date=target_date,
        )
        
        if not approved_ot:
            raise ValidationError("Bạn không có đơn tăng ca được phê duyệt cho hôm nay.")
        return True

    @staticmethod
    def cancel_and_reset_overtime_flow(
        *, 
        overtime_request: OvertimeRequest, 
        actor_user_id: int | None = None, 
        source: str = "system", 
        anchor_notification_id: int | None = None
    ) -> dict:
        """
        Hủy tất cả yêu cầu OT trong ngày và khôi phục trạng thái chấm công về ban đầu.
        Sử dụng khi Admin từ chối hàng loạt hoặc Reset dữ liệu lỗi.
        """
        overtime_date = overtime_request.overtime_date
        employee = Employee.query.get(overtime_request.employee_id)
        user_id = employee.user_id if employee else None
        now_ts = get_current_time()

        # 1. Tìm tất cả các yêu cầu OT cùng ngày chưa bị xóa
        same_day_requests = OvertimeRequest.query.filter_by(
            employee_id=overtime_request.employee_id,
            overtime_date=overtime_date,
            is_deleted=False,
        ).all()
        
        request_ids = [row.id for row in same_day_requests]
        notification_ids: set[int] = set()

        if anchor_notification_id is not None:
            notification_ids.add(anchor_notification_id)

        # 2. Xử lý xóa thông báo (Đã sửa token để khớp với link trong hàm create)
        if user_id and request_ids:
            for req_id in request_ids:
                exact_tokens = (
                    f"overtime_request:{req_id}",
                    f"/overtime/{req_id}",
                    f"/manager/overtime-requests?id={req_id}", # Khớp với hàm create_overtime_request
                )
                linked = Notification.query.filter(
                    Notification.user_id == user_id,
                    Notification.is_deleted.is_(False),
                    or_(*[Notification.link == token for token in exact_tokens]),
                ).all()
                for row in linked:
                    notification_ids.add(row.id)

        deleted_notifications = 0
        for notification_id in notification_ids:
            noti = Notification.query.filter_by(id=notification_id, is_deleted=False).first()
            if not noti: continue
            noti.is_deleted = True
            noti.updated_at = now_ts
            deleted_notifications += 1

        # 3. Khôi phục bảng Attendance (Sử dụng Constants từ Attendance Model)
        attendance = Attendance.query.filter_by(
            employee_id=overtime_request.employee_id,
            date=overtime_date,
        ).first()

        before_attendance = {}
        after_attendance = {}

        if attendance:
            before_attendance = {
                "attendance_type": attendance.attendance_type,
                "overtime_hours": str(attendance.overtime_hours),
                "working_hours": str(attendance.working_hours),
                "shift_status": attendance.shift_status
            }

            # Reset các trường OT về 0
            attendance.overtime_hours = Decimal("0.00")
            attendance.overtime_check_in = None
            attendance.overtime_check_out = None
            
            # Tính lại tổng giờ làm việc (chỉ còn giờ hành chính)
            regular_hours = Decimal(str(attendance.regular_hours or 0))
            attendance.working_hours = regular_hours.quantize(Decimal("0.01"))

            # Trả trạng thái về đúng bản chất ngày hôm đó
            if attendance.is_holiday:
                attendance.set_attendance_type(Attendance.Type.HOLIDAY)
                attendance.set_shift_status(Attendance.ShiftStatus.HOLIDAY_OFF)
            elif attendance.is_weekend:
                attendance.set_attendance_type(Attendance.Type.WEEKEND)
                attendance.set_shift_status(Attendance.ShiftStatus.WEEKEND_OFF)
            else:
                attendance.set_attendance_type(Attendance.Type.NORMAL)
                if attendance.check_in and attendance.check_out:
                    attendance.set_shift_status(Attendance.ShiftStatus.REGULAR_DONE)
                elif attendance.check_in:
                    attendance.set_shift_status(Attendance.ShiftStatus.WORKING_REGULAR)
                else:
                    attendance.set_shift_status(Attendance.ShiftStatus.NOT_STARTED)

            after_attendance = {
                "attendance_type": attendance.attendance_type,
                "overtime_hours": str(attendance.overtime_hours),
                "working_hours": str(attendance.working_hours),
                "shift_status": attendance.shift_status
            }

        # 4. Hủy các yêu cầu OT (Trạng thái cancelled)
        deleted_requests = 0
        for row in same_day_requests:
            row.is_deleted = True
            row.status = "cancelled"
            row.updated_at = now_ts
            deleted_requests += 1

        # 5. Ghi Log lịch sử OT_RESET
        db.session.add(
            HistoryLog(
                employee_id=overtime_request.employee_id,
                action="OT_RESET",
                entity_type="overtime_request",
                entity_id=overtime_request.id,
                description=(
                    f"Reset OT flow from {source} | date={overtime_date.isoformat()} "
                    f"| old_state={before_attendance} | new_state={after_attendance} "
                    f"| requests_cancelled={deleted_requests}"
                ),
                performed_by=actor_user_id,
                created_at=now_ts
            )
        )

        db.session.commit()
        return {
            "success": True,
            "deleted_requests": deleted_requests,
            "deleted_notifications": deleted_notifications,
            "overtime_date": overtime_date.isoformat(),
        }