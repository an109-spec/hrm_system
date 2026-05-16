from app.common.exceptions import ValidationError


MIN_PASSWORD_LENGTH = 8


def validate_update_profile(dto):
    if not dto.full_name:
        raise ValidationError("Full name is required")

    if dto.phone and len(dto.phone) < 9:
        raise ValidationError("Phone number is invalid")


def validate_change_password(dto):
    if not dto.current_password:
        raise ValidationError("Current password required")

    if not dto.new_password:
        raise ValidationError("New password required")

    if dto.new_password != dto.confirm_password:
        raise ValidationError("Password confirmation does not match")

    if len(dto.new_password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
        )