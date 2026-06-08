from __future__ import annotations
from typing import Any
from datetime import date
from app.extensions.db import db
from app.models import Dependent, Employee, HistoryLog, Salary
from app.utils.time import get_current_time
from app.constants.dependent import DependentRelationship

class EmployeeDependentService:
    @staticmethod
    def validate_relationship(relationship: str):
        if relationship not in DependentRelationship.values():
            raise ValueError(f"Mối quan hệ '{relationship}' không hợp lệ")
        
    @staticmethod
    def _get_employee(user_id: int | None) -> Employee:
        employee = Employee.query.filter_by(user_id=user_id, is_deleted=False).first()
        if not employee:
            raise ValueError("Không tìm thấy hồ sơ nhân viên")
        return employee


    @staticmethod
    def _get_employee_by_id(employee_id: int) -> Employee:
        employee = db.session.get(Employee, employee_id)
        if not employee or employee.is_deleted:
            raise ValueError("Nhân viên không tồn tại.")
        return employee

    @staticmethod
    def list_dependents_by_employee_id(*, employee_id: int) -> dict[str, Any]:
        employee = EmployeeDependentService._get_employee_by_id(employee_id)
        return EmployeeDependentService.list_dependents(employee=employee)

    @staticmethod
    def create_dependent_by_employee_id(*, employee_id: int, payload: dict[str, Any], actor_user_id: int) -> dict[str, Any]:
        employee = EmployeeDependentService._get_employee_by_id(employee_id)
        return EmployeeDependentService.create_dependent(
            employee=employee,
            payload=payload,
            actor_user_id=actor_user_id,
        )

    @staticmethod
    def update_dependent_by_employee_id(*, employee_id: int, dependent_id: int, payload: dict[str, Any], actor_user_id: int) -> dict[str, Any]:
        employee = EmployeeDependentService._get_employee_by_id(employee_id)
        return EmployeeDependentService.update_dependent(
            employee=employee,
            dependent_id=dependent_id,
            payload=payload,
            actor_user_id=actor_user_id,
        )

    @staticmethod
    def delete_dependent_by_employee_id(*, employee_id: int, dependent_id: int, actor_user_id: int) -> dict[str, Any]:
        employee = EmployeeDependentService._get_employee_by_id(employee_id)
        return EmployeeDependentService.delete_dependent(
            employee=employee,
            dependent_id=dependent_id,
            actor_user_id=actor_user_id,
        )

    @staticmethod
    def _serialize_dependent(row: Dependent) -> dict:
        """
        Chuyển đổi Object Model sang Dictionary (JSON) để trả về cho Frontend.
        """
        return {
            "id": row.id,
            "full_name": row.full_name,
            "dob": row.dob.isoformat() if row.dob else None,
            "relationship": row.relationship,
            "relationship_label": DependentRelationship.get_label(row.relationship),
            "tax_code": row.tax_code,
            "is_valid": bool(row.is_valid),
            "note": row.note,
            "employee_id": row.employee_id
        }

    @staticmethod
    def list_dependents(*, employee: Employee) -> dict[str, Any]:
        """
        Lấy danh sách người phụ thuộc của một nhân viên.
        Áp dụng cho: 
        1. Nhân viên xem hồ sơ cá nhân.
        2. HR/Kế toán kiểm tra số lượng người phụ thuộc để tính thuế TNCN.
        """
        if not employee:
            raise ValueError("Hồ sơ nhân viên không hợp lệ")
        rows = Dependent.query.filter_by(
            employee_id=employee.id,
            is_deleted=False
        ).order_by(Dependent.created_at.desc()).all()
        valid_count = len([x for x in rows if x.is_valid])

        return {
            "items": [
                EmployeeDependentService._serialize_dependent(x)
                for x in rows
            ],
            "number_of_dependents": valid_count, # Số lượng dùng để tính lương/thuế
            "total_records": len(rows)           # Tổng số lượng khai báo
        }

    @staticmethod
    def _validate_dependent(data: dict[str, Any]) -> None:
        """
        Kiểm tra tính hợp lệ của dữ liệu người phụ thuộc trước khi lưu.
        Đã lược bỏ mã số thuế và khớp với Constant DependentRelationship.
        """
        full_name = (data.get("full_name") or "").strip()
        if not full_name:
            raise ValueError("Họ tên người phụ thuộc là bắt buộc")
        
        if len(full_name) > 120:
            raise ValueError("Họ tên không được vượt quá 120 ký tự")
        relationship = data.get("relationship")
        if relationship not in DependentRelationship.values():
            raise ValueError(f"Quan hệ '{relationship}' không hợp lệ. Vui lòng chọn trong danh mục quy định.")
        dob = data.get("dob")
        if not dob:
            raise ValueError("Ngày sinh người phụ thuộc là bắt buộc")
        if isinstance(dob, str):
            try:
                from datetime import datetime
                datetime.strptime(dob, '%Y-%m-%d')
            except ValueError:
                raise ValueError("Định dạng ngày sinh không hợp lệ (YYYY-MM-DD)")

        # 4. Kiểm tra Ghi chú (Nếu có thì không quá dài)
        note = (data.get("note") or "").strip()
        if note and len(note) > 500:
            raise ValueError("Ghi chú không được vượt quá 500 ký tự")

    @staticmethod
    def create_dependent(*, employee: Employee, payload: dict[str, Any], actor_user_id: int) -> dict[str, Any]:
        """
        Tạo mới người phụ thuộc và lưu vào lịch sử hệ thống.
        """
        if not employee:
            raise ValueError("Hồ sơ nhân viên không hợp lệ")
        EmployeeDependentService._validate_dependent(payload)
        now = get_current_time()
        try:
            dob_str = payload.get("dob")
            dob = date.fromisoformat(dob_str)
            if dob > now.date():
                raise ValueError("Ngày sinh không được vượt quá thời gian hiện tại")
            new_dependent = Dependent(
                employee_id=employee.id,
                full_name=payload["full_name"].strip(),
                dob=dob,
                relationship=payload["relationship"],
                tax_code=None,  
                is_valid=bool(payload.get("is_valid", True)),
                note=(payload.get("note") or "").strip() or None,
                created_at=now
            )
            db.session.add(new_dependent)
            db.session.flush() 
            log = HistoryLog(
                employee_id=employee.id,
                action="EMPLOYEE_DEPENDENT_CREATED",
                entity_type="dependent",
                entity_id=new_dependent.id,
                description=f"Thêm mới người phụ thuộc: {new_dependent.full_name} ({DependentRelationship.get_label(new_dependent.relationship)})",
                performed_by=actor_user_id,
                created_at=now
            )
            db.session.add(log)
            db.session.commit()
            return {
                "message": "Thêm người phụ thuộc thành công",
                "item": EmployeeDependentService._serialize_dependent(new_dependent)
            }
        except Exception as e:
            db.session.rollback()
            # Log lỗi thực tế ra console để ông dễ debug khi làm đồ án
            print(f"Error in create_dependent: {str(e)}")
            raise e
        
    @staticmethod
    def update_dependent(*, employee: Employee, dependent_id: int, payload: dict[str, Any], actor_user_id: int) -> dict[str, Any]:
        """
        Cập nhật thông tin người phụ thuộc và ghi lại lịch sử thay đổi.
        """
        if not employee:
            raise ValueError("Hồ sơ nhân viên không hợp lệ")
        row = Dependent.query.filter_by(
            id=dependent_id,
            employee_id=employee.id,
            is_deleted=False
        ).first()
        if not row:
            raise ValueError("Không tìm thấy người phụ thuộc hoặc bạn không có quyền chỉnh sửa")
        EmployeeDependentService._validate_dependent(payload)
        now = get_current_time()
        try:
            row.full_name = payload["full_name"].strip()
            row.relationship = payload["relationship"]
            row.tax_code = None 
            row.is_valid = bool(payload.get("is_valid", True))
            row.note = (payload.get("note") or "").strip() or None
            dob_str = payload.get("dob")
            if dob_str:
                dob = date.fromisoformat(dob_str)
                if dob > now.date():
                    raise ValueError("Ngày sinh không được vượt quá thời gian hiện tại")
                row.dob = dob
            log = HistoryLog(
                employee_id=employee.id,
                action="EMPLOYEE_DEPENDENT_UPDATED",
                entity_type="dependent",
                entity_id=row.id,
                description=f"Cập nhật thông tin người phụ thuộc: {row.full_name} ({DependentRelationship.get_label(row.relationship)})",
                performed_by=actor_user_id,
                created_at=now
            )
            db.session.add(log)
            db.session.commit()

            return {
                "message": "Cập nhật người phụ thuộc thành công",
                "item": EmployeeDependentService._serialize_dependent(row)
            }
        except Exception as e:
            db.session.rollback()
            print(f"Error in update_dependent: {str(e)}") # Hỗ trợ debug
            raise e
        
    @staticmethod
    def delete_dependent(*, employee: Employee, dependent_id: int, actor_user_id: int) -> dict[str, Any]:
        if not employee:
            raise ValueError("Hồ sơ nhân viên không hợp lệ")
        row = Dependent.query.filter_by(
            id=dependent_id,
            employee_id=employee.id,
            is_deleted=False
        ).first()
        if not row:
            raise ValueError("Không tìm thấy người phụ thuộc")
        used_in_salary = Salary.query.filter(
            Salary.employee_id == employee.id,
            Salary.status.in_(['approved', 'paid']) 
        ).first()
        if used_in_salary:
            raise ValueError(
                f"Không thể xóa vì người phụ thuộc này đã được chốt trong bảng lương "
                f"tháng {used_in_salary.month}/{used_in_salary.year} (Trạng thái: {used_in_salary.status})"
            )
        now = get_current_time()
        try:
            row.is_deleted = True
            db.session.add(
                HistoryLog(
                    employee_id=employee.id,
                    action="EMPLOYEE_DEPENDENT_DELETED",
                    entity_type="dependent",
                    entity_id=row.id,
                    description=f"Nhân viên xóa người phụ thuộc {row.full_name}",
                    performed_by=actor_user_id,
                    created_at=now
                )
            )
            db.session.commit()
            return {"message": "Đã xóa người phụ thuộc thành công"}
        except Exception as e:
            db.session.rollback()
            raise e