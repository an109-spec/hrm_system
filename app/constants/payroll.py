class SalaryStatus:
    PENDING = "pending"
    APPROVED = "approved"
    PAID = "paid"
    COMPLAINT = "complaint"

    LABELS = {
        PENDING: "Chờ Admin duyệt",
        APPROVED: "Chờ thanh toán",
        PAID: "Đã thanh toán",
        COMPLAINT: "Khiếu nại",
    }

    @classmethod
    def choices(cls):
        return [(key, value) for key, value in cls.LABELS.items()]

    @classmethod
    def get_label(cls, value: str) -> str:
        cleaned_value = (value or "").strip().lower()
        return cls.LABELS.get(cleaned_value, "Không rõ")