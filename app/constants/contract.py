class ContractStatus:
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    EXPIRING = "expiring"

    LABELS = {
        ACTIVE: "Đang hiệu lực",
        EXPIRED: "Hết hạn",
        TERMINATED: "Đã chấm dứt",
        EXPIRING: "Sắp hết hạn",
    }

    @classmethod
    def choices(cls):
        return [(key, value) for key, value in cls.LABELS.items()]

    @classmethod
    def get_label(cls, value: str) -> str:
        cleaned_value = (value or "").strip().lower()
        return cls.LABELS.get(cleaned_value, "Không rõ")


class ContractRequestStatus:
    PENDING = "pending"
    PENDING_TERMINATION = "pending_termination"
    APPROVED = "approved"
    REJECTED = "rejected"

    LABELS = {
        PENDING: "Chờ duyệt",
        PENDING_TERMINATION: "Chờ duyệt chấm dứt",
        APPROVED: "Đã duyệt",
        REJECTED: "Từ chối",
    }

    @classmethod
    def choices(cls):
        return [(key, value) for key, value in cls.LABELS.items()]

    @classmethod
    def get_label(cls, value: str) -> str:
        cleaned_value = (value or "").strip().lower()
        return cls.LABELS.get(cleaned_value, "Không rõ")
    
class ProposalType:
    RENEWAL = "renewal"
    TERMINATION = "termination"
    PROBATION_CONVERSION = "probation_conversion"
    ADJUSTMENT = "adjustment"

    LABELS = {
        RENEWAL: "Gia hạn",
        TERMINATION: "Chấm dứt hợp đồng",
        PROBATION_CONVERSION: "Chuyển chính thức",
        ADJUSTMENT: "Điều chỉnh hợp đồng",
    }

    @classmethod
    def choices(cls):
        """Dùng cho các field form, ví dụ: SelectField trong WTForms"""
        return [(key, value) for key, value in cls.LABELS.items()]

    @classmethod
    def get_label(cls, value: str) -> str:
        """Dùng để hiển thị tên đẹp trên UI/Table thay vì giá trị code"""
        cleaned_value = (value or "").strip().lower()
        return cls.LABELS.get(cleaned_value, "Không rõ")