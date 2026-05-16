from __future__ import annotations
from typing import Any
from datetime import date
import re

from app.extensions.db import db
from app.models import Dependent, Employee, HistoryLog, Salary
from app.utils.time import get_current_time


class EmployeeDependentService:
    RELATIONSHIPS = {"con", "vo_chong", "bo", "me", "khac"}

    # =====================================================
    # EMPLOYEE RESOLUTION
    # =====================================================
    @staticmethod
    def _employee_by_user(user_id: int | None) -> Employee:
        employee = Employee.query.filter_by(
            user_id=user_id,
            is_deleted=False
        ).first()

        if not employee:
            raise ValueError("Không tìm thấy hồ sơ nhân viên")

        return employee

    # =====================================================
    # SERIALIZER
    # =====================================================
    @staticmethod
    def _serialize_dependent(row: Dependent) -> dict:
        return {
            "id": row.id,
            "full_name": row.full_name,
            "dob": row.dob.isoformat() if row.dob else None,
            "relationship": row.relationship,
            "tax_code": row.tax_code,
            "is_valid": bool(row.is_valid),
            "note": getattr(row, "note", None),
        }

    # =====================================================
    # LIST
    # =====================================================
    @staticmethod
    def list_dependents(*, employee: Employee) -> dict[str, Any]:
        if not employee:
            raise ValueError("Hồ sơ nhân viên không hợp lệ")

        rows = Dependent.query.filter_by(
            employee_id=employee.id,
            is_deleted=False
        ).order_by(Dependent.created_at.desc()).all()

        count = sum(1 for x in rows if x.is_valid)

        return {
            "items": [
                EmployeeDependentService._serialize_dependent(x)
                for x in rows
            ],
            "number_of_dependents": count
        }

    # =====================================================
    # VALIDATION
    # =====================================================
    @staticmethod
    def _validate_dependent(data: dict[str, Any]) -> None:
        if not (data.get("full_name") or "").strip():
            raise ValueError("Họ tên người phụ thuộc là bắt buộc")

        if data.get("relationship") not in EmployeeDependentService.RELATIONSHIPS:
            raise ValueError("Quan hệ không hợp lệ")

        tax_code = (data.get("tax_code") or "").strip()
        if tax_code and not re.fullmatch(r"[0-9]{10,13}", tax_code):
            raise ValueError("Mã số thuế cá nhân phải có 10-13 chữ số")

    # =====================================================
    # CREATE
    # =====================================================
    @staticmethod
    def create_dependent(*, employee: Employee, payload: dict[str, Any], actor_user_id: int) -> dict[str, Any]:
        if not employee:
            raise ValueError("Hồ sơ nhân viên không hợp lệ")

        EmployeeDependentService._validate_dependent(payload)

        now = get_current_time()
        try:
            dob_str = payload.get("dob")
            if not dob_str:
                raise ValueError("Ngày sinh của người phụ thuộc là bắt buộc")
                
            dob = date.fromisoformat(dob_str)
            if dob > now.date():
                raise ValueError("Ngày sinh không được vượt quá thời gian hiện tại")

            row = Dependent(
                employee_id=employee.id,
                full_name=payload["full_name"].strip(),
                dob=dob,
                relationship=payload["relationship"],
                tax_code=(payload.get("tax_code") or "").strip() or None,
                is_valid=bool(payload.get("is_valid", True)),
                note=(payload.get("note") or "").strip() or None,
                created_at=now
            )

            db.session.add(row)
            db.session.flush()  # Đồng bộ để sinh ID cho thực thể `row`

            db.session.add(
                HistoryLog(
                    employee_id=employee.id,
                    action="EMPLOYEE_DEPENDENT_CREATED",
                    entity_type="dependent",
                    entity_id=row.id,
                    description=f"Nhân viên tạo người phụ thuộc {row.full_name}",
                    performed_by=actor_user_id,
                    created_at=now
                )
            )

            db.session.commit()
            return {
                "message": "Thêm người phụ thuộc thành công",
                "item": EmployeeDependentService._serialize_dependent(row)
            }
            
        except Exception as e:
            db.session.rollback()
            raise e

    # =====================================================
    # UPDATE
    # =====================================================
    @staticmethod
    def update_dependent(*, employee: Employee, dependent_id: int, payload: dict[str, Any], actor_user_id: int) -> dict[str, Any]:
        if not employee:
            raise ValueError("Hồ sơ nhân viên không hợp lệ")

        row = Dependent.query.filter_by(
            id=dependent_id,
            employee_id=employee.id,
            is_deleted=False
        ).first()

        if not row:
            raise ValueError("Không tìm thấy người phụ thuộc")

        EmployeeDependentService._validate_dependent(payload)

        now = get_current_time()
        try:
            row.full_name = payload["full_name"].strip()
            row.relationship = payload["relationship"]
            row.tax_code = (payload.get("tax_code") or "").strip() or None
            row.is_valid = bool(payload.get("is_valid", True))

            dob_str = payload.get("dob")
            if not dob_str:
                raise ValueError("Ngày sinh của người phụ thuộc là bắt buộc")
                
            dob = date.fromisoformat(dob_str)
            if dob > now.date():
                raise ValueError("Ngày sinh không được vượt quá thời gian hiện tại")

            row.dob = dob
            row.note = (payload.get("note") or "").strip() or None

            db.session.add(
                HistoryLog(
                    employee_id=employee.id,
                    action="EMPLOYEE_DEPENDENT_UPDATED",
                    entity_type="dependent",
                    entity_id=row.id,
                    description=f"Nhân viên cập nhật người phụ thuộc {row.full_name}",
                    performed_by=actor_user_id,
                    created_at=now
                )
            )

            db.session.commit()
            return {
                "message": "Cập nhật người phụ thuộc thành công",
                "item": EmployeeDependentService._serialize_dependent(row)
            }
            
        except Exception as e:
            db.session.rollback()
            raise e

    # =====================================================
    # DELETE
    # =====================================================
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

        # Kiểm tra điều kiện ràng buộc nghiệp vụ với bảng lương
        used = Salary.query.filter_by(
            employee_id=employee.id,
            status="finalized"
        ).first()

        if used:
            raise ValueError("Không thể xóa người phụ thuộc đã dùng cho bảng lương đã chốt (finalized)")

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