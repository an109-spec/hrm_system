from datetime import date, timedelta
from unittest import result

from flask import url_for
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.routing import ValidationError

from app.constants.leave import LEAVE_TYPE_CONFIGS, LeaveStatus
from app.utils.time import _normalize, get_current_time
from app.extensions.db import db

from app.models.leave import LeaveRequest
from app.models.leave_usage import EmployeeLeaveUsage
from app.models.notification import Notification
from app.models.employee import Employee
from sqlalchemy.orm import joinedload

from app.utils.upload_service import UploadService 
from .dto import LeaveRequestDTO
from .validators import LeaveValidator

class LeaveService:
    '''
    xem còn bao nhiêu phép/ năm -> nếu chưa có thì tạo mới 
    '''
    @staticmethod
    def get_leave_balance(employee_id: int, year: int = None) -> EmployeeLeaveUsage:
        if year is None:
            year = get_current_time().year
        usage = EmployeeLeaveUsage.query.filter_by(
            employee_id=employee_id,
            year=year
        ).first()
        if usage:
            return usage
        # 2. Nếu không tìm thấy, chuẩn bị tạo mới
        annual_config = LEAVE_TYPE_CONFIGS.get("ANNUAL", {})
        default_days = annual_config.get("default_days", 12)

        new_usage = EmployeeLeaveUsage(
            employee_id=employee_id,
            year=year,
            total_days=default_days,
            used_days=0,
            remaining_days=default_days
        )

        try:
            db.session.add(new_usage)
            db.session.commit()
            return new_usage
        except IntegrityError:
            # 3. Xử lý Race Condition: Nếu có request khác đã tạo trước 1 tích tắc
            db.session.rollback()
            # Truy vấn lại bản ghi mà request kia đã vừa tạo thành công
            return EmployeeLeaveUsage.query.filter_by(
                employee_id=employee_id,
                year=year
            ).one()

    @staticmethod
    def update_usage_after_approve(employee_id: int, days: int, year: int):
        """
        Cập nhật số ngày phép đã sử dụng sau khi đơn được duyệt.
        Đảm bảo tính nhất quán của dữ liệu bằng cách sử dụng Transaction.
        """
        if days <= 0:
            raise ValueError("Số ngày nghỉ cần cập nhật phải là số dương.")
        try:
            usage = LeaveService.get_leave_balance(employee_id, year)
            usage.used_days += days
            usage.update_balance() 
            db.session.commit()
            return usage
        except SQLAlchemyError as e:
            db.session.rollback()
            raise Exception("Lỗi hệ thống khi cập nhật số dư phép. Vui lòng thử lại sau.") from e

    @staticmethod
    def create_leave_request(dto: LeaveRequestDTO):
        now = get_current_time()
        usage = LeaveService.get_leave_balance(dto.employee_id, now.year)
        LeaveValidator.validate(dto, usage.remaining_days)
        leave = LeaveRequest(
            employee_id=dto.employee_id,
            leave_type_id=dto.leave_type_id,
            from_date=dto.from_date,
            to_date=dto.to_date,
            reason=dto.reason,
            status=LeaveStatus.PENDING,
            approved_by=dto.approved_by,
            document_url=dto.document_url,
            subtype=dto.subtype,
            relation=dto.relation
        )
        db.session.add(leave)
        
        employee = Employee.query.get(dto.employee_id)
        if employee and employee.manager_id:
            manager = Employee.query.get(employee.manager_id)
            if manager and manager.user_id:
                target_link = url_for('leave_bp.leave_approval_list', _external=False)

                db.session.add(Notification(
                    user_id=manager.user_id,
                    title="Đơn xin nghỉ phép mới",
                    content=f"Nhân viên {employee.full_name} gửi đơn nghỉ {dto.requested_days} ngày.",
                    type="leave",
                    link=target_link
                ))

        db.session.commit()
        return leave

    @staticmethod
    def get_my_requests(employee_id: int):
        """
        Lấy toàn bộ lịch sử đơn xin nghỉ phép của nhân viên,
        bao gồm cả các đơn đã hủy hoặc đã bị xóa mềm (nếu cần).
        """
        return (
            LeaveRequest.query
            .options(
                joinedload(LeaveRequest.leave_type), # Load tên loại nghỉ
                joinedload(LeaveRequest.approver)    # Load thông tin người duyệt
            )
            .filter(
                LeaveRequest.employee_id == employee_id
                # Đã xóa dòng filter(LeaveRequest.is_deleted == False) 
                # để lấy tất cả bản ghi
            )
            .order_by(LeaveRequest.created_at.desc()) # Đơn mới nhất lên đầu
            .all()
        )
    
    @staticmethod
    def cancel_request(leave_id: int, employee_id: int):
        """
        Hủy đơn xin nghỉ phép. 
        """
        # 1. Lấy đơn
        leave = LeaveRequest.query.filter_by(
            id=leave_id,
            employee_id=employee_id,
            is_deleted=False
        ).first()
        if not leave:
            raise ValueError("❌ Không tìm thấy đơn xin nghỉ phép hợp lệ.")
        # 2. Sử dụng Constant từ file app/constants/leave.py
        allow_cancel_statuses = [
            LeaveStatus.PENDING, 
            LeaveStatus.PENDING_HR, 
            LeaveStatus.PENDING_ADMIN, 
            LeaveStatus.SUPPLEMENT_REQUESTED
        ]
        if leave.status not in allow_cancel_statuses:
            # Dùng get_label để thông báo lỗi rõ nghĩa hơn (VD: "Đã duyệt" thay vì "approved")
            current_label = LeaveStatus.get_label(leave.status)
            raise ValueError(f"❌ Không thể hủy đơn ở trạng thái: '{current_label}'.")
        # 3. Cập nhật trạng thái
        leave.status = LeaveStatus.CANCELLED
        # Commit
        db.session.commit()
        return leave
    
    @staticmethod
    def _approved_leave_dates(employee_id: int, start: date, end: date) -> set[date]:
        """
        Lấy danh sách các ngày đã được duyệt nghỉ phép của một nhân viên.
        Sử dụng để kiểm tra trùng lặp thời gian khi đăng ký mới.
        """
        approved = LeaveRequest.query.filter(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status == LeaveStatus.APPROVED,
            LeaveRequest.is_deleted == False,          
            LeaveRequest.from_date <= end,
            LeaveRequest.to_date >= start,
        ).all()
        result: set[date] = set()
        for item in approved:
            current = max(item.from_date, start)
            edge = min(item.to_date, end)
            while current <= edge:
                result.add(current)
                current += timedelta(days=1)
        return result
    
    @staticmethod
    def _save_leave_document(file_storage, category: str, user_id: int, entity_id: int) -> str:
        """
        Sử dụng UploadService để lưu file và ghi lại vào database.
        """
        if not file_storage or not file_storage.filename:
            raise ValidationError("Vui lòng tải lên giấy tờ đính kèm.")
        filename = file_storage.filename
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        allowed_ext = {"pdf", "png", "jpg", "jpeg"}
        if ext not in allowed_ext:
            raise ValidationError(f"Định dạng .{ext} không hợp lệ. Chỉ chấp nhận PDF hoặc ảnh.")
        entity_type = f"leave_{category.lower()}"
        try:
            file_record = UploadService.save_file(
                file=file_storage,
                user_id=user_id,
                entity_type=entity_type,
                entity_id=entity_id
            )
            return file_record.file_url 
        except Exception as e:
            raise ValidationError(str(e))

    @staticmethod
    def get_department_leave_requests(department_id: int, start_date: date, end_date: date):
        """
        Lấy danh sách đơn nghỉ phép của toàn bộ nhân viên trong phòng ban
        trong khoảng thời gian từ start_date đến end_date.
        """
        return (
            LeaveRequest.query
            .join(Employee, LeaveRequest.employee_id == Employee.id)
            .filter(
                Employee.department_id == department_id,
                LeaveRequest.is_deleted == False,
                # Điều kiện kiểm tra giao thoa thời gian
                LeaveRequest.from_date <= end_date,
                LeaveRequest.to_date >= start_date
            )
            .options(
                joinedload(LeaveRequest.employee), # Load thông tin nhân viên để hiện tên
                joinedload(LeaveRequest.leave_type) # Load thông tin loại nghỉ
            )
            .order_by(LeaveRequest.from_date.asc())
            .all()
        )

    @staticmethod
    def get_team_leave_requests(manager_id: int, start_date: date, end_date: date):
        """
        Lấy danh sách đơn nghỉ phép của nhân viên cấp dưới trực tiếp (Team).
        """
        return (
            LeaveRequest.query
            .join(Employee, LeaveRequest.employee_id == Employee.id)
            .filter(
                Employee.manager_id == manager_id,
                LeaveRequest.is_deleted == False,
                LeaveRequest.from_date <= end_date,
                LeaveRequest.to_date >= start_date
            )
            .options(
                joinedload(LeaveRequest.employee),
                joinedload(LeaveRequest.leave_type)
            )
            .order_by(LeaveRequest.from_date.asc())
            .all()
        )
    
    @staticmethod
    def get_pending_requests_for_manager(manager_id: int):
        """
        Lấy danh sách các đơn nghỉ phép ĐANG CHỜ DUYỆT của nhân viên cấp dưới.
        Sắp xếp theo đơn mới nhất lên đầu để Manager ưu tiên xử lý.
        """
        return (
            LeaveRequest.query
            .join(Employee, LeaveRequest.employee_id == Employee.id)
            .filter(
                Employee.manager_id == manager_id,
                LeaveRequest.is_deleted == False,
                # Lấy các đơn đang chờ Manager 
                LeaveRequest.status.in_([LeaveStatus.PENDING])
            )
            .options(
                joinedload(LeaveRequest.employee),
                joinedload(LeaveRequest.leave_type)
            )
            # Sắp xếp theo ngày tạo (mới nhất lên đầu)
            .order_by(LeaveRequest.created_at.desc()) 
            .all()
        )
    
    @staticmethod
    def get_leave_request_for_manager(request_id: int, manager_id: int):
        """
        Lấy chi tiết đơn nghỉ phép cho Manager.
        Đảm bảo Manager chỉ xem được đơn của nhân viên thuộc cùng phòng ban.
        """
        # 1. Lấy thông tin Manager trước để biết phòng ban của họ
        manager = Employee.query.get(manager_id)
        if not manager or not manager.department_id:
            return None

        # 2. Lấy đơn nghỉ phép cùng với thông tin nhân viên và loại nghỉ
        leave_request = LeaveRequest.query.options(
            joinedload(LeaveRequest.employee),
            joinedload(LeaveRequest.leave_type)
        ).filter_by(id=request_id).first()

        # 3. Kiểm tra đơn tồn tại và thuộc phòng ban của Manager
        if not leave_request or leave_request.employee.department_id != manager.department_id:
            return None

        return leave_request
    
    @staticmethod
    def approve_leave_request(request_id: int, manager_id: int):
        """
        Duyệt đơn nghỉ phép cho nhân viên thuộc phòng ban của Manager.
        """
        # 1. Lấy đơn và thông tin Manager
        leave = LeaveRequest.query.get(request_id)
        manager = Employee.query.get(manager_id)
        if not leave:
            raise ValueError("Đơn nghỉ phép không tồn tại.")
        if not manager or leave.employee.department_id != manager.department_id:
            raise ValueError("Bạn không có quyền duyệt đơn của nhân viên ngoài phòng ban.")
        # 2. Kiểm tra trạng thái đơn
        if leave.status != LeaveStatus.PENDING:
            current_label = LeaveStatus.get_label(leave.status)
            raise ValueError(f"Không thể duyệt đơn đang ở trạng thái: '{current_label}'.")
        # 3. Tính số ngày nghỉ (giả định 1 ngày đơn giản, bạn có thể thay thế bằng hàm tính ngày công thực tế nếu có)
        delta = (leave.to_date - leave.from_date).days + 1
        try:
            # 4. Cập nhật trạng thái
            leave.status = LeaveStatus.APPROVED
            leave.approved_by = manager_id
            # 5. Trừ ngày phép
            LeaveService.update_usage_after_approve(leave.employee_id, delta, leave.from_date.year)
            # 6. Gửi thông báo cho nhân viên
            target_link = url_for('leave_bp.view_my_request', id=leave.id, _external=False)
            db.session.add(Notification(
                user_id=leave.employee.user_id,
                title="Đơn nghỉ phép đã được duyệt",
                content=f"Quản lý {manager.full_name} đã duyệt đơn nghỉ phép của bạn từ {leave.from_date} đến {leave.to_date}.",
                type="leave",
                link=target_link
            ))
            db.session.commit()
            return leave
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def reject_leave_request(request_id: int, manager_id: int, reason: str = None):
        """
        Từ chối đơn nghỉ phép và ghi nhận lý do từ chối.
        """
        # 1. Lấy đơn và thông tin Manager
        leave = LeaveRequest.query.get(request_id)
        manager = Employee.query.get(manager_id)

        if not leave:
            raise ValueError("Đơn nghỉ phép không tồn tại.")
        if not manager or leave.employee.department_id != manager.department_id:
            raise ValueError("Bạn không có quyền từ chối đơn của nhân viên ngoài phòng ban.")

        # 2. Kiểm tra trạng thái đơn (Chỉ cho phép từ chối nếu đơn đang ở trạng thái PENDING)
        if leave.status != LeaveStatus.PENDING:
            current_label = LeaveStatus.get_label(leave.status)
            raise ValueError(f"Không thể từ chối đơn đang ở trạng thái: '{current_label}'.")

        try:
            # 3. Cập nhật trạng thái
            leave.status = LeaveStatus.REJECTED
            leave.approved_by = manager_id
            
            # Ghi chú lý do từ chối vào trường reason của đơn (nếu có)
            if reason:
                leave.reason = f"{leave.reason}\n\n[Lý do từ chối]: {reason}"

            # 4. Gửi thông báo cho nhân viên
            target_link = url_for('leave_bp.view_my_request', id=leave.id, _external=False)
            db.session.add(Notification(
                user_id=leave.employee.user_id,
                title="Đơn nghỉ phép đã bị từ chối",
                content=f"Quản lý {manager.full_name} đã từ chối đơn nghỉ phép của bạn. {f'Lý do: {reason}' if reason else ''}",
                type="leave",
                link=target_link
            ))

            db.session.commit()
            return leave
        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def get_leave_request_detail(leave_id: int, employee_id: int) -> LeaveRequest:
        """
        Lấy chi tiết đơn nghỉ phép của nhân viên theo ID.
        Đảm bảo chỉ nhân viên sở hữu đơn mới có thể xem chi tiết.
        """
        leave = LeaveRequest.query.options(
            joinedload(LeaveRequest.leave_type), 
            joinedload(LeaveRequest.approver)    
        ).filter_by(
            id=leave_id, 
            employee_id=employee_id, 
            is_deleted=False
        ).first()
        if not leave:
            raise ValueError("Không tìm thấy đơn nghỉ phép hoặc bạn không có quyền xem đơn này.")
        return leave

    @staticmethod
    def get_active_leave_on_date(employee_id: int, target_date: date) -> LeaveRequest | None:
        """
        Lấy đơn nghỉ phép ĐÃ DUYỆT của nhân viên vào một ngày cụ thể.
        Đây là nơi duy nhất quản lý logic 'Đơn nghỉ phép hợp lệ'.
        """
        return LeaveRequest.query.filter(
            LeaveRequest.employee_id == employee_id,
            LeaveRequest.status == LeaveStatus.APPROVED, # Sử dụng hằng số chuẩn
            LeaveRequest.from_date <= target_date,
            LeaveRequest.to_date >= target_date,
            LeaveRequest.is_deleted.is_(False)
        ).first()
    
    '''
    hàm mới xây dựng 
    '''

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

    @staticmethod
    def get_leave_requests(manager_id: int, filters: dict | None = None) -> list[dict]:
        employees = LeaveService._get_subordinates(manager_id)
        sub_ids = [e.id for e in employees]
        filters = filters or {}
        if not sub_ids:
            query = LeaveRequest.query.filter(LeaveRequest.approved_by == manager_id)
        else:
            query = LeaveRequest.query.filter(
                or_(
                    LeaveRequest.employee_id.in_(sub_ids),
                    LeaveRequest.approved_by == manager_id,
                )
            )
        status = (filters.get("status") or "").strip()
        if status:
            query = query.filter(LeaveRequest.status == status)
        from_date = filters.get("from_date")
        if from_date:
            dt = _normalize(from_date)
            if dt: query = query.filter(LeaveRequest.from_date >= dt.date())
        to_date = filters.get("to_date")
        if to_date:
            dt = _normalize(to_date)
            if dt: query = query.filter(LeaveRequest.to_date <= dt.date())
        is_paid = filters.get("is_paid")
        if is_paid in {"true", "false"}:
            query = query.join(LeaveRequest.leave_type).filter(LeaveRequest.leave_type.has(is_paid=(is_paid == "true")))
        rows = query.order_by(LeaveRequest.created_at.desc()).all()
        if not rows:
            return []
        data = []
        emergency_keywords = ["khẩn", "emergency", "ốm", "tai nạn", "đột xuất"]
        f_name = (filters.get("employee_name") or "").strip().lower()
        f_code = (filters.get("employee_code") or "").strip()
        f_dept = (filters.get("department") or "").strip().lower()
        f_type = (filters.get("leave_type") or "").strip().lower()
        f_emergency = str(filters.get("emergency_only", "")).lower() in {"1", "true", "yes"}
        f_attachment = str(filters.get("has_attachment", "")).lower() in {"1", "true", "yes"}
        for l in rows:
            employee = l.employee
            if f_name and employee and f_name not in (employee.full_name or "").lower():
                continue
            if f_code and employee and f_code not in str(employee.id):
                continue
            if f_dept and employee and employee.department and f_dept not in (employee.department.name or "").lower():
                continue
            leave_type_name = l.leave_type.name if l.leave_type else "--"
            if f_type and f_type not in leave_type_name.lower():
                continue
            source = f"{l.reason or ''} {l.subtype or ''}".lower()
            is_emergency = any(kw in source for kw in emergency_keywords)
            if f_emergency and not is_emergency:
                continue
            if f_attachment and not l.document_url:
                continue
            data.append({
                "id": l.id,
                "employee_id": l.employee_id,
                "name": employee.full_name if employee else "--",
                "employee_code": employee.id if employee else "--",
                "department": employee.department.name if employee and employee.department else "--",
                "position": employee.position.job_title if employee and employee.position else "--",
                "type": leave_type_name,
                "from": l.from_date.isoformat(),
                "to": l.to_date.isoformat(),
                "status": l.status,
                "status_label": LeaveStatus.get_label(l.status), # Dùng class hằng số cũ
                "reason": l.reason or "",
                "is_paid": bool(l.leave_type.is_paid) if l.leave_type else True,
                "is_emergency": is_emergency,
                "attachment": l.document_url,
                "created_at": l.created_at.date().isoformat() if l.created_at else None,
                "days": (l.to_date - l.from_date).days + 1,
            })
        return data
    
    @staticmethod
    def get_leave_summary(manager_id: int) -> dict:
        today = get_current_time().date()
        start_year = date(today.year, 1, 1)
        rows = LeaveService.get_team_leave_requests(manager_id, start_year, today)
        
        # Tính toán
        return {
            "pending": len([x for x in rows if x.status == LeaveStatus.PENDING]),
            "today": len([x for x in rows if x.from_date <= today <= x.to_date]),
            "emergency": len([x for x in rows if any(kw in (f"{x.reason} {x.subtype}").lower() for kw in ["khẩn", "emergency", "ốm", "tai nạn", "đột xuất"])]),
            "approved": len([x for x in rows if x.status == LeaveStatus.APPROVED]),
            "rejected": len([x for x in rows if x.status == LeaveStatus.REJECTED]),
            "supplement_requested": len([x for x in rows if x.status == LeaveStatus.SUPPLEMENT_REQUESTED]),
        }