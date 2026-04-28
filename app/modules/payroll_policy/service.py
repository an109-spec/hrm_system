from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.extensions.db import db
from app.models import Dependent, HistoryLog, SystemSetting


class PayrollPolicyService:
    KEY_PREFIX = "salary.policy"

    DEFAULT_POLICY = {
        "late_penalty": {
            "under_15": 20000,
            "from_15_to_30": 50000,
            "over_60_half_day": True,
        },
        "insurance": {
            "social_percent": 8.0,
            "health_percent": 1.5,
            "unemployment_percent": 1.0,
        },
        "tax": {
            "brackets": [
                {"from": 0, "to": 10_000_000, "rate_percent": 5, "quick_deduction": 0},
                {"from": 10_000_000, "to": 30_000_000, "rate_percent": 10, "quick_deduction": 500_000},
                {"from": 30_000_000, "to": 60_000_000, "rate_percent": 20, "quick_deduction": 3_500_000},
                {"from": 60_000_000, "to": 100_000_000, "rate_percent": 30, "quick_deduction": 9_500_000},
                {"from": 100_000_000, "to": 999_999_999_999, "rate_percent": 35, "quick_deduction": 14_500_000},
            ]
        },
        "deduction": {
            "personal": 15_500_000,
            "dependent_per_person": 6_200_000,
        },
        "payroll_flow": {
            "pending": "pending_approval",
            "approved": "approved",
            "locked": "locked",
            "complaint": "complaint",
            "allow_hr_edit_statuses": ["draft", "pending_approval"],
            "disallow_direct_edit_statuses": ["approved", "locked", "finalized"],
            "final_lock_statuses": ["locked", "finalized"],
        },
        "tax_free_allowances": {
            "fuel_allowance": 0,
            "meal_allowance": 0,
            "responsibility_allowance": 0,
            "other_allowance": 0,
        },
        "config_edit_locked": False,
    }

    @staticmethod
    def _key(name: str) -> str:
        return f"{PayrollPolicyService.KEY_PREFIX}.{name}"

    @staticmethod
    def _setting_value(name: str, default: Any) -> str:
        row = SystemSetting.query.filter_by(key=PayrollPolicyService._key(name)).first()
        return row.value if row else str(default)

    @staticmethod
    def _set_setting(name: str, value: Any, description: str = "") -> None:
        key = PayrollPolicyService._key(name)
        row = SystemSetting.query.filter_by(key=key).first()
        if row:
            row.value = str(value)
            if description:
                row.description = description
        else:
            db.session.add(SystemSetting(key=key, value=str(value), description=description or "salary policy"))

    @staticmethod
    def get_policy() -> dict:
        d = PayrollPolicyService.DEFAULT_POLICY
        policy = {
            "late_penalty": {
                "under_15": int(float(PayrollPolicyService._setting_value("late.under_15", d["late_penalty"]["under_15"]))),
                "from_15_to_30": int(float(PayrollPolicyService._setting_value("late.from_15_to_30", d["late_penalty"]["from_15_to_30"]))),
                "over_60_half_day": PayrollPolicyService._setting_value("late.over_60_half_day", "true").lower() == "true",
            },
            "insurance": {
                "social_percent": float(PayrollPolicyService._setting_value("insurance.social_percent", d["insurance"]["social_percent"])),
                "health_percent": float(PayrollPolicyService._setting_value("insurance.health_percent", d["insurance"]["health_percent"])),
                "unemployment_percent": float(PayrollPolicyService._setting_value("insurance.unemployment_percent", d["insurance"]["unemployment_percent"])),
            },
            "deduction": {
                "personal": int(float(PayrollPolicyService._setting_value("deduction.personal", d["deduction"]["personal"]))),
                "dependent_per_person": int(float(PayrollPolicyService._setting_value("deduction.dependent_per_person", d["deduction"]["dependent_per_person"]))),
            },
            "tax_free_allowances": {
                "fuel_allowance": int(float(PayrollPolicyService._setting_value("tax_free_allowance.fuel_allowance", 0))),
                "meal_allowance": int(float(PayrollPolicyService._setting_value("tax_free_allowance.meal_allowance", 0))),
                "responsibility_allowance": int(float(PayrollPolicyService._setting_value("tax_free_allowance.responsibility_allowance", 0))),
                "other_allowance": int(float(PayrollPolicyService._setting_value("tax_free_allowance.other_allowance", 0))),
            },
            "payroll_flow": d["payroll_flow"],
            "config_edit_locked": PayrollPolicyService._setting_value("config_edit_locked", "false").lower() == "true",
        }

        brackets = []
        for idx, row in enumerate(d["tax"]["brackets"], start=1):
            brackets.append(
                {
                    "id": idx,
                    "from": int(float(PayrollPolicyService._setting_value(f"tax.bracket.{idx}.from", row["from"]))),
                    "to": int(float(PayrollPolicyService._setting_value(f"tax.bracket.{idx}.to", row["to"]))),
                    "rate_percent": float(PayrollPolicyService._setting_value(f"tax.bracket.{idx}.rate_percent", row["rate_percent"])),
                    "quick_deduction": int(float(PayrollPolicyService._setting_value(f"tax.bracket.{idx}.quick_deduction", row["quick_deduction"]))),
                }
            )
        policy["tax"] = {"brackets": brackets}
        policy["insurance"]["total_percent"] = round(
            policy["insurance"]["social_percent"]
            + policy["insurance"]["health_percent"]
            + policy["insurance"]["unemployment_percent"],
            2,
        )
        return policy

    @staticmethod
    def update_policy(payload: dict, actor_user_id: int | None = None) -> dict:
        if PayrollPolicyService.get_policy().get("config_edit_locked"):
            raise ValueError("Cấu hình đang bị khóa chỉnh sửa")

        late = payload.get("late_penalty") or {}
        ins = payload.get("insurance") or {}
        ded = payload.get("deduction") or {}
        tax = (payload.get("tax") or {}).get("brackets") or []
        tax_free = payload.get("tax_free_allowances") or {}

        if late:
            PayrollPolicyService._set_setting("late.under_15", late.get("under_15", 20000))
            PayrollPolicyService._set_setting("late.from_15_to_30", late.get("from_15_to_30", 50000))
            PayrollPolicyService._set_setting("late.over_60_half_day", str(bool(late.get("over_60_half_day", True))).lower())
        if ins:
            PayrollPolicyService._set_setting("insurance.social_percent", ins.get("social_percent", 8))
            PayrollPolicyService._set_setting("insurance.health_percent", ins.get("health_percent", 1.5))
            PayrollPolicyService._set_setting("insurance.unemployment_percent", ins.get("unemployment_percent", 1))
        if ded:
            PayrollPolicyService._set_setting("deduction.personal", ded.get("personal", 15500000))
            PayrollPolicyService._set_setting("deduction.dependent_per_person", ded.get("dependent_per_person", 6200000))
        if tax:
            for idx, row in enumerate(tax, start=1):
                PayrollPolicyService._set_setting(f"tax.bracket.{idx}.from", row.get("from", 0))
                PayrollPolicyService._set_setting(f"tax.bracket.{idx}.to", row.get("to", 0))
                PayrollPolicyService._set_setting(f"tax.bracket.{idx}.rate_percent", row.get("rate_percent", 0))
                PayrollPolicyService._set_setting(f"tax.bracket.{idx}.quick_deduction", row.get("quick_deduction", 0))
        if tax_free:
            for key in ["fuel_allowance", "meal_allowance", "responsibility_allowance", "other_allowance"]:
                PayrollPolicyService._set_setting(f"tax_free_allowance.{key}", tax_free.get(key, 0))

        db.session.add(
            HistoryLog(
                employee_id=None,
                action="UPDATE_SALARY_POLICY",
                entity_type="salary_policy",
                description=str(payload),
                performed_by=actor_user_id,
            )
        )
        db.session.commit()
        return PayrollPolicyService.get_policy()

    @staticmethod
    def set_edit_lock(locked: bool, actor_user_id: int | None = None) -> None:
        PayrollPolicyService._set_setting("config_edit_locked", str(bool(locked)).lower())
        db.session.add(HistoryLog(action="LOCK_SALARY_POLICY" if locked else "UNLOCK_SALARY_POLICY", entity_type="salary_policy", description=f"locked={locked}", performed_by=actor_user_id))
        db.session.commit()

    @staticmethod
    def tax_by_bracket(taxable_income: Decimal, brackets: list[dict]) -> Decimal:
        if taxable_income <= 0:
            return Decimal("0")
        selected = None
        for b in brackets:
            if taxable_income > Decimal(str(b["from"])) and taxable_income <= Decimal(str(b["to"])):
                selected = b
                break
        if not selected:
            selected = brackets[-1]
        tax = taxable_income * (Decimal(str(selected["rate_percent"])) / Decimal("100")) - Decimal(str(selected["quick_deduction"]))
        return max(Decimal("0"), tax).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    @staticmethod
    def dependent_count(employee_id: int | None) -> int:
        if not employee_id:
            return 0
        count = Dependent.query.filter_by(employee_id=employee_id, is_deleted=False, is_valid=True).count()
        PayrollPolicyService._set_setting(f"employee.{employee_id}.number_of_dependents", count)
        return count