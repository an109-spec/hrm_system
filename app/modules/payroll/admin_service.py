from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.constants.common import RoleName
from app.constants.payroll import PayrollConfig, SalaryStatus
from app.extensions.db import db
from app.models import HistoryLog, SystemSetting
from app.models.notification import Notification
from app.models.role import Role
from app.models.salary import Salary
from app.models.user import User
from .base_service import PersonalPayrollService

class PayrollPolicyService(PersonalPayrollService):
    @staticmethod
    def get_setting_value(name: str, default: Any) -> str:
        full_key = PayrollConfig.make_key(name)
        row = SystemSetting.query.filter_by(key=full_key).first()
        return row.value if row else str(default)

    @staticmethod
    def _set_setting(name: str, value: Any, description: str = "") -> None:
        key = PayrollConfig.make_key(name) 
        row = SystemSetting.query.filter_by(key=key).first()
        if row:
            row.value = str(value)
            if description:
                row.description = description
        else:
            new_setting = SystemSetting(key=key, value=str(value), description=description or "salary policy")
            db.session.add(new_setting)
        db.session.commit()

    @staticmethod
    def get_policy() -> dict:
        d = PayrollConfig.get_default()
        
        policy = {
            "late_penalty": {
                "under_15": int(float(PayrollPolicyService.get_setting_value("late.under_15", d["late_penalty"]["under_15"]))),
                "from_15_to_30": int(float(PayrollPolicyService.get_setting_value("late.from_15_to_30", d["late_penalty"]["from_15_to_30"]))),
                "from_31_to_59": int(float(PayrollPolicyService.get_setting_value("late.from_31_to_59", d["late_penalty"]["from_31_to_59"]))),
                "over_60_half_day": PayrollPolicyService.get_setting_value("late.over_60_half_day", str(d["late_penalty"]["over_60_half_day"])).lower() == "true",
            },
            "insurance": {
                "social_percent": float(PayrollPolicyService.get_setting_value("insurance.social_percent", d["insurance"]["social_percent"])),
                "health_percent": float(PayrollPolicyService.get_setting_value("insurance.health_percent", d["insurance"]["health_percent"])),
                "unemployment_percent": float(PayrollPolicyService.get_setting_value("insurance.unemployment_percent", d["insurance"]["unemployment_percent"])),
            },
            "deduction": {
                "personal": int(float(PayrollPolicyService.get_setting_value("deduction.personal", d["deduction"]["personal"]))),
                "dependent_per_person": int(float(PayrollPolicyService.get_setting_value("deduction.dependent_per_person", d["deduction"]["dependent_per_person"]))),
            },
            "tax_free_allowances": {
                "fuel_allowance": int(float(PayrollPolicyService.get_setting_value("tax_free_allowance.fuel_allowance", d["tax_free_allowances"]["fuel_allowance"]))),
                "meal_allowance": int(float(PayrollPolicyService.get_setting_value("tax_free_allowance.meal_allowance", d["tax_free_allowances"]["meal_allowance"]))),
                "responsibility_allowance": int(float(PayrollPolicyService.get_setting_value("tax_free_allowance.responsibility_allowance", d["tax_free_allowances"]["responsibility_allowance"]))),
                "other_allowance": int(float(PayrollPolicyService.get_setting_value("tax_free_allowance.other_allowance", d["tax_free_allowances"]["other_allowance"]))),
            },
            "payroll_flow": d["payroll_flow"],
            "config_edit_locked": PayrollPolicyService.get_setting_value("config_edit_locked", str(d["config_edit_locked"])).lower() == "true",
        }

        brackets = []
        for idx, row in enumerate(d["tax"]["brackets"], start=1):
            brackets.append({
                "id": idx,
                "from": int(float(PayrollPolicyService.get_setting_value(f"tax.bracket.{idx}.from", row["from"]))),
                "to": int(float(PayrollPolicyService.get_setting_value(f"tax.bracket.{idx}.to", row["to"]))),
                "rate_percent": float(PayrollPolicyService.get_setting_value(f"tax.bracket.{idx}.rate_percent", row["rate_percent"])),
                "quick_deduction": int(float(PayrollPolicyService.get_setting_value(f"tax.bracket.{idx}.quick_deduction", row["quick_deduction"]))),
            })
        policy["tax"] = {"brackets": brackets}
        
        # Tính toán tổng
        policy["insurance"]["total_percent"] = round(
            policy["insurance"]["social_percent"] + policy["insurance"]["health_percent"] + policy["insurance"]["unemployment_percent"], 2
        )
        
        return policy

    @staticmethod
    def update_policy(payload: dict, actor_user_id: int | None = None) -> dict:
        """
        Cập nhật cấu hình lương và ghi log lịch sử.
        """
        current_policy = PayrollPolicyService.get_policy()
        if current_policy.get("config_edit_locked"):
            raise ValueError("Cấu hình đang bị khóa chỉnh sửa")
        late = payload.get("late_penalty") or {}
        ins = payload.get("insurance") or {}
        ded = payload.get("deduction") or {}
        tax = (payload.get("tax") or {}).get("brackets") or []
        tax_free = payload.get("tax_free_allowances") or {}

        if late:
            PayrollPolicyService._set_setting("late.under_15", late.get("under_15"))
            PayrollPolicyService._set_setting("late.from_15_to_30", late.get("from_15_to_30"))
            PayrollPolicyService._set_setting("late.from_31_to_59", late.get("from_31_to_59"))
            PayrollPolicyService._set_setting("late.over_60_half_day", str(late.get("over_60_half_day", True)).lower())
        if ins:
            PayrollPolicyService._set_setting("insurance.social_percent", ins.get("social_percent"))
            PayrollPolicyService._set_setting("insurance.health_percent", ins.get("health_percent"))
            PayrollPolicyService._set_setting("insurance.unemployment_percent", ins.get("unemployment_percent"))
        if ded:
            PayrollPolicyService._set_setting("deduction.personal", ded.get("personal"))
            PayrollPolicyService._set_setting("deduction.dependent_per_person", ded.get("dependent_per_person"))
        if tax:
            for idx, row in enumerate(tax, start=1):
                PayrollPolicyService._set_setting(f"tax.bracket.{idx}.from", row.get("from"))
                PayrollPolicyService._set_setting(f"tax.bracket.{idx}.to", row.get("to"))
                PayrollPolicyService._set_setting(f"tax.bracket.{idx}.rate_percent", row.get("rate_percent"))
                PayrollPolicyService._set_setting(f"tax.bracket.{idx}.quick_deduction", row.get("quick_deduction"))
        if tax_free:
            for key in ["fuel_allowance", "meal_allowance", "responsibility_allowance", "other_allowance"]:
                if key in tax_free:
                    PayrollPolicyService._set_setting(f"tax_free_allowance.{key}", tax_free[key])
        HistoryLog.append(
            employee_id=None,
            action="UPDATE_SALARY_POLICY",
            entity_type="salary_policy",
            description=f"Cập nhật cấu hình lương: {str(payload)}",
            performed_by=actor_user_id
        )
        db.session.commit()
        return PayrollPolicyService.get_policy()

    @staticmethod
    def set_edit_lock(locked: bool, actor_user_id: int | None = None) -> None:
        """
        Khóa hoặc mở khóa cấu hình lương.
        """
        PayrollPolicyService._set_setting("config_edit_locked", str(locked).lower())
        action_name = "LOCK_SALARY_POLICY" if locked else "UNLOCK_SALARY_POLICY"
        HistoryLog.append(
            employee_id=None,
            action=action_name,
            entity_type="salary_policy",
            description=f"Cấu hình lương đã được {'khóa' if locked else 'mở khóa'}",
            performed_by=actor_user_id
        )
        db.session.commit()

    @staticmethod
    def approve_payroll_flow(
        salary_id: int, 
        action: str, 
        note: str = "", 
        actor_user_id: int | None = None
    ) -> dict:
        salary = Salary.query.get(salary_id)
        if not salary:
            raise ValueError("Không tìm thấy bảng lương")
        
        action = action.lower()

        # 1. PHÊ DUYỆT (Chỉ cho phép khi đã qua bước Review)
        if action == "approve":
            # Gợi ý: Có thể thêm kiểm tra xem đã có khiếu nại nào chưa xử lý xong không
            salary.status = SalaryStatus.APPROVED

        # 2. GỬI BẢNG LƯƠNG CHO TOÀN BỘ NHÂN VIÊN REVIEW (Bước mới)
        elif action == "notify_review":
            if salary.status != SalaryStatus.PENDING:
                raise ValueError("Chỉ có thể gửi thông báo review khi bảng lương đang ở trạng thái PENDING")
            # Kích hoạt thông báo cho tất cả nhân viên
            PayrollPolicyService._notify_all_employees_for_review(salary.month, salary.year)
            # Không cần đổi status, vẫn giữ PENDING để HR có thể sửa nếu nhân viên phản hồi

        # 3. CHỐT LƯƠNG (Finalize)
        elif action == "finalize":
            if salary.status != SalaryStatus.APPROVED:
                raise ValueError("Chỉ chốt được bảng lương đã APPROVED")
            salary.status = SalaryStatus.LOCKED

        # 4. TỪ CHỐI / KHIẾU NẠI (Reject)
        elif action == "reject":
            if salary.status == SalaryStatus.PAID:
                raise ValueError("Không thể từ chối bảng lương đã thanh toán.")
            if not note or len(note.strip()) < 5:
                raise ValueError("Cần nhập lý do từ chối để HR sửa đổi.")
            salary.status = SalaryStatus.REJECTED

        # 5. THANH TOÁN (Paid)
        elif action == "paid":
            if salary.status != SalaryStatus.LOCKED:
                raise ValueError("Chỉ thanh toán được bảng lương đã chốt (LOCKED)")
            salary.status = SalaryStatus.PAID
            PayrollPolicyService._notify_employee_payment(salary)
        
        else:
            raise ValueError("Action không hợp lệ")

        # Lưu ghi chú
        if note:
            salary.note = note
        HistoryLog.append(
            employee_id=salary.employee_id,
            action=f"ADMIN_{action.upper()}_PAYROLL",
            entity_type="salary",
            entity_id=salary.id,
            description=f"Admin đã thực hiện: {action}. Ghi chú: {note}",
            performed_by=actor_user_id
        )
        hr_role = Role.query.filter_by(name=RoleName.HR).first()
        if hr_role:
            hr_users = User.query.filter_by(role_id=hr_role.id).all()
            for hr in hr_users:
                notification = Notification(
                    user_id=hr.id,
                    title=f"Kết quả duyệt lương: {SalaryStatus.get_label(salary.status)}",
                    content=f"Bảng lương tháng {salary.month}/{salary.year} của {salary.employee.full_name} đã chuyển sang trạng thái: {SalaryStatus.get_label(salary.status)}.",
                    type="PAYROLL_UPDATE"
                )
                db.session.add(notification)
        db.session.commit()
        return {
            "id": salary.id, 
            "status": salary.status, 
            "status_label": SalaryStatus.get_label(salary.status)
        }
    @staticmethod
    def _notify_all_employees_for_review(month: int, year: int):
        salaries = Salary.query.filter_by(month=month, year=year, is_deleted=False).all()
        for s in salaries:
            if s.employee and s.employee.user_id:
                notification = Notification(
                    user_id=s.employee.user_id,
                    title="📝 Bảng lương đang chờ kiểm tra",
                    content=f"Bảng lương tháng {month}/{year} của bạn đã sẵn sàng. Vui lòng xem và phản hồi nếu có sai sót.",
                    link=f"/payroll/latest/me",
                    type="PAYROLL_REVIEW"
                )
                db.session.add(notification)

    @staticmethod
    def set_salary_config_for_position(position_id: int, salary_data: dict, actor_user_id: int | None = None):
        """
        Lưu cấu hình lương cho một chức danh cụ thể (dựa trên position_id).
        salary_data ví dụ: {"base_salary": 20000000, "lunch_allowance": 500000}
        """
        for key, value in salary_data.items():
            setting_key = f"pos_{position_id}.{key}"
            PayrollPolicyService._set_setting(setting_key, value, description=f"Config cho Position ID: {position_id}")
        HistoryLog.append(
            employee_id=None,
            action="UPDATE_POSITION_SALARY_CONFIG",
            entity_type="position_salary",
            entity_id=position_id,
            description=f"Cập nhật cấu hình lương cho Position ID {position_id}: {salary_data}",
            performed_by=actor_user_id
        )

    @staticmethod
    def get_salary_config_for_position(position_id: int) -> dict:
        """
        Lấy cấu hình lương của một chức danh theo position_id.
        """
        prefix = f"pos_{position_id}."
        settings = SystemSetting.query.filter(SystemSetting.key.like(f"{prefix}%")).all()
        config = {}
        for s in settings:
            attr = s.key.replace(prefix, "")
            config[attr] = s.value
        return config