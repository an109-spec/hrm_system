from datetime import time
from decimal import Decimal

class OvertimeConfig:
    MULTIPLIERS = {
        "holiday": Decimal("3.00"),
        "weekend": Decimal("2.00"),
        "after_shift": Decimal("1.50"), 
        "normal": Decimal("1.00")
    }
    
    OFFICIAL_PAY_START_TIME = time(19, 0, 0)

    @staticmethod
    def apply_multiplier(hours: Decimal, type_key: str) -> Decimal:
        multiplier = OvertimeConfig.MULTIPLIERS.get(type_key, Decimal("1.0"))
        return (hours * multiplier).quantize(Decimal("0.01")) 