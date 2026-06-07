class WorkingStatus:
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    RESIGNED = "resigned"
    PENDING_RESIGNATION = "pending_resignation"
    LABELS = {
        ACTIVE: "Đang làm việc",
        ON_LEAVE: "Nghỉ phép",
        RESIGNED: "Nghỉ việc",
        PENDING_RESIGNATION: "Chờ nghỉ việc"
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
    
class GenderType:
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"

    LABELS = {
        MALE: "Nam",
        FEMALE: "Nữ",
        OTHER: "Khác",
    }

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(key, value) for key, value in cls.LABELS.items()]

    @classmethod
    def get_label(cls, value: str) -> str:
        cleaned_value = (value or "").strip().lower()
        return cls.LABELS.get(cleaned_value, "Không rõ")


class AccountStatus:
    ACTIVE = "active"
    LOCKED = "locked"
    INACTIVE = "inactive"

    LABELS = {
        ACTIVE: "Hoạt động",
        LOCKED: "Bị khóa",
        INACTIVE: "Ngừng hoạt động",
    }

    @classmethod
    def choices(cls):
        return [(key, value) for key, value in cls.LABELS.items()]

    @classmethod
    def get_label(cls, value: str) -> str:
        cleaned_value = (value or "").strip().lower()
        return cls.LABELS.get(cleaned_value, "Không rõ")