from datetime import date


class LeaveValidator:

    @staticmethod
    def validate_date_range(from_date: date, to_date: date):
        if from_date > to_date:
            raise ValueError("from_date cannot be greater than to_date")

    @staticmethod
    def validate_reason(reason: str):
        if not reason or len(reason.strip()) < 5:
            raise ValueError("Reason must be at least 5 characters")

    @staticmethod
    def validate_leave_days_limit(remaining_days: int, requested_days: int):
        if requested_days > remaining_days:
            raise ValueError("Not enough leave balance")