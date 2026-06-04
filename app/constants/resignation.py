class ResignationStatus:
    PENDING_MANAGER = "pending_manager"
    PENDING_HR = "pending_hr"
    PENDING_ADMIN = "pending_admin"
    APPROVED = "approved"
    REJECTED = "rejected"

    LABELS = {
        PENDING_MANAGER: "Chờ Manager duyệt",
        PENDING_HR: "Chờ HR duyệt",
        PENDING_ADMIN: "Chờ Admin duyệt",
        APPROVED: "Đã duyệt",
        REJECTED: "Từ chối",
    }

    @classmethod
    def get_label(cls, value: str) -> str:
        return cls.LABELS.get(value, "Không xác định")

class ResignationType:
    # Phân biệt ai là người khởi tạo/đề xuất
    EMPLOYEE = "employee"
    MANAGER_PROPOSAL = "manager_proposal"

    LABELS = {
        EMPLOYEE: "Nhân viên tự xin nghỉ",
        MANAGER_PROPOSAL: "Quản lý đề xuất nghỉ",
    }