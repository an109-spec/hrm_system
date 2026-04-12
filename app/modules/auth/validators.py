import re
from app.common.exceptions import ValidationError

# Regex chuẩn hơn cho Email và Phone
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
PHONE_PATTERN = re.compile(r"^\+?\d{9,15}$")

# =========================
# HELPERS
# =========================
def validate_email(email: str) -> None:
    if not email or not email.strip():
        raise ValidationError("Email không được để trống")
    if not EMAIL_PATTERN.fullmatch(email.strip()):
        raise ValidationError("Định dạng Email không hợp lệ")

def validate_phone(phone: str) -> None:
    if not phone or not phone.strip():
        raise ValidationError("Số điện thoại không được để trống")
    if not PHONE_PATTERN.fullmatch(phone.strip()):
        raise ValidationError("Định dạng số điện thoại không hợp lệ")

def validate_password(password: str) -> None:
    if not password or not password.strip():
        raise ValidationError("Mật khẩu không được để trống")
    # HRM cần bảo mật cao hơn: ít nhất 8 ký tự, có thể thêm check chữ hoa/số nếu cần
    if len(password) < 8:
        raise ValidationError("Mật khẩu phải có ít nhất 8 ký tự")

# =========================
# REGISTER VALIDATOR (HRM Optimized)
# =========================
def validate_register(data: dict) -> list[str]:
    errors = []

    email = data.get("email")
    phone = data.get("phone")
    password = data.get("password")
    full_name = data.get("full_name")
    
    # HRM Specific fields
    position = data.get("position")
    department_id = data.get("department_id")

    # 1. Định danh: Trong HRM, Email thường là bắt buộc để gửi thông báo/lương
    if not email:
        errors.append("Email là bắt buộc đối với nhân viên")
    else:
        try:
            validate_email(email)
        except ValidationError as e:
            errors.append(str(e))

    # 2. Số điện thoại (Tùy chọn nhưng phải đúng định dạng nếu nhập)
    if phone:
        try:
            validate_phone(phone)
        except ValidationError as e:
            errors.append(str(e))

    # 3. Mật khẩu
    try:
        validate_password(password)
    except ValidationError as e:
        errors.append(str(e))

    # 4. Thông tin cá nhân
    if not full_name or not full_name.strip():
        errors.append("Vui lòng nhập họ và tên nhân viên")
    elif len(full_name.strip()) < 2:
        errors.append("Họ tên quá ngắn")

    # 5. Thông tin công việc (HRM logic)
    if not position or not position.strip():
        errors.append("Vui lòng nhập vị trí công việc")
    
    if not department_id:
        errors.append("Vui lòng chọn phòng ban làm việc")

    return errors

# =========================
# LOGIN VALIDATOR
# =========================
def validate_login(data: dict) -> None:
    if not isinstance(data, dict):
        raise ValidationError("Dữ liệu gửi lên không đúng định dạng")

    identifier = data.get("identifier")
    password = data.get("password")

    if not identifier or not identifier.strip():
        raise ValidationError("Vui lòng nhập Email hoặc Số điện thoại")

    if not password or not password.strip():
        raise ValidationError("Vui lòng nhập mật khẩu")