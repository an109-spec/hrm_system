from dataclasses import dataclass
from typing import Optional


@dataclass
class LoginDTO:
    identifier: str   # email hoặc phone
    password: str


@dataclass
class RegisterDTO:
    password: str
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    # Bổ sung để phục vụ HRM:
    position: Optional[str] = None  # Vị trí ứng tuyển/làm việc
    department_id: Optional[int] = None # Phòng ban dự kiến


@dataclass
class RequestPasswordResetDTO:
    identifier: str   # email hoặc phone


@dataclass
class VerifyOTPDTO:
    """DTO dùng riêng cho việc kiểm tra mã OTP trước khi cho phép đổi mật khẩu"""
    identifier: str
    otp_code: str
    otp_type: str = "email"


@dataclass
class ResetPasswordDTO:
    identifier: str   # email hoặc phone
    otp_code: str
    new_password: str
    otp_type: str = "email"


@dataclass
class RequestPasswordResetResultDTO:
    otp_expires_at_iso: str
    delivery_channel: str
    otp_preview: Optional[str] = None