from app.constants.common import RoleName
from decimal import Decimal

class SalaryStatus:
    # 1. Các hằng số trạng thái
    DRAFT = "draft"           # Mới tạo, đang soạn thảo
    PENDING = "pending"       # Chờ duyệt (đã gửi đi)
    APPROVED = "approved"     # Admin đã duyệt, chờ thanh toán
    PAID = "paid"             # Đã thanh toán xong
    REJECTED = "rejected"     # Bị từ chối, cần sửa lại
    COMPLAINT = "complaint"   # Đang có khiếu nại
    LOCKED = "locked"         # Đã khóa sổ (Finalized), không thể sửa

    # 2. Nhãn hiển thị cho UI
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
        """
        Dùng cho các hàm Guard: 
        Trả về True nếu trạng thái cho phép HR/Admin chỉnh sửa bảng lương.
        """
        # Chỉ những trạng thái này mới được phép sửa
        return status in {cls.DRAFT, cls.REJECTED, cls.COMPLAINT}
    
class PayrollIssueType:
    """Các nhóm danh mục khiếu nại lương từ nhân viên"""
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
    """Trạng thái xử lý đơn khiếu nại của phòng nhân sự"""
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
        "tax_free_allowances": {
            "fuel_allowance": 0,
            "meal_allowance": 0,
        },
        "config_edit_locked": False,
    }

    @classmethod
    def get_default(cls, key=None):
        """Hàm lấy cấu hình, nếu key là None trả về toàn bộ"""
        if key:
            return cls.DEFAULT_POLICY.get(key)
        return cls.DEFAULT_POLICY
    
    @classmethod
    def make_key(cls, name: str) -> str:
        """Tạo khóa chuẩn hóa để truy vấn trong Database"""
        return f"{cls.KEY_PREFIX}.{name}"

class SalarySettings:
    FIXED_HOURLY_RATE = Decimal("50000")
    
    BASE_SALARY_BY_ROLE = {
        RoleName.ADMIN: Decimal("30000000"),   
        RoleName.HR: Decimal("25000000"),     
        RoleName.MANAGER: Decimal("40000000"), 
    }

class ConfigLockStatus:
    LOCKED = "true"
    UNLOCKED = "false"