from app.constants.common import RoleName
from decimal import Decimal

class SalaryStatus:
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    PAID = "paid"
    REJECTED = "rejected"
    COMPLAINT = "complaint"
    LOCKED = "locked"

    LABELS = {
        DRAFT: "Nháp",
        PENDING: "Chờ Admin duyệt",
        APPROVED: "Chờ thanh toán",
        PAID: "Đã thanh toán",
        REJECTED: "Bị từ chối",
        COMPLAINT: "Khiếu nại",
        LOCKED: "Đã khóa (Finalized)",
    }

    @classmethod
    def choices(cls):
        return [(key, value) for key, value in cls.LABELS.items()]

    @classmethod
    def get_label(cls, value: str) -> str:
        cleaned_value = (value or "").strip().lower()
        return cls.LABELS.get(cleaned_value, "Không rõ")

    @classmethod
    def is_editable(cls, status: str) -> bool:
        return status in {cls.DRAFT, cls.REJECTED, cls.COMPLAINT}

class PayrollIssueType:
    ATTENDANCE = "attendance_issue"
    OT = "ot_issue"
    ALLOWANCE = "allowance_issue"
    TAX = "tax_issue"
    INSURANCE = "insurance_issue"
    DEDUCTION = "deduction_issue"
    OTHER = "other"

    LABELS = {
        ATTENDANCE: "Khiếu nại chấm công",
        OT: "Khiếu nại tăng ca (OT)",
        ALLOWANCE: "Khiếu nại phụ cấp",
        TAX: "Khiếu nại thuế TNCN",
        INSURANCE: "Khiếu nại bảo hiểm",
        DEDUCTION: "Khiếu nại khoản giảm trừ",
        OTHER: "Vấn đề khác khác",
    }

    @classmethod
    def values(cls) -> set[str]:
        return {cls.ATTENDANCE, cls.OT, cls.ALLOWANCE, cls.TAX, cls.INSURANCE, cls.DEDUCTION, cls.OTHER}

class SalaryComplaintStatus:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"

    LABELS = {
        PENDING: "⏳ Đang chờ xử lý",
        IN_PROGRESS: "⏳ Đang xử lý",
        RESOLVED: "✅ Đã giải quyết",
        REJECTED: "❌ Từ chối",
    }

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(key, value) for key, value in cls.LABELS.items()]

class PayrollConfig:
    KEY_PREFIX = "salary.policy"

    DEFAULT_POLICY = {
        "late_penalty": {
            "under_15": 20000,
            "from_15_to_30": 50000,
            "from_31_to_59": 100000,
            "over_60_half_day": True
        },       
        "insurance": {
            "social_percent": 8.0,
            "health_percent": 1.5,
            "unemployment_percent": 1.0,
            "employer_social_percent": 17.0,
            "employer_health_percent": 3.0,
            "employer_unemployment_percent": 1.0,
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
        "tax_free_allowances": {
            "meal_allowance": 730000,
            "fuel_allowance": 500000,
            "responsibility_allowance": 0,
            "other_allowance": 0
        },
        "payroll_flow": [
            {"status": "draft", "label": "Soạn thảo"},
            {"status": "pending", "label": "Chờ duyệt"},
            {"status": "approved", "label": "Đã duyệt"},
            {"status": "locked", "label": "Đã chốt sổ"},
            {"status": "paid", "label": "Đã thanh toán"}
        ],
        "config_edit_locked": False,
    }

    @classmethod
    def get_default(cls, key=None):
        if key:
            return cls.DEFAULT_POLICY.get(key)
        return cls.DEFAULT_POLICY
    
    @classmethod
    def make_key(cls, name: str) -> str:
        return f"{cls.KEY_PREFIX}.{name}"

class SalarySettings:
    FIXED_HOURLY_RATE = Decimal("50000")
    
    BASE_SALARY_BY_ROLE = {
        RoleName.ADMIN: Decimal("30000000"),   
        RoleName.HR: Decimal("25000000"),     
        RoleName.MANAGER: Decimal("40000000"), 
        RoleName.EMPLOYEE: Decimal("8800000"),
    }

class ConfigLockStatus:
    LOCKED = "true"
    UNLOCKED = "false"
