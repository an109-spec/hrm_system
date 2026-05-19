from datetime import time

class AttendanceStatus:
    PRESENT = "present"
    LATE = "late"
    ABSENT = "absent"
    LEAVE = "leave"

    LABELS = {
        PRESENT: "Có mặt",
        LATE: "Đi muộn",
        ABSENT: "Vắng mặt",
        LEAVE: "Nghỉ phép",
    }
    @classmethod
    def choices(cls):
        return [(key, value) for key, value in cls.LABELS.items()]
    @classmethod
    def get_label(cls, value: str) -> str:
        cleaned_value = (value or "").strip().lower()
        return cls.LABELS.get(cleaned_value, "Không rõ")

class AttendanceConstants:
    STATUS_NOT_STARTED = "not_started"
    STATUS_WORKING_REGULAR = "working_regular"
    STATUS_REGULAR_DONE = "regular_done"
    STATUS_PENDING_OT = "regular_done_pending_ot_decision"
    STATUS_PRE_OT_REST = "pre_ot_rest"
    STATUS_WORKING_OVERTIME = "working_overtime"
    STATUS_REGULAR_CHECKOUT_REQ = "regular_checkout_required"
    STATUS_OT_CHECKIN_REQ = "ot_checkin_required"
    STATUS_COMPLETED = "completed"
    STATUS_LEAVE = "leave"
    STATUS_ABSENT = "absent"
    STATUS_HOLIDAY_OFF = "holiday_off"
    STATUS_WEEKEND_OFF = "weekend_off"

    OT_APPROVED_REQUIRED_STATES = {
        STATUS_PRE_OT_REST,
        STATUS_OT_CHECKIN_REQ,
        STATUS_WORKING_OVERTIME,
    }

    IMMUTABLE_OFFDAY_STATES = {
        STATUS_HOLIDAY_OFF,
        STATUS_WEEKEND_OFF,
    }

    FINAL_SHIFT_STATES = {
        STATUS_COMPLETED,
        STATUS_HOLIDAY_OFF,
        STATUS_WEEKEND_OFF,
        STATUS_LEAVE,
    }

    VALID_STATUSES = {
        STATUS_NOT_STARTED, STATUS_WORKING_REGULAR, STATUS_REGULAR_DONE,
        STATUS_PENDING_OT, STATUS_REGULAR_CHECKOUT_REQ, STATUS_ABSENT
    } | OT_APPROVED_REQUIRED_STATES | FINAL_SHIFT_STATES

    LATE_RULES = [
        {"min": 60, "penalty": 0, "label": "Nửa ngày công", "type": "half_day"},
        {"min": 31, "penalty": 100000, "label": "Phạt 100.000đ", "type": "money"},
        {"min": 15, "penalty": 50000, "label": "Phạt 50.000đ", "type": "money"},
        {"min": 1,  "penalty": 20000, "label": "Phạt 20.000đ", "type": "money"},
    ]  

    @staticmethod
    def normalize(value: str | None) -> str:
        return (value or "").strip().lower()

    @staticmethod
    def is_valid(value: str) -> bool:
        return AttendanceConstants.normalize(value) in AttendanceConstants.VALID_STATUSES
    @staticmethod
    def get_late_penalty(late_minutes: int) -> dict:
        """Tính toán tiền phạt và trạng thái nghỉ dựa trên số phút đi muộn"""
        if late_minutes <= 0:
            return {"penalty_amount": 0, "message": "", "is_half_day": False}
        for rule in AttendanceConstants.LATE_RULES:
            if late_minutes >= rule["min"]:
                return {
                    "penalty_amount": rule["penalty"],
                    "message": f" • {rule['label']}",
                    "is_half_day": (rule["type"] == "half_day")
                }
        return {"penalty_amount": 0, "message": "", "is_half_day": False}


class WorkConfig:
    CHECKIN_START = time(6, 0, 0)            # bắt đầu được ghi nhận công
    WORKDAY_START = time(8, 0, 0)            # giờ vào làm chính thức
    LATE_THRESHOLD = time(9, 0, 0)           # sau giờ này: đi trễ nặng / half-day

    LUNCH_START = time(12, 0, 0)
    LUNCH_END = time(13, 0, 0)

    WORKDAY_END = time(17, 0, 0)             # tan ca

    OT_START = time(18, 0, 0)                # mở OT / bắt đầu OT window
    OT_END = time(22, 0, 0)                  # kết thúc OT
    STANDARD_WORKING_DAYS = 22         # Số ngày công tiêu chuẩn trong tháng
    LATE_THRESHOLD_MINS = 0            # Số phút đi muộn cho phép (nếu có)