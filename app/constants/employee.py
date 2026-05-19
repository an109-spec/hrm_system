class WorkingStatus:
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    RESIGNED = "resigned"

    LABELS = {
        ACTIVE: "Đang làm việc",
        ON_LEAVE: "Nghỉ phép",
        RESIGNED: "Nghỉ việc",
    }

    @classmethod
    def choices(cls):
        return [(key, value) for key, value in cls.LABELS.items()]

    @classmethod
    def get_label(cls, value: str) -> str:
        cleaned_value = (value or "").strip().lower()
        return cls.LABELS.get(cleaned_value, "Không rõ")


class EmploymentType:
    PROBATION = "probation"
    PERMANENT = "permanent"
    INTERN = "intern"

    LABELS = {
        PROBATION: "Thử việc",
        PERMANENT: "Chính thức",
        INTERN: "Thực tập sinh",
    }

    @classmethod
    def choices(cls):
        return [(key, value) for key, value in cls.LABELS.items()]

    @classmethod
    def get_label(cls, value: str) -> str:
        cleaned_value = (value or "").strip().lower()
        return cls.LABELS.get(cleaned_value, "Không rõ")