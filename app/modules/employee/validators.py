from app.common.exceptions import ValidationError


def validate_update_profile(dto):
    if not dto.full_name:
        raise ValidationError("Full name is required")

    if dto.phone and len(dto.phone) < 9:
        raise ValidationError("Phone number is invalid")


def validate_change_password(dto):
    if not dto.current_password:
        raise ValidationError("Current password required")

    if dto.new_password != dto.confirm_password:
        raise ValidationError("Password confirmation does not match")

    if len(dto.new_password) < 6:
        raise ValidationError("Password must be at least 6 characters")