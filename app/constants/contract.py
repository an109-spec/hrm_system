class ContractStatus:
    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"

    LABELS = {
        ACTIVE: "Đang hiệu lực",
        EXPIRED: "Hết hạn",
        TERMINATED: "Đã chấm dứt",
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