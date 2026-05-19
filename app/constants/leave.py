class LeaveStatus:
    PENDING = "pending"
    PENDING_HR = "pending_hr"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    SUPPLEMENT_REQUESTED = "supplement_requested"
    COMPLAINT = "complaint"

    LABELS = {
        PENDING: "Chờ Manager duyệt",
        PENDING_HR: "Chờ HR duyệt",
        APPROVED: "Đã duyệt",
        REJECTED: "Từ chối",
        CANCELLED: "Đã hủy",
        SUPPLEMENT_REQUESTED: "Yêu cầu bổ sung",
        COMPLAINT: "Khiếu nại",
    }

    @classmethod
    def choices(cls):
        return [(key, value) for key, value in cls.LABELS.items()]

    @classmethod
    def get_label(cls, value: str) -> str:
        if not value:
            return "Không xác định"
        return cls.LABELS.get(str(value).strip().lower(), "Không xác định")


LEAVE_TYPE_CONFIGS = {
    "ANNUAL": {"name": "Nghỉ phép năm", "is_paid": True, "default_days": 12},
    "SICK": {"name": "Nghỉ ốm", "is_paid": True, "default_days": 5},
    "UNPAID": {"name": "Nghỉ không lương", "is_paid": False, "default_days": 0},
    "HOLIDAY": {"name": "Nghỉ lễ", "is_paid": True, "default_days": 0},
    "PERSONAL": {"name": "Nghỉ việc riêng", "is_paid": True, "default_days": 3},
    "MATERNITY": {"name": "Nghỉ thai sản", "is_paid": True, "default_days": 180},
}

STATUS_BADGE_CONFIG = {
    LeaveStatus.PENDING: {"icon": "bi-hourglass-split", "label": "Chờ Manager duyệt", "class": "bg-warning text-dark"},
    LeaveStatus.PENDING_HR: {"icon": "bi-file-earmark-medical", "label": "Chờ HR duyệt", "class": "bg-info text-dark"},
    LeaveStatus.APPROVED: {"icon": "bi-check-circle-fill", "label": "Đã duyệt", "class": "bg-success"},
    LeaveStatus.REJECTED: {"icon": "bi-x-circle-fill", "label": "Từ chối", "class": "bg-danger"},
    LeaveStatus.SUPPLEMENT_REQUESTED: {"icon": "bi-paperclip", "label": "Yêu cầu bổ sung", "class": "bg-secondary"},
    LeaveStatus.CANCELLED: {"icon": "bi-slash-circle", "label": "Đã hủy", "class": "bg-dark"},
    LeaveStatus.COMPLAINT: {"icon": "bi-megaphone", "label": "Khiếu nại", "class": "bg-primary"},
}

ENUM_LABELS = {
    "leave_status": LeaveStatus.LABELS,
    "leave_type": {key: value["name"] for key, value in LEAVE_TYPE_CONFIGS.items()},
}