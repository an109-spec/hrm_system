class DependentRelationship:
    CON = "con"
    VO_CHONG = "vo_chong"
    BO = "bo"
    ME = "me"
    KHAC = "khac"

    LABELS = {
        CON: "Con đẻ/Con nuôi",
        VO_CHONG: "Vợ/Chồng",
        BO: "Bố đẻ/Bố vợ/Bố chồng",
        ME: "Mẹ đẻ/Mẹ vợ/Mẹ chồng",
        KHAC: "Người thân khác",
    }

    @classmethod
    def choices(cls):
        return [(key, value) for key, value in cls.LABELS.items()]

    @classmethod
    def values(cls):
        return [cls.CON, cls.VO_CHONG, cls.BO, cls.ME, cls.KHAC]

    @classmethod
    def get_label(cls, value: str) -> str:
        return cls.LABELS.get(str(value).lower(), "Không xác định")