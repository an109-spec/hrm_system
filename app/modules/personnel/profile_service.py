from datetime import datetime

from app.constants.employee import EmploymentType, GenderType, WorkingStatus
from app.models.employee import Employee
from app.models.history import HistoryLog
from app.models.user import User
from app.common.exceptions import NotFoundError, UnauthorizedError
from app.extensions.db import db
from app.utils.upload_service import UploadService

class ProfileService:

    @staticmethod
    def get_profile(user_id=None, employee_id=None):
        if employee_id:
            emp = db.session.get(Employee, employee_id)
        elif user_id:
            user = db.session.get(User, user_id)
            emp = user.employee_profile if user else None
        else:
            raise ValueError("Phải cung cấp user_id hoặc employee_id")
        if not emp:
            raise NotFoundError("Không tìm thấy thông tin nhân viên")
        return {
            "basic": {
                "id": emp.id,
                "full_name": emp.full_name,
                "avatar": emp.avatar,
                "gender": {
                    "value": emp.gender,
                    "label": GenderType.get_label(emp.gender)
                },
                "dob": emp.dob.strftime("%d/%m/%Y") if emp.dob else None,
                "age": emp.age,
                "phone": emp.phone,
                "address": emp.address,
                "address_detail": {
                    "province": emp.province_id,
                    "district": emp.district_id,
                    "ward": emp.ward_id,
                    "street": emp.address_detail
                },
                "email": emp.user.email if emp.user else None,
            },
            "job": {
                "department": emp.department.name if emp.department else None,
                "position": emp.position.job_title if emp.position else None,
                "manager": emp.manager.full_name if emp.manager else None,
                "hire_date": emp.hire_date.strftime("%d/%m/%Y") if emp.hire_date else None,
                "employment_type": {
                    "value": emp.employment_type,
                    "label": EmploymentType.get_label(emp.employment_type)
                },
                "working_status": {
                    "value": emp.working_status,
                    "label": WorkingStatus.get_label(emp.working_status)
                },
                "is_attendance_required": emp.is_attendance_required
            },
            "system": {
                "user_id": emp.user_id,
                "username": emp.user.username if emp.user else None,
                "created_at": emp.created_at.strftime("%d/%m/%Y %H:%M") if emp.created_at else None,
                "updated_at": emp.updated_at.strftime("%d/%m/%Y %H:%M") if emp.updated_at else None,
            }
        }
    
    @staticmethod
    def update_profile(user_id, dto):
        """
        Cập nhật thông tin cá nhân của nhân viên.
        Khớp với Model Employee (địa chỉ chi tiết, giới tính, ngày sinh).
        """
        user = db.session.get(User, user_id)
        if not user or not user.employee_profile:
            raise NotFoundError("Không tìm thấy thông tin nhân viên để cập nhật.")

        emp = user.employee_profile

        # 1. Cập nhật các trường cơ bản
        emp.full_name = dto.full_name
        emp.phone = dto.phone
        emp.gender = dto.gender  # 'male', 'female', 'other'
        
        # 2. Xử lý ngày sinh (Chuyển từ string sang date object nếu cần)
        if isinstance(dto.dob, str):
            emp.dob = datetime.strptime(dto.dob, "%Y-%m-%d").date()
        else:
            emp.dob = dto.dob
        # 3. Cập nhật địa chỉ chi tiết (Dựa trên Model của ông)
        emp.address = dto.address  
        emp.province_id = dto.province_id
        emp.district_id = dto.district_id
        emp.ward_id = dto.ward_id
        emp.address_detail = dto.address_detail # Số nhà, tên đường
        try:
            HistoryLog.append(
                employee_id=emp.id,
                action="UPDATE_PROFILE",
                entity_type="employees",
                entity_id=emp.id,
                description=f"Nhân viên {emp.full_name} tự cập nhật thông tin cá nhân.",
                performed_by=user_id 
            )
            db.session.commit()
            return {
                "status": "success",
                "title": "Thành công",
                "message": "Thông tin cá nhân đã được cập nhật.",
                "data": {
                    "full_name": emp.full_name,
                    "updated_at": emp.updated_at.strftime("%H:%M %d/%m/%Y") if emp.updated_at else None
                }
            }
        except Exception as e:
            db.session.rollback()
            raise e
        
    @staticmethod
    def update_profile_by_employee_id(employee_id, dto):
        """Cập nhật hồ sơ theo employee_id và giữ logic truy vấn DB trong service."""
        emp = db.session.get(Employee, employee_id)
        if not emp or not emp.user_id:
            raise NotFoundError("Không tìm thấy thông tin nhân viên để cập nhật.")
        return ProfileService.update_profile(user_id=emp.user_id, dto=dto)
    
    @staticmethod
    def change_password(user_id, dto):
        user = db.session.get(User, user_id)
        if not user:
            raise NotFoundError("Tài khoản không tồn tại trên hệ thống.")
        if not user.check_password(dto.current_password):
            raise UnauthorizedError("Mật khẩu hiện tại không chính xác. Vui lòng kiểm tra lại.")
        user.set_password(dto.new_password)
        try:
            db.session.commit()
            return {
                "status": "success",
                "title": "Đổi mật khẩu thành công!",
                "message": "Mật khẩu của bạn đã được cập nhật. Vui lòng sử dụng mật khẩu mới cho lần đăng nhập sau."
            }
        except Exception as e:
            db.session.rollback()
            raise e
        
    @staticmethod
    def get_history(employee_id):
        logs = HistoryLog.query.filter_by(
            employee_id=employee_id,
            is_deleted=False
        ).order_by(HistoryLog.created_at.desc()).all()

        result = []
        for log in logs:
            result.append({
                "id": log.id,
                "action": log.action, 
                "entity": {
                    "type": log.entity_type, 
                    "id": log.entity_id
                },
                "description": log.description,
                "time": log.created_at.strftime("%d/%m/%Y %H:%M") if log.created_at else None,
                "performed_by": log.performed_by 
            })
        return result
    
    @staticmethod
    def update_avatar(employee_id: int, file, actor_user_id: int):
        if not file or not file.filename:
            raise ValueError("Không có file avatar")
        ext = file.filename.rsplit(".", 1)[-1].lower()
        if ext not in {"jpg", "jpeg", "png", "webp"}:
            raise ValueError("Avatar chỉ hỗ trợ JPG, PNG hoặc WEBP")
        emp = db.session.get(Employee, employee_id)
        if not emp:
            raise NotFoundError("Không tìm thấy nhân viên")
        file_record = UploadService.save_file(
            file=file,
            user_id=actor_user_id,
            entity_type="avatars",
            entity_id=emp.id
        )
        emp.avatar = f"/static/uploads/{file_record.file_url}"
        is_self = (emp.user_id == actor_user_id)
        HistoryLog.append(
            employee_id=emp.id,
            action="UPDATE_AVATAR",
            entity_type="employees",
            entity_id=emp.id,
            description=f"{'Nhân viên' if is_self else 'HR'} đã cập nhật ảnh đại diện.",
            performed_by=actor_user_id
        )
        db.session.commit()
        return {"message": "Cập nhật thành công", "avatar": emp.avatar}