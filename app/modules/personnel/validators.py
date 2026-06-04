from app.common.exceptions import ValidationError

MIN_PASSWORD_LENGTH = 8

def validate_update_profile(dto):
    # 1. Kiểm tra Họ tên (bắt buộc trong Model)
    if not dto.full_name or not dto.full_name.strip():
        raise ValidationError("Họ và tên không được để trống")

    # 2. Kiểm tra Số điện thoại
    if dto.phone:
        # Check độ dài tối thiểu và định dạng số
        if len(dto.phone) < 10 or not dto.phone.isdigit():
            raise ValidationError("Số điện thoại không hợp lệ (phải có ít nhất 10 số)")

    # 3. Kiểm tra Giới tính (Vì Model yêu cầu nullable=False)
    if not hasattr(dto, 'gender') or not dto.gender:
        raise ValidationError("Vui lòng chọn giới tính")
        
    # 4. Kiểm tra Ngày sinh
    if not hasattr(dto, 'dob') or not dto.dob:
        raise ValidationError("Vui lòng nhập ngày sinh")


def validate_change_password(dto):
    # 1. Kiểm tra trống
    if not dto.current_password:
        raise ValidationError("Vui lòng nhập mật khẩu hiện tại")

    if not dto.new_password:
        raise ValidationError("Vui lòng nhập mật khẩu mới")

    # 2. Kiểm tra khớp mật khẩu
    if dto.new_password != dto.confirm_password:
        raise ValidationError("Mật khẩu xác nhận không khớp")

    # 3. Kiểm tra độ dài
    if len(dto.new_password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(
            f"Mật khẩu phải có ít nhất {MIN_PASSWORD_LENGTH} ký tự"
        )
    
    # 4. Kiểm tra mật khẩu mới không được trùng mật khẩu cũ
    if dto.new_password == dto.current_password:
        raise ValidationError("Mật khẩu mới không được trùng với mật khẩu hiện tại")